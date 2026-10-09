"""Verify the configured GSI endpoint using real loopback HTTP requests."""

from http.client import HTTPConnection
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from app.logic.gsi_manager import GSIManager


class GSIPortTests(unittest.TestCase):
    def free_port(self):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            return listener.getsockname()[1]

    def assert_endpoint(self, manager, port):
        started, received = Event(), Event()
        failures = []

        def on_data(data):
            if b'server_started' in data:
                started.set()
            elif b'error' in data:
                failures.append(data)
                started.set()
            elif data == b'{"player": {}}':
                received.set()

        manager.register_data_callback(on_data)
        self.assertTrue(manager.start_server())
        try:
            self.assertTrue(started.wait(5), "GSI server did not start")
            self.assertFalse(failures)
            self.assertEqual(manager.current_port, port)
            connection = HTTPConnection("127.0.0.1", port, timeout=3)
            try:
                connection.request("POST", "/", b'{"player": {}}', {"Content-Type": "application/json"})
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.read(), b"OK")
                self.assertTrue(received.wait(1))
            finally:
                connection.close()
        finally:
            manager.stop_server()

    def test_saved_port_matches_cfg_and_actual_http_listener(self):
        port = self.free_port()
        with TemporaryDirectory() as temporary, patch("app.logic.gsi_manager.GSISoundHandler"):
            cfg = Path(temporary) / "game/csgo/cfg"
            cfg.mkdir(parents=True)
            manager = GSIManager(temporary, {"gsi_port": port})
            self.assertTrue(manager.create_gsi_cfg()[0])
            self.assertIn(f"127.0.0.1:{port}", (cfg / "gamestate_integration_cs2toolkit.cfg").read_text())
            self.assert_endpoint(manager, port)

    def test_stopping_and_changing_port_restarts_on_new_endpoint(self):
        manager = GSIManager()
        first = self.free_port()
        manager.current_port = first
        self.assert_endpoint(manager, first)
        second = self.free_port()
        manager.current_port = second
        self.assert_endpoint(manager, second)


if __name__ == "__main__":
    unittest.main()
