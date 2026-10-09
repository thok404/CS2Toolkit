"""Exercise replacement/restore against a disposable game installation."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.logic.font_replacer import FontReplacer
from app.logic.replacement_backup import ReplacementBackup


class FontReplacementTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.library = self.root / "library"
        self.game = self.library / "steamapps/common/Counter-Strike Global Offensive/game"
        self.fonts = self.game / "csgo/panorama/fonts"
        self.global_conf = self.game / "core/panorama/fonts/conf.d/42-repl-global.conf"
        self.fonts.mkdir(parents=True)
        self.global_conf.parent.mkdir(parents=True)
        self.stock = {
            self.fonts / "fonts.conf": b"<fontconfig><fontpattern>notosans</fontpattern><fontpattern>.uifont</fontpattern></fontconfig>\r\n",
            self.fonts / "notosans-regular.ttf": b"stock font bytes",
            self.fonts / "symbols.uifont": b"stock symbols",
            self.global_conf: b"<fontconfig><!-- FONT TO REPLACE --></fontconfig>\r\n",
        }
        self.write_stock()
        self.source = self.root / "custom.ttf"
        self.source.write_bytes(b"\0" * 32)
        self.backups = self.root / "backups"
        self.replacer = FontReplacer(str(self.library), str(self.backups))

    def write_stock(self):
        for path, data in self.stock.items():
            path.write_bytes(data)

    def game_bytes(self):
        return {str(path.relative_to(self.game)): path.read_bytes()
                for path in self.game.rglob("*") if path.is_file()}

    def replace(self, source=None):
        result = self.replacer.replace_font(str(source or self.source))
        self.assertTrue(result["success"], result)

    def assert_stock(self):
        expected = {str(path.relative_to(self.game)): data for path, data in self.stock.items()}
        self.assertEqual(self.game_bytes(), expected)

    def test_replace_then_restore_exact_bytes(self):
        self.replace()
        self.assertTrue(self.replacer.is_font_replacement_intact(str(self.source)))
        self.assertEqual(self.replacer.restore_font(), {"success": True, "needs_verify": False})
        self.assert_stock()

    def test_second_font_keeps_original_baseline(self):
        self.replace()
        second = self.root / "second.ttf"
        second.write_bytes(b"\0" * 40)
        self.replace(second)
        self.replacer.restore_font()
        self.assert_stock()

    def test_custom_name_colliding_with_stock_is_restored(self):
        source = self.root / "notosans-regular.ttf"
        source.write_bytes(b"\0" * 32)
        self.replace(source)
        self.replacer.restore_font()
        self.assert_stock()

    def test_steam_restored_configs_are_detected_and_repaired(self):
        self.replace()
        for path in (self.fonts / "fonts.conf", self.global_conf):
            path.write_bytes(self.stock[path])
        self.assertFalse(self.replacer.is_font_replacement_intact(str(self.source)))
        self.replace()
        self.replacer.restore_font()
        self.assert_stock()

    def test_complete_game_update_refreshes_stock_baseline(self):
        self.replace()
        self.stock[self.fonts / "notosans-regular.ttf"] = b"updated stock bytes"
        self.write_stock()
        self.replace()
        self.replacer.restore_font()
        self.assert_stock()

    def test_failed_update_restores_previous_custom_font(self):
        self.replace()
        before = self.game_bytes()
        second = self.root / "second.ttf"
        second.write_bytes(b"\0" * 40)
        with patch.object(self.replacer, "update_global_conf", side_effect=OSError("locked")):
            result = self.replacer.replace_font(str(second))
        self.assertFalse(result["success"])
        self.assertEqual(self.game_bytes(), before)
        self.replacer.restore_font()
        self.assert_stock()

    def test_failure_at_each_write_restores_original_files(self):
        for method in ("clear_fonts_directory", "copy_font_file", "create_fonts_conf", "update_global_conf"):
            with self.subTest(method=method):
                with patch.object(self.replacer, method, side_effect=OSError("write failed")):
                    result = self.replacer.replace_font(str(self.source))
                self.assertFalse(result["success"])
                self.assert_stock()

    def test_failed_repair_preserves_partial_steam_update(self):
        self.replace()
        for path in (self.fonts / "fonts.conf", self.global_conf):
            path.write_bytes(self.stock[path])
        before = self.game_bytes()
        with patch.object(self.replacer, "copy_font_file", side_effect=OSError("locked")):
            self.assertFalse(self.replacer.replace_font(str(self.source))["success"])
        self.assertEqual(self.game_bytes(), before)
        self.replacer.restore_font()
        self.assert_stock()

    def test_missing_configs_are_removed_on_rollback(self):
        for path in self.stock:
            path.unlink()
        before = self.game_bytes()
        with patch.object(self.replacer, "update_global_conf", side_effect=OSError("locked")):
            self.assertFalse(self.replacer.replace_font(str(self.source))["success"])
        self.assertEqual(self.game_bytes(), before)

    def test_failed_rollback_is_retained_for_next_operation(self):
        self.replace()
        with patch.object(self.replacer, "copy_font_file", side_effect=OSError("copy failed")), \
                patch.object(ReplacementBackup, "restore", side_effect=OSError("restore failed")):
            result = self.replacer.replace_font(str(self.source))
        self.assertFalse(result["success"])
        operation = self.replacer._backup_operation() + ".rollback"
        self.assertIsNotNone(ReplacementBackup.latest(self.backups, operation))
        self.assertTrue(self.replacer.restore_font()["success"])
        self.assert_stock()
        self.assertIsNone(ReplacementBackup.latest(self.backups, operation))

    def test_interrupted_replacement_can_be_retried(self):
        with patch.object(self.replacer, "copy_font_file", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.replacer.replace_font(str(self.source))
        self.replace()
        self.replacer.restore_font()
        self.assert_stock()

    def test_intact_original_restore_is_noop(self):
        self.assertEqual(self.replacer.restore_font(), {"success": True, "needs_verify": False})
        self.assert_stock()

    def test_legacy_custom_font_without_backup_requires_verification(self):
        self.replacer.clear_fonts_directory(str(self.fonts))
        self.replacer.copy_font_file(str(self.source), str(self.fonts))
        self.replacer.create_fonts_conf(str(self.fonts), "custom", "custom.ttf")
        self.replacer.update_global_conf(str(self.global_conf), "custom")
        self.assertEqual(self.replacer.restore_font(), {"success": True, "needs_verify": True})
        self.assertEqual(self.game_bytes(), {})

    def test_corrupt_backup_fails_and_is_kept(self):
        self.replace()
        baseline = ReplacementBackup.latest(self.backups, self.replacer._backup_operation())
        entry = next(entry for entry in baseline._entries.values() if entry["existed"])
        (baseline.operation_dir / entry["backup_path"]).write_bytes(b"corrupt")
        self.assertFalse(self.replacer.restore_font()["success"])
        self.assertTrue(Path(baseline.manifest_path).is_file())


if __name__ == "__main__":
    unittest.main()
