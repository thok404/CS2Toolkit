"""Verify the configured GSI endpoint using real loopback HTTP requests."""

from http.client import HTTPConnection
from pathlib import Path
import socket
import errno
import json
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch

from app.logic.gsi_manager import GSIManager, ReusableHTTPServer


class GSIPortTests(unittest.TestCase):
    def denied(self):
        error = PermissionError(errno.EACCES, "bind denied")
        error.winerror = 10013
        return error

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

    def test_denied_bind_falls_back_and_rewrites_cfg_before_success(self):
        port = self.free_port()
        with TemporaryDirectory() as temporary:
            cfg = Path(temporary) / "game/csgo/cfg"
            cfg.mkdir(parents=True)
            manager = GSIManager(temporary)
            manager.current_port = port
            manager.create_gsi_cfg()
            notifications = []
            started = Event()

            def callback(data):
                payload = json.loads(data)
                notifications.append(payload)
                if payload.get("success") == "server_started" or "error" in payload:
                    started.set()

            def factory(address, handler):
                if address[1] == port:
                    raise self.denied()
                return ReusableHTTPServer(address, handler)

            manager.register_data_callback(callback)
            with patch("app.logic.gsi_manager.ReusableHTTPServer", side_effect=factory):
                manager.start_server()
                try:
                    self.assertTrue(started.wait(5))
                    self.assertTrue(manager.is_running())
                    self.assertNotEqual(manager.current_port, port)
                    self.assertTrue(notifications[0]["cfg_updated"])
                    self.assertEqual(notifications[0]["requested_port"], port)
                    self.assertIn(f"127.0.0.1:{manager.current_port}", (cfg / "gamestate_integration_cs2toolkit.cfg").read_text())
                    connection = HTTPConnection("127.0.0.1", manager.current_port, timeout=3)
                    try:
                        connection.request("POST", "/", b'{}')
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        response.read()
                    finally:
                        connection.close()
                finally:
                    manager.stop_server()

    def test_whole_port_range_denied_uses_os_selected_port(self):
        port = self.free_port()
        attempted = []

        def factory(address, handler):
            attempted.append(address[1])
            if address[1]:
                raise self.denied()
            return ReusableHTTPServer(address, handler)

        manager = GSIManager()
        with patch("app.logic.gsi_manager.ReusableHTTPServer", side_effect=factory):
            server = manager._bind_server("127.0.0.1", port)
        try:
            self.assertEqual(attempted, list(range(port, min(port + 10, 65536))) + [0])
            self.assertGreater(server.server_address[1], 0)
        finally:
            server.server_close()

    def test_occupied_exclusive_port_is_not_shared(self):
        with socket.socket() as owner:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                owner.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            owner.bind(("127.0.0.1", 0))
            owner.listen()
            port = owner.getsockname()[1]
            manager = GSIManager()
            server = manager._bind_server("127.0.0.1", port)
            try:
                self.assertNotEqual(server.server_address[1], port)
                self.assertEqual(owner.getsockname()[1], port)
            finally:
                server.server_close()

    def test_all_bind_attempts_fail_startup_can_be_retried(self):
        manager = GSIManager()
        port = self.free_port()
        manager.current_port = port
        notifications = []
        failed = Event()

        def callback(data):
            notifications.append(json.loads(data))
            failed.set()

        manager.register_data_callback(callback)
        with patch("app.logic.gsi_manager.ReusableHTTPServer", side_effect=self.denied()) as factory:
            manager.start_server()
            self.assertTrue(failed.wait(5))
            manager._server_thread.join(5)
            self.assertEqual(factory.call_count, 11)
        self.assertEqual(notifications[0]["error"], "server_start_failed")
        self.assertFalse(manager.is_starting())
        self.assertFalse(manager.is_running())
        self.assert_endpoint(manager, port)

    def test_last_port_does_not_attempt_invalid_port_number(self):
        manager = GSIManager()
        with patch("app.logic.gsi_manager.ReusableHTTPServer", side_effect=self.denied()) as factory:
            with self.assertRaises(OSError):
                manager._bind_server("127.0.0.1", 65535)
        self.assertEqual([call.args[0][1] for call in factory.call_args_list], [65535, 0])

    def test_non_address_error_is_not_retried(self):
        with patch("app.logic.gsi_manager.ReusableHTTPServer", side_effect=OSError(errno.EMFILE, "no descriptors")) as factory:
            with self.assertRaises(OSError):
                GSIManager()._bind_server("127.0.0.1", self.free_port())
        factory.assert_called_once()

    def test_stopping_during_bind_does_not_leave_listener_running(self):
        entered, release = Event(), Event()
        manager = GSIManager()
        manager.current_port = self.free_port()
        opened = []

        def factory(address, handler):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test did not release binding")
            server = ReusableHTTPServer(address, handler)
            opened.append(server)
            return server

        with patch("app.logic.gsi_manager.ReusableHTTPServer", side_effect=factory):
            manager.start_server()
            try:
                self.assertTrue(entered.wait(5))
                manager.stop_server()
            finally:
                release.set()
                manager._server_thread.join(5)
        self.assertFalse(manager.is_starting())
        self.assertFalse(manager.is_running())
        self.assertEqual(opened[0].socket.fileno(), -1)


if __name__ == "__main__":
    unittest.main()
