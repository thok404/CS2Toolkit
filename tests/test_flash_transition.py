"""Exercise real Qt opacity transitions without a running CS2 process."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PySide6.QtCore import QEvent, QObject, Qt, Signal, QCoreApplication
from PySide6.QtTest import QTest
from types import SimpleNamespace
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from app.logic.visual_handler import OverlayWindow


class FlashTransitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, color in (("first.png", "red"), ("second.png", "blue")):
            pixmap = QPixmap(32, 32)
            pixmap.fill(QColor(color))
            pixmap.save(str(self.root / name))
        self.window_patch = patch("app.logic.visual_handler.find_cs2_window", return_value=0)
        self.window_patch.start()
        self.addCleanup(self.window_patch.stop)
        self.overlay = OverlayWindow()
        self.overlay.geometry_timer.stop()
        self.overlay.focus_timer.stop()
        self.addCleanup(self.close_overlay)

    def close_overlay(self):
        self.overlay.flash_recovery_timer.stop()
        self.overlay.flash_fade_timer.stop()
        self.overlay.close()
        self.overlay.deleteLater()
        self.app.processEvents()

    def start_recovery(self):
        self.overlay.update_flash(0)
        self.overlay._start_flash_fade_out()

    def advance_recovery(self, milliseconds):
        with patch.object(self.overlay._flash_fade_elapsed, "elapsed", return_value=milliseconds):
            self.overlay._advance_flash_fade()

    def test_recovery_is_continuous_monotonic_and_reaches_zero(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        self.overlay.update_flash(1)
        self.start_recovery()
        values = []
        for time in range(0, 1001, 25):
            self.advance_recovery(time)
            values.append(self.overlay.flash_label.opacity())
        self.assertEqual(values[0], 1.0)
        self.assertEqual(values[-1], 0.0)
        self.assertTrue(all(a >= b for a, b in zip(values, values[1:])))
        self.assertGreater(len(set(values)), 30)
        self.assertFalse(self.overlay.flash_fade_timer.isActive())

    def test_repeated_clear_state_does_not_restart_recovery(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        self.overlay.update_flash(1)
        self.start_recovery()
        self.advance_recovery(400)
        opacity = self.overlay.flash_label.opacity()
        self.overlay.update_flash(0)
        self.assertTrue(self.overlay.flash_fade_timer.isActive())
        self.assertFalse(self.overlay.flash_recovery_timer.isActive())
        self.assertEqual(self.overlay.flash_label.opacity(), opacity)

    def test_geometry_refresh_keeps_image_until_fully_transparent(self):
        with patch("app.logic.visual_handler.random.choice", side_effect=[
                str(self.root / "first.png"), str(self.root / "second.png")]) as choose:
            self.overlay.set_flash_image(str(self.root))
            self.overlay.update_flash(1)
            self.start_recovery()
            self.advance_recovery(400)
            source_key = self.overlay._flash_display_pixmap.cacheKey()
            with patch("app.logic.visual_handler.load_pixmap") as load:
                # Force a real label resize, then repeat a periodic geometry refresh.
                self.overlay.flash_label.resize(1, 1)
                self.overlay._update_geometry_to_game()
                self.overlay._update_geometry_to_game()
                load.assert_not_called()
            self.assertEqual(self.overlay._flash_display_pixmap.cacheKey(), source_key)
            self.assertEqual(choose.call_count, 1)
            self.advance_recovery(1000)
            self.assertEqual(self.overlay.flash_label.opacity(), 0.0)
            self.assertEqual(choose.call_count, 2)
            self.assertEqual(self.overlay._flash_display_pixmap.toImage().pixelColor(0, 0), QColor("blue"))

    def test_second_flash_cancels_fade_without_switching_image(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        source_key = self.overlay._flash_display_pixmap.cacheKey()
        self.overlay.update_flash(1)
        self.start_recovery()
        self.advance_recovery(400)
        self.overlay.update_flash(1)
        self.assertFalse(self.overlay.flash_fade_timer.isActive())
        self.assertEqual(self.overlay.flash_label.opacity(), 1.0)
        self.assertEqual(self.overlay._flash_display_pixmap.cacheKey(), source_key)

    def test_dpi_event_refreshes_pixel_cache_without_resetting_fade(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        self.overlay.update_flash(1)
        self.start_recovery()
        self.advance_recovery(400)
        source_key = self.overlay._flash_display_pixmap.cacheKey()
        before = self.overlay.flash_label.opacity()
        self.overlay._flash_prepared_ratio = 2.0
        QCoreApplication.sendEvent(self.overlay, QEvent(QEvent.DevicePixelRatioChange))
        self.assertEqual(self.overlay._flash_prepared_ratio, self.overlay.flash_label.devicePixelRatioF())
        self.assertEqual(self.overlay._flash_display_pixmap.cacheKey(), source_key)
        self.assertEqual(self.overlay.flash_label.opacity(), before)
        self.assertTrue(self.overlay.flash_fade_timer.isActive())
        self.start_recovery()
        self.advance_recovery(1000)
        self.assertEqual(self.overlay.flash_label.opacity(), 0.0)

    def test_onset_reveals_and_paints_before_waiting_for_focus_timer(self):
        class PaintRecorder(QObject):
            paints = 0

            def eventFilter(self, watched, event):
                if event.type() == QEvent.Paint:
                    self.paints += 1
                return False

        self.overlay.set_flash_image(str(self.root / "first.png"))
        self.app.processEvents()
        recorder = PaintRecorder()
        self.overlay.installEventFilter(recorder)
        self.overlay._focused_game = 0
        self.overlay.setWindowOpacity(0.0)
        with patch("app.logic.visual_handler.find_cs2_window", return_value=123), \
                patch("app.logic.visual_handler.foreground_window", return_value=123), \
                patch("app.logic.visual_handler.raise_overlay_window"), \
                patch.object(self.overlay, "_update_geometry_to_game"):
            self.overlay.update_flash(1)
        self.assertEqual(self.overlay.windowOpacity(), 1.0)
        self.assertGreater(recorder.paints, 0)
        self.overlay.removeEventFilter(recorder)

    def test_prepared_flash_is_shown_without_disk_or_process_scan(self):
        path = self.root / "first.png"
        self.overlay.set_flash_image(str(path))
        path.unlink()
        self.overlay._focused_game = 123
        with patch("app.logic.visual_handler.foreground_window", return_value=123), \
                patch("app.logic.visual_handler.find_cs2_window") as find, \
                patch("app.logic.visual_handler.load_pixmap") as load:
            self.overlay.update_flash(1)
        find.assert_not_called()
        load.assert_not_called()
        self.assertEqual(self.overlay.flash_label.opacity(), 1.0)
        self.assertEqual(self.overlay.windowOpacity(), 1.0)

    def test_transparent_image_and_letterbox_are_opaque_during_flash(self):
        pixmap = QPixmap(16, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        path = self.root / "transparent.png"
        pixmap.save(str(path))
        self.overlay.resize(96, 64)
        self.overlay.flash_label.setGeometry(self.overlay.rect())
        self.overlay.set_flash_image(str(path), "keep_aspect")
        self.overlay._focused_game = 123
        with patch("app.logic.visual_handler.foreground_window", return_value=123):
            self.overlay.update_flash(1)
        frame = self.overlay.grab().toImage()
        for x, y in [(0, 0), (95, 63), (48, 32)]:
            self.assertEqual(frame.pixelColor(x, y), QColor("#202020"))

    def test_flash_scaling_modes_prepare_physical_pixels_before_onset(self):
        source = QPixmap(20, 40)
        source.fill(QColor("red"))
        self.overlay.resize(96, 64)
        label = self.overlay.flash_label
        label.setGeometry(self.overlay.rect())
        ratio = label.devicePixelRatioF()
        for mode in ("stretch", "keep_aspect", "keep_aspect_crop"):
            with self.subTest(mode=mode):
                self.overlay._set_label_pixmap_from_pixmap(label, source, mode)
                prepared = label.pixmap()
                self.assertEqual((prepared.width(), prepared.height()),
                                 (round(96 * ratio), round(64 * ratio)))
                self.assertEqual(prepared.devicePixelRatio(), ratio)
                self.assertFalse(label.hasScaledContents())
                expected_corner = QColor("#202020") if mode == "keep_aspect" else QColor("red")
                self.assertEqual(prepared.toImage().pixelColor(0, 0), expected_corner)
                self.assertEqual(prepared.toImage().pixelColor(prepared.width()//2, prepared.height()//2), QColor("red"))

    def test_screen_scale_change_rebuilds_cache_without_changing_flash_image(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        source_key = self.overlay._flash_display_pixmap.cacheKey()
        # QLabel.pixmap() normalizes to the current screen; retain the scale
        # used to prepare the cache rather than inferring it from that getter.
        self.overlay._flash_prepared_ratio = 2.0
        with patch.object(self.overlay, "_set_label_pixmap_from_pixmap",
                             wraps=self.overlay._set_label_pixmap_from_pixmap) as prepare:
            self.overlay._update_geometry_to_game()
        prepare.assert_called_once()
        self.assertEqual(self.overlay._flash_display_pixmap.cacheKey(), source_key)
        self.assertEqual(self.overlay.flash_label.pixmap().devicePixelRatio(),
                         self.overlay.flash_label.devicePixelRatioF())

    def test_brief_clear_does_not_reveal_game_before_flash_returns(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        self.overlay.update_flash(1)
        self.overlay.update_flash(0)
        QTest.qWait(25)
        self.assertTrue(self.overlay.flash_recovery_timer.isActive())
        self.assertEqual(self.overlay.flash_label.opacity(), 1.0)
        self.overlay.update_flash(1)
        QTest.qWait(80)
        self.assertFalse(self.overlay.flash_recovery_timer.isActive())
        self.assertFalse(self.overlay.flash_fade_timer.isActive())
        self.assertEqual(self.overlay.flash_label.opacity(), 1.0)

    def test_repeated_clear_does_not_restart_confirmation_or_prevent_recovery(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        self.overlay.update_flash(1)
        self.overlay.update_flash(0)
        QTest.qWait(25)
        self.overlay.update_flash(0)
        QTest.qWait(50)
        self.assertFalse(self.overlay.flash_recovery_timer.isActive())
        self.assertTrue(self.overlay.flash_fade_timer.isActive())
        QTest.qWait(30)
        self.assertLess(self.overlay.flash_label.opacity(), 1.0)

    def test_recovery_uses_screen_cadence_and_elapsed_time_after_a_delayed_frame(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        self.overlay.update_flash(1)
        with patch.object(self.overlay, "screen", return_value=SimpleNamespace(refreshRate=lambda: 165)):
            self.start_recovery()
        self.assertEqual(self.overlay.flash_fade_timer.interval(), 6)
        self.assertEqual(self.overlay.flash_fade_timer.timerType(), Qt.PreciseTimer)
        self.advance_recovery(500)
        self.assertAlmostEqual(self.overlay.flash_label.opacity(), 0.5)
        self.advance_recovery(1150)
        self.assertEqual(self.overlay.flash_label.opacity(), 0.0)
        self.assertFalse(self.overlay.flash_fade_timer.isActive())

    def test_cover_and_background_fade_together_and_clear_previous_frame(self):
        pixmap = QPixmap(16, 32)
        pixmap.fill(QColor(0, 0, 0, 0))
        path = self.root / "transparent.png"
        pixmap.save(str(path))
        self.overlay.resize(96, 64)
        self.overlay.flash_label.setGeometry(self.overlay.rect())
        self.overlay.set_flash_image(str(path), "keep_aspect")
        self.overlay.setWindowOpacity(1.0)
        for opacity, alpha in ((1.0, 255), (0.5, 127), (0.0, 0)):
            self.overlay.flash_label.setOpacity(opacity)
            self.overlay.repaint()
            frame = self.overlay.grab().toImage()
            for x, y in [(0, 0), (frame.width()-1, frame.height()-1),
                         (frame.width()//2, frame.height()//2)]:
                self.assertLessEqual(abs(frame.pixelColor(x, y).alpha()-alpha), 1)

    def test_selected_duration_controls_recovery_and_zero_skips_fade(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        for duration in (0, 500, 1000, 2000):
            with self.subTest(duration=duration):
                self.overlay.set_flash_fade_duration(duration)
                self.overlay.update_flash(1)
                self.start_recovery()
                if duration:
                    self.advance_recovery(duration // 2)
                    self.assertAlmostEqual(self.overlay.flash_label.opacity(), 0.5)
                    self.advance_recovery(duration)
                self.assertEqual(self.overlay.flash_label.opacity(), 0.0)
                self.assertFalse(self.overlay.flash_fade_timer.isActive())

    def test_duration_change_during_fade_applies_to_next_recovery_without_a_jump(self):
        self.overlay.set_flash_image(str(self.root / "first.png"))
        self.overlay.set_flash_fade_duration(2000)
        self.overlay.update_flash(1)
        self.start_recovery()
        self.advance_recovery(400)
        before = self.overlay.flash_label.opacity()
        self.overlay.set_flash_fade_duration(500)
        self.advance_recovery(400)
        self.assertEqual(self.overlay.flash_label.opacity(), before)
        self.advance_recovery(2000)
        self.overlay.update_flash(1)
        self.start_recovery()
        self.advance_recovery(250)
        self.assertAlmostEqual(self.overlay.flash_label.opacity(), 0.5)

    def test_common_display_refresh_rates_choose_bounded_cadence(self):
        for rate, expected in [(0, 16), (60, 16), (120, 8), (144, 7),
                               (165, 6), (240, 4), (360, 4)]:
            with self.subTest(rate=rate), patch.object(self.overlay, "screen",
                    return_value=SimpleNamespace(refreshRate=lambda: rate)):
                self.overlay._refresh_flash_cadence()
                self.assertEqual(self.overlay.flash_fade_timer.interval(), expected)

    def test_screen_and_refresh_changes_keep_current_fade_progress(self):
        class Screen(QObject):
            refreshRateChanged = Signal(float)

            def __init__(self, rate):
                super().__init__()
                self.rate = rate

            def refreshRate(self):
                return self.rate

        first, second = Screen(60), Screen(240)
        current = [first]
        self.overlay.set_flash_image(str(self.root / "first.png"))
        source_key = self.overlay._flash_display_pixmap.cacheKey()
        with patch.object(self.overlay, "screen", side_effect=lambda: current[0]):
            self.overlay._on_flash_screen_changed(first)
            self.overlay.update_flash(1)
            self.start_recovery()
            self.advance_recovery(400)
            before = self.overlay.flash_label.opacity()
            current[0] = second
            self.overlay._on_flash_screen_changed(second)
            self.assertEqual(self.overlay.flash_fade_timer.interval(), 4)
            self.assertEqual(self.overlay.flash_label.opacity(), before)
            # The old monitor is disconnected; only the current monitor can
            # update cadence, and a rate change does not restart the fade clock.
            second.rate = 120
            first.refreshRateChanged.emit(60)
            self.assertEqual(self.overlay.flash_fade_timer.interval(), 4)
            second.refreshRateChanged.emit(120)
            self.assertEqual(self.overlay.flash_fade_timer.interval(), 8)
            self.advance_recovery(500)
            self.assertAlmostEqual(self.overlay.flash_label.opacity(), 0.5)
        self.assertEqual(self.overlay._flash_display_pixmap.cacheKey(), source_key)


if __name__ == "__main__":
    unittest.main()
