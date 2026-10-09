import ctypes
import os
import subprocess

from .steam_utils import SteamUtils
from .cs2_window import find_cs2_window


class LaunchManager:
    @staticmethod
    def is_cs2_running():
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq cs2.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            output = (result.stdout or "").strip()
            if result.returncode == 0 and output and "INFO:" not in output.upper() and "没有运行的任务" not in output:
                return "cs2.exe" in output.lower()
        except Exception:
            pass

        try:
            return bool(find_cs2_window())
        except Exception:
            return False

    @staticmethod
    def launch_cs2(cs2_path, use_vulkan=False):
        if not cs2_path or not os.path.isdir(cs2_path):
            return False, "CS2 路径无效，请先正确设置游戏路径。"

        steam_root = SteamUtils.auto_detect_steam_path()
        if not steam_root:
            return False, "未检测到 Steam 安装目录，无法通过 Steam 启动 CS2。"

        steam_exe = os.path.join(steam_root, "Steam.exe")
        if not os.path.isfile(steam_exe):
            return False, f"找不到 Steam 可执行文件：{steam_exe}"

        command = [steam_exe, "-applaunch", "730"]
        if use_vulkan:
            command.append("-vulkan")

        try:
            subprocess.Popen(command, cwd=steam_root)
            if use_vulkan:
                return True, "已通过 Steam 启动 CS2，并附加 -vulkan 参数。"
            return True, "已通过 Steam 启动 CS2。"
        except Exception as e:
            return False, f"启动 CS2 失败：{e}"

    @staticmethod
    def close_cs2():
        try:
            result = subprocess.run(
                ["taskkill", "/F", "/IM", "cs2.exe"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            if result.returncode == 0:
                return True, "已请求关闭 CS2。"

            output = (result.stdout or "") + (result.stderr or "")
            if "not found" in output.lower() or "没有运行的实例" in output or "找不到进程" in output:
                return False, "当前未检测到正在运行的 CS2。"
            return False, output.strip() or "关闭 CS2 失败。"
        except Exception as e:
            return False, f"关闭 CS2 失败：{e}"
