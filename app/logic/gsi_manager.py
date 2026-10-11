import os
import json
import threading
import errno
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from .gsi_sound_handler import GSISoundHandler

class ReusableHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = False
    daemon_threads = True

class GSIHandler(BaseHTTPRequestHandler):
    # 处理GSI POST请求
    disable_nagle_algorithm = True

    def address_string(self):
        # 禁用耗时的反向 DNS 解析，直接返回 IP
        return self.client_address[0]

    # 隐藏成功的POST请求日志，以保持控制台清洁
    def log_message(self, format, *args):
        if self.command == "POST" and "200" in args:
            return
        super().log_message(format, *args)

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data_bytes = self.rfile.read(content_length)

            # 使用回调函数处理数据
            if hasattr(self.server, 'data_callback'):
                self.server.data_callback(post_data_bytes)

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            print(f"处理GSI POST请求时出错: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Error processing GSI data")


class GSIManager:
    # 管理 Game State Integration (GSI) 的所有功能
    def __init__(self, cs2_path=None, config_manager=None):
        self.cs2_path = cs2_path
        self.config_manager = config_manager
        self._server_thread = None
        self._httpd = None
        self._is_starting = False
        self._data_callbacks = []
        self.data_callback = self._dispatch_data
        self.current_port = 3000  # 当前使用的端口
        self.current_host = '127.0.0.1'  # 当前使用的主机

        if self.config_manager:
            saved_port = self.config_manager.get("gsi_port", 3000)
            if isinstance(saved_port, int) and 1 <= saved_port <= 65535:
                self.current_port = saved_port

        # 初始化GSI音效处理器
        self.sound_handler = GSISoundHandler(config_manager) if config_manager else None

        # 设置默认的数据处理回调
        if self.sound_handler:
            self.register_data_callback(self._default_data_handler)

    def get_gsi_cfg_content(self):
        # 生成GSI配置文件内容，使用当前端口
        return f'''
"gsi-cs2"
{{
    "uri" "http://{self.current_host}:{self.current_port}"
    "timeout" "1.0"
    "buffer"  "0.0"
    "throttle" "0.0"
    "heartbeat" "60.0"
    "auth"
    {{
        "token" "TOKEN"
    }}
    "output"
    {{
        "precision_time" "3"
        "precision_position" "1"
        "precision_vector" "3"
    }}
    "data"
    {{
        "map_round_wins" "0"
        "map" "0"
        "player_id" "1"
        "player_match_stats" "1"
        "player_state" "1"
        "player_weapons" "1"
        "provider" "1"
        "round" "1"
        "allgrenades" "0"
        "allplayers_id" "0"
        "allplayers_match_stats" "0"
        "allplayers_position" "0"
        "allplayers_state" "0"
        "allplayers_weapons" "0"
        "bomb" "1"
        "phase_countdowns" "1"
        "player_position" "0"
    }}
}}
'''

    def set_cs2_path(self, path):
        self.cs2_path = path

    def create_gsi_cfg(self):
        if not self.cs2_path or not os.path.isdir(self.cs2_path):
            return False, "CS2路径未设置或无效。"
        cfg_dir = os.path.join(self.cs2_path, "game", "csgo", "cfg")
        if not os.path.isdir(cfg_dir):
            return False, f"找不到CS2的CFG目录: {cfg_dir}"
        cfg_path = os.path.join(cfg_dir, "gamestate_integration_cs2toolkit.cfg")
        temporary_path = None
        original = None
        try:
            content = self.get_gsi_cfg_content()
            if os.path.isfile(cfg_path):
                with open(cfg_path, 'r', encoding='utf-8', newline='') as f:
                    original = f.read()
                # Preserve the installed token and data selections; only update
                # the URI when an existing integration file is present.
                import re
                content, count = re.subn(
                    r'("uri"\s*")[^"\r\n]*(")',
                    lambda match: match[1] + f"http://{self.current_host}:{self.current_port}" + match[2],
                    original,
                )
                if count != 1:
                    return False, "现有GSI配置的 uri 字段无效，请检查配置文件。"
                if content == original:
                    return True, f"GSI配置已与监听端口 {self.current_port} 一致。"
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='', dir=cfg_dir,
                                             prefix='.cs2toolkit-', suffix='.tmp', delete=False) as f:
                temporary_path = f.name
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            if original is not None:
                with open(cfg_path, 'r', encoding='utf-8', newline='') as f:
                    if f.read() != original:
                        return False, "GSI配置已被其他操作修改，请重试同步。"
            os.replace(temporary_path, cfg_path)
            return True, f"GSI配置文件已成功创建于: {cfg_path}\n使用端口: {self.current_port}"
        except IOError as e:
            return False, f"无法写入GSI配置文件: {e}"
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.remove(temporary_path)

    def register_data_callback(self, callback):
        # 注册处理GSI数据的回调函数。多个功能（例如集成音效和界面）
        # 需要同时消费同一份 GSI 数据，后注册的回调不能覆盖先注册的音效处理器。
        if callback and callback not in self._data_callbacks:
            self._data_callbacks.append(callback)

    def _dispatch_data(self, data_bytes):
        """Deliver one GSI payload to every registered consumer."""
        for callback in tuple(self._data_callbacks):
            try:
                callback(data_bytes)
            except Exception as exc:
                print(f"GSI回调处理失败: {exc}")

    def _default_data_handler(self, post_data_bytes):
        # 默认的GSI数据处理器
        if self.sound_handler:
            try:
                # 处理GSI数据并播放相应音效
                self.sound_handler.handle_gsi_data(post_data_bytes)
            except Exception as e:
                print(f"处理GSI数据时出错: {e}")

    def set_gsi_sound_pack(self, pack_path: str):
        # 设置GSI音效包
        if self.sound_handler:
            return self.sound_handler.set_gsi_sound_pack(pack_path)
        return False

    def set_gsi_sound_volume(self, volume: float):
        # 设置GSI音效音量
        if self.sound_handler:
            self.sound_handler.set_volume(volume)

    def test_gsi_sound(self, sound_type: str):
        # 测试GSI音效
        if self.sound_handler:
            self.sound_handler.test_sound(sound_type)

    def _bind_server(self, host, port, max_attempts=128):
        # A refused connection does not prove bind permission. Bind the real
        # listener once and retain it, including across Windows exclusions.
        candidates = list(range(port, min(port + max_attempts, 65536)))
        if len(candidates) < max_attempts:
            candidates.extend(range(3000, 3000 + max_attempts - len(candidates)))
        last_error = None
        for candidate in candidates:
            try:
                return ReusableHTTPServer((host, candidate), GSIHandler)
            except OSError as exc:
                if exc.errno not in (errno.EADDRINUSE, errno.EACCES, 10013, 10048):
                    raise
                last_error = exc
        raise OSError(f"无法绑定可用GSI端口（已尝试 {len(candidates)} 个端口）：{last_error}")

    def _server_target(self, host='127.0.0.1', port=3000):
        try:
            self._httpd = self._bind_server(host, port)
            self.current_port = self._httpd.server_address[1]
            self.current_host = host
            # 将回调函数传递给服务器实例，以便GSIHandler可以访问它
            self._httpd.data_callback = self.data_callback
            self._is_starting = False
            print(f"GSI服务器已在 {host}:{self.current_port} 上启动...")

            if self.current_port != port and self.data_callback:
                warning_info = {"warning": "port_changed", "old_port": port,
                                "new_port": self.current_port}
                self.data_callback(json.dumps(warning_info).encode('utf-8'))

            # 通知UI服务器启动成功
            if self.data_callback:
                success_info = {"success": "server_started", "port": self.current_port, "host": host}
                self.data_callback(json.dumps(success_info).encode('utf-8'))

            self._httpd.serve_forever()
        except OSError as e:
            self._is_starting = False
            print(f"无法启动GSI服务器: {e}")
            if self.data_callback:
                # 通过回调通知UI错误
                error_info = {"error": "server_start_failed", "message": str(e)}
                self.data_callback(json.dumps(error_info).encode('utf-8'))
        except Exception as e:
            self._is_starting = False
            print(f"GSI服务器发生意外错误: {e}")
            if self.data_callback:
                error_info = {"error": "server_unexpected_error", "message": str(e)}
                self.data_callback(json.dumps(error_info).encode('utf-8'))
        finally:
            if self._httpd is not None:
                self._httpd.server_close()
                self._httpd = None
            if self._httpd is None:
                self._is_starting = False

    def start_server(self):
        if self._is_starting or (self._server_thread and self._server_thread.is_alive()):
            print("GSI服务器已在运行中。")
            return False

        self._is_starting = True
        self._server_thread = threading.Thread(
            target=self._server_target,
            args=(self.current_host, self.current_port),
            daemon=True,
        )
        self._server_thread.start()
        return True

    def stop_server(self):
        self._is_starting = False
        httpd = self._httpd
        if httpd:
            print("正在关闭GSI服务器...")
            httpd.shutdown()
            httpd.server_close()
            if self._httpd is httpd:
                self._httpd = None
        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=1)
        self._server_thread = None
        print("GSI服务器已停止。")

    def is_running(self):
        return self._httpd is not None and self._server_thread is not None and self._server_thread.is_alive()

    def is_starting(self):
        return self._is_starting
