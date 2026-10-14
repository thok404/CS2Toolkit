"""Persisted duration, dialog editing and configuration import boundaries."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from PySide6.QtWidgets import QApplication, QWidget
from app.logic.config_manager import ConfigManager
from app.logic.flash_settings import normalize_flash_fade_duration
from app.logic.visual_handler import VisualHandler
from app.ui.pages.visual_page import VisualConfigDialog


class FlashSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(TemporaryDirectory()))
        self.stack.enter_context(patch.object(ConfigManager, "_resolve_work_dir", return_value=str(self.root)))
        self.stack.enter_context(patch.object(ConfigManager, "_migrate_legacy_work_dir"))
        self.config = ConfigManager()
        self.config.set("visual", {"flash_path": "preserved.png", "flash_enabled": True})
        self.parent = QWidget()
        self.parent.resize(1000, 700)
        self.addCleanup(self.parent.close)

    def dialog(self):
        dialog = VisualConfigDialog(self.config, "flash", self.parent)
        self.addCleanup(dialog.deleteLater)
        self.addCleanup(dialog.close)
        return dialog

    def test_missing_duration_uses_default_without_rewriting_existing_settings(self):
        before = dict(self.config.get("visual"))
        with patch.object(self.config, "save_config") as save:
            dialog = self.dialog()
            self.assertEqual(dialog.flash_fade_slider.value(), 10)
            self.assertEqual(dialog.flash_fade_value.text(), "1.0 秒")
            save.assert_not_called()
        self.assertEqual(self.config.get("visual"), before)

    def test_drag_saves_once_merges_latest_settings_and_survives_restart(self):
        dialog = self.dialog()
        with patch.object(self.config, "save_config", wraps=self.config.save_config) as save:
            dialog.flash_fade_slider.setSliderDown(True)
            dialog.flash_fade_slider.setValue(12)
            dialog.flash_fade_slider.setValue(15)
            save.assert_not_called()
            # Simulate another setting replacing the object while the dialog
            # is open. Saving the duration must retain that current state.
            self.config.set("visual", {"flash_path": "latest.png", "kill_icon_enabled": True})
            save.reset_mock()
            dialog.flash_fade_slider.setSliderDown(False)
            self.assertEqual(save.call_count, 1)
        reloaded = ConfigManager()
        self.assertEqual(reloaded.get("visual"), {"flash_path": "latest.png",
                         "kill_icon_enabled": True, "flash_fade_duration_ms": 1500})
        reopened = VisualConfigDialog(reloaded, "flash", self.parent)
        self.addCleanup(reopened.close)
        self.addCleanup(reopened.deleteLater)
        self.assertEqual(reopened.flash_fade_slider.value(), 15)
        with patch("app.logic.visual_handler.find_cs2_window", return_value=0), \
                patch("app.logic.visual_handler.AudioSessionController"):
            handler = VisualHandler(reloaded)
            try:
                self.assertEqual(handler.overlay._flash_fade_duration, 1500)
            finally:
                handler.cleanup()
                handler.overlay.close()
                handler.overlay.deleteLater()
                handler._audio_executor.shutdown(wait=True)

    def test_keyboard_zero_and_reset_are_saved_without_replacing_other_choices(self):
        dialog = self.dialog()
        dialog.flash_fade_slider.setValue(0)
        self.assertEqual(dialog.flash_fade_value.text(), "无淡出")
        self.assertEqual(self.config.get("visual")["flash_fade_duration_ms"], 0)
        dialog.flash_fade_reset.click()
        self.assertEqual(self.config.get("visual")["flash_fade_duration_ms"], 1000)
        self.assertEqual(self.config.get("visual")["flash_path"], "preserved.png")

    def test_imported_values_are_bounded_and_invalid_optional_values_keep_default(self):
        for value, expected in [(None, 1000), (True, 1000), ("fast", 1000),
                                (500.0, 1000), (-100, 0), (9999, 2000), (650, 700)]:
            with self.subTest(value=value):
                self.assertEqual(normalize_flash_fade_duration(value), expected)


if __name__ == "__main__":
    unittest.main()
