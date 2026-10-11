import errno
import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from app.logic.gsi_manager import GSIManager, ReusableHTTPServer


class GSIStartupTests(unittest.TestCase):
    def test_denied_and_occupied_ports_are_retried(self):
        manager = GSIManager()
        server = object()
        with patch('app.logic.gsi_manager.ReusableHTTPServer', side_effect=[
            PermissionError(errno.EACCES, 'blocked'),
            OSError(errno.EADDRINUSE, 'occupied'), server,
        ]) as bind:
            self.assertIs(manager._bind_server('127.0.0.1', 32000), server)
        self.assertEqual([call.args[0][1] for call in bind.call_args_list],
                         [32000, 32001, 32002])

    def test_unrelated_bind_errors_are_reported(self):
        manager = GSIManager()
        with patch('app.logic.gsi_manager.ReusableHTTPServer',
                   side_effect=OSError(errno.ENETUNREACH, 'network unavailable')) as bind:
            with self.assertRaises(OSError):
                manager._bind_server('127.0.0.1', 32000)
            self.assertEqual(bind.call_count, 1)

    def test_selected_port_http_delivery_and_restart(self):
        manager = GSIManager()
        manager.current_port = 0  # OS-selected loopback port for test isolation.
        ready = threading.Event()
        delivered = []

        def receive(data):
            state = json.loads(data)
            if state.get('success') == 'server_started':
                ready.set()
            elif 'player' in state:
                delivered.append(state)

        manager.register_data_callback(receive)
        for _ in range(2):
            ready.clear()
            manager.current_port = 0
            self.assertTrue(manager.start_server())
            try:
                self.assertTrue(ready.wait(3), 'server did not start')
                self.assertNotEqual(manager.current_port, 3000)
                connection = http.client.HTTPConnection('127.0.0.1', manager.current_port, timeout=3)
                connection.request('POST', '/', body=b'{"player":{"activity":"playing"}}')
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b'OK')
                connection.close()
            finally:
                manager.stop_server()
            self.assertFalse(manager.is_running())
            self.assertFalse(manager.is_starting())
        self.assertEqual(len(delivered), 2)

    def test_cfg_sync_preserves_auth_and_data(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg_dir = Path(directory) / 'game' / 'csgo' / 'cfg'
            cfg_dir.mkdir(parents=True)
            cfg = cfg_dir / 'gamestate_integration_cs2toolkit.cfg'
            original = (b'"gsi"\r\n{\r\n "uri" "http://127.0.0.1:3000"\r\n'
                        b' "auth" { "token" "test-only" }\r\n'
                        b' "data" { "player_state" "1" }\r\n}\r\n')
            cfg.write_bytes(original)
            manager = GSIManager(cs2_path=directory)
            manager.current_port = 32001
            self.assertTrue(manager.create_gsi_cfg()[0])
            self.assertEqual(cfg.read_bytes(), original.replace(b':3000', b':32001'))
            self.assertFalse(list(cfg_dir.glob('.cs2toolkit-*.tmp')))

    def test_cfg_without_uri_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg_dir = Path(directory) / 'game' / 'csgo' / 'cfg'
            cfg_dir.mkdir(parents=True)
            cfg = cfg_dir / 'gamestate_integration_cs2toolkit.cfg'
            original = b'"custom" { "data" {} }'
            cfg.write_bytes(original)
            manager = GSIManager(cs2_path=directory)
            self.assertFalse(manager.create_gsi_cfg()[0])
            self.assertEqual(cfg.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
