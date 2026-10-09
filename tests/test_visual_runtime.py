"""GSI and audio regressions without a running game or real audio sessions."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from app.logic.visual_handler import VisualHandler, _native_rect_to_logical


class VisualRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.icon = str(Path(temporary.name) / "icon.png")
        Path(self.icon).write_bytes(b"icon")
        self.config = {"visual": {"kill_icon_enabled": True, "kill_icon_path": self.icon,
                                  "flash_enabled": True, "flash_reduce_volume_enabled": True}}
        self.overlay_patch = patch("app.logic.visual_handler.OverlayWindow")
        self.overlay_patch.start()
        self.addCleanup(self.overlay_patch.stop)
        self.audio_patch = patch("app.logic.visual_handler.AudioSessionController")
        self.controller = self.audio_patch.start().return_value
        self.addCleanup(self.audio_patch.stop)
        self.controller.reduce_process_volume.return_value = (True, "reduced")
        self.controller.restore_volume.return_value = (True, "restored")
        self.handler = VisualHandler(self.config)
        self.addCleanup(self.handler._audio_executor.shutdown, wait=True)
        self.addCleanup(self.handler.cleanup)
        self.kills = Mock()
        self.handler.signals.show_kill_icon.connect(self.kills)

    def state(self, kills, steamid="self", flashed=0):
        return {"provider": {"steamid": "self"}, "round": {"phase": "live"},
                "player": {"steamid": steamid, "team": "CT", "activity": "playing",
                           "state": {"health": 100, "flashed": flashed},
                           "match_stats": {"kills": kills}}}

    def test_spectating_does_not_trigger_a_kill_on_respawn(self):
        self.handler.process_gsi(self.state(10))
        self.handler.process_gsi(self.state(2, steamid="teammate"))
        self.handler.process_gsi(self.state(10))
        self.kills.assert_not_called()
        self.handler.process_gsi(self.state(11))
        self.kills.assert_called_once_with(self.icon)

    def test_short_advanced_icon_list_uses_fallback(self):
        self.config["visual"].update(kill_icon_is_advanced=True, kill_icons_1_5=[])
        self.handler.process_gsi(self.state(1))
        self.handler.process_gsi(self.state(2))
        self.kills.assert_called_once_with(self.icon)

    def test_short_flash_restores_volume_after_slow_reduction(self):
        started, release = Event(), Event()
        calls = []

        def reduce(*args):
            started.set()
            if not release.wait(5):
                raise TimeoutError("test did not release audio worker")
            calls.append("reduce")
            return True, "reduced"

        def restore():
            calls.append("restore")
            return True, "restored"

        self.controller.reduce_process_volume.side_effect = reduce
        self.controller.restore_volume.side_effect = restore
        try:
            self.handler.process_gsi(self.state(0, flashed=255))
            self.assertTrue(started.wait(5))
            self.handler.process_gsi(self.state(0, flashed=0))
            self.handler.cleanup()
            self.assertEqual(calls, [])
        finally:
            release.set()
        self.handler._audio_executor.shutdown(wait=True)
        self.assertEqual(calls, ["reduce", "restore"])

    def test_exit_restores_volume_once_and_ignores_late_gsi(self):
        self.handler.process_gsi(self.state(0, flashed=255))
        self.handler.cleanup()
        self.handler.cleanup()
        self.handler.process_gsi(self.state(0, flashed=255))
        self.handler._audio_executor.shutdown(wait=True)
        self.controller.reduce_process_volume.assert_called_once()
        self.controller.restore_volume.assert_called_once()

    def test_mixed_dpi_rects_preserve_monitor_origins(self):
        screens = [
            SimpleNamespace(geometry=lambda: QRect(0, 0, 1707, 960), devicePixelRatio=lambda: 1.5),
            SimpleNamespace(geometry=lambda: QRect(2560, 0, 1536, 864), devicePixelRatio=lambda: 1.25),
        ]
        with patch("app.logic.visual_handler.QGuiApplication.screens", return_value=screens):
            self.assertEqual(_native_rect_to_logical(0, 0, 2560, 1440), QRect(0, 0, 1707, 960))
            self.assertEqual(_native_rect_to_logical(2560, 0, 1920, 1080), QRect(2560, 0, 1536, 864))
            self.assertEqual(_native_rect_to_logical(2685, 125, 1000, 750), QRect(2660, 100, 800, 600))

    def test_negative_monitor_origin(self):
        screen = SimpleNamespace(geometry=lambda: QRect(-1920, 0, 1536, 864), devicePixelRatio=lambda: 1.25)
        with patch("app.logic.visual_handler.QGuiApplication.screens", return_value=[screen]):
            self.assertEqual(_native_rect_to_logical(-1920, 0, 1920, 1080), QRect(-1920, 0, 1536, 864))


if __name__ == "__main__":
    unittest.main()
