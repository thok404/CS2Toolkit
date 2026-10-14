"""Qt lifecycle/overlay and HTTP connection tests using isolated app data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import socket
from http.client import HTTPConnection
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import ExitStack
from unittest.mock import patch
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app.main_window import CS2Tool
from app.logic.config_manager import ConfigManager
from app.logic.launch_manager import LaunchManager
from app.logic.visual_handler import OverlayWindow
from app.ui.pages.about_page import AboutPage


class GameLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.startup = staticmethod(CS2Tool._deferred_startup_tasks)

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(TemporaryDirectory()))
        self.stack.enter_context(patch.object(ConfigManager, '_resolve_work_dir', return_value=str(self.root / 'data')))
        self.stack.enter_context(patch.object(ConfigManager, '_migrate_legacy_work_dir'))
        self.stack.enter_context(patch.object(CS2Tool, '_deferred_startup_tasks'))
        self.stack.enter_context(patch.object(AboutPage, '_fetch_donation_content'))
        self.stack.enter_context(patch.object(LaunchManager, 'is_cs2_running', return_value=False))
        self.stack.enter_context(patch('app.main_window.find_cs2_window', return_value=0))
        self.window = CS2Tool()
        self.window.game_monitor.stop()
        self.addCleanup(self.close_window)
        self.game = self.root / 'game'
        (self.game / 'game/bin/win64').mkdir(parents=True)
        (self.game / 'game/bin/win64/cs2.exe').write_bytes(b'')
        self.cfg = self.game / 'game/csgo/cfg'
        self.cfg.mkdir(parents=True)
        self.window.config_manager.set('steam_path', str(self.game))
        self.stack.enter_context(patch.object(self.window, 'check_for_updates'))
        self.stack.enter_context(patch.object(self.window, 'show_success'))
        self.stack.enter_context(patch.object(self.window, 'show_warning'))

    def close_window(self):
        self.window._force_quit = True
        self.window.close()
        self.window.tray_icon.hide()
        self.window.visual_handler.overlay.close()
        self.window.visual_handler._audio_executor.shutdown(wait=True)

    def free_port(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            return listener.getsockname()[1]

    def wait_started(self):
        for _ in range(100):
            QTest.qWait(10)
            if self.window.gsi_manager.is_running():
                return
        self.fail('GSI did not start')

    def send_state(self):
        port = self.window.gsi_manager.current_port
        connection = HTTPConnection('127.0.0.1', port, timeout=3)
        try:
            payload = {'provider': {'steamid': 'self'}, 'map': {'mode': 'deathmatch'},
                       'player': {'steamid': 'self', 'activity': 'playing', 'state': {'health': 100}}}
            connection.request('POST', '/', json.dumps(payload), {'Content-Type': 'application/json'})
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
        finally:
            connection.close()
        QTest.qWait(30)
        self.assertEqual(self.window.last_game_state_overview['activity'], 'playing')

    def test_tool_first_prepares_game_cfg_before_game_connects(self):
        self.window.gsi_manager.current_port = self.free_port()
        self.startup(self.window)
        self.wait_started()
        self.assertEqual(self.window.gsi_manager.cs2_path, str(self.game))
        self.assertIn(f'127.0.0.1:{self.window.gsi_manager.current_port}', (self.cfg / 'gamestate_integration_cs2toolkit.cfg').read_text())
        self.send_state()

    def test_game_first_connects_to_endpoint_already_loaded_by_game(self):
        game_port = self.free_port()
        (self.cfg / 'gamestate_integration_cs2toolkit.cfg').write_text(f'"uri" "http://127.0.0.1:{game_port}"')
        self.window.gsi_manager.current_port = self.free_port()
        self.startup(self.window)
        self.wait_started()
        self.assertEqual(self.window.gsi_manager.current_port, game_port)
        self.send_state()

    def test_game_appearance_exit_and_relaunch_resets_event_baselines(self):
        with patch('app.main_window.find_cs2_window', side_effect=[123, 0, 456]), \
                patch.object(self.window.visual_handler, 'reset_game_state') as visual, \
                patch.object(self.window.integrated_sound_page, 'reset_game_state') as sound, \
                patch.object(self.window.go_pet_manager, 'reset_game_state') as pet, \
                patch.object(self.window, '_perform_steam_detection'), \
                patch.object(self.window.visual_handler.overlay, '_update_geometry_to_game'), \
                patch.object(self.window.visual_handler.overlay, '_check_game_focus'):
            for _ in range(3):
                self.window._poll_game_lifecycle()
        self.assertEqual(visual.call_count, 3)
        self.assertEqual(sound.call_count, 3)
        self.assertEqual(pet.call_count, 3)
        self.assertEqual(self.window._game_window, 456)

    def test_overlay_is_repositioned_and_raised_when_late_game_gains_focus(self):
        overlay = self.window.visual_handler.overlay
        overlay.focus_timer.stop()
        overlay._focused_game = 0
        with patch('app.logic.visual_handler.find_cs2_window', return_value=123), \
                patch('app.logic.visual_handler.foreground_window', return_value=123), \
                patch('app.logic.visual_handler.raise_overlay_window') as raise_window, \
                patch.object(overlay, '_update_geometry_to_game') as position:
            overlay._check_game_focus()
            overlay._check_game_focus()
        position.assert_called_once()
        raise_window.assert_called_once()
        self.assertEqual(overlay.windowOpacity(), 1.0)
        with patch('app.logic.visual_handler.find_cs2_window', return_value=123), \
                patch('app.logic.visual_handler.foreground_window', return_value=456):
            overlay._check_game_focus()
        self.assertEqual(overlay.windowOpacity(), 0.0)

    def test_flash_cover_is_presented_before_status_ui_and_sound_work(self):
        order = []
        with patch.object(self.window.visual_handler, 'process_gsi', side_effect=lambda _: order.append('visual')), \
                patch.object(self.window.home_tab, 'update_gsi_overview', side_effect=lambda: order.append('overview')), \
                patch.object(self.window.integrated_sound_page, 'process_game_state', side_effect=lambda _: order.append('sound')), \
                patch.object(self.window.go_pet_manager, 'process_gsi', side_effect=lambda _: order.append('pet')):
            self.window.handle_gsi_data_on_ui_thread({'player': {'state': {'flashed': 255}}})
        self.assertEqual(order, ['visual', 'overview', 'sound', 'pet'])


if __name__ == '__main__':
    unittest.main()
