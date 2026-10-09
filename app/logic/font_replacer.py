# 字体替换功能模块
# 处理字体文件的复制和配置文件的生成

import hashlib
import os
import re
import shutil
from .font_config import FontConfigManager
from .replacement_backup import ReplacementBackup

# Valve 原版 42-repl-global.conf 只是带占位符的替换模板，被本工具改写后不再包含它
STOCK_GLOBAL_CONF_MARKER = "FONT TO REPLACE"
# 原版 fonts.conf 只按文件名放行原版字体，本工具生成的版本会额外放行所有 .ttf
TOOLKIT_FONT_PATTERN = ".ttf"


class FontReplacer:
    # 字体替换器

    def __init__(self, steam_library_path, backup_root):
        self.steam_library_path = steam_library_path
        self.config_manager = FontConfigManager()
        # 原版字体备份目录（位于数据目录内，随数据目录一起迁移）
        self.backup_root = backup_root

    def validate_paths(self, font_path):
        # 验证路径有效性

        if not os.path.isdir(self.steam_library_path):
            raise ValueError("Steam库路径无效！")

        # 直接构建CS2路径
        cs2_game_path = os.path.join(self.steam_library_path, "steamapps", "common", "Counter-Strike Global Offensive")
        if not os.path.exists(cs2_game_path):
            raise ValueError("CS2安装路径不存在！请检查CS2是否已安装。")

        cs2_game_dir = os.path.join(cs2_game_path, "game")
        if not os.path.exists(cs2_game_dir):
            raise ValueError("CS2游戏文件不完整！")

        if not font_path or not os.path.isfile(font_path):
            raise ValueError("请选择有效的字体文件！")

        if not font_path.lower().endswith('.ttf'):
            raise ValueError("只支持TTF格式的字体文件！")

        return True

    def get_fonts_directory(self):
        # 获取fonts目录路径
        cs2_path = os.path.join(self.steam_library_path, "steamapps", "common", "Counter-Strike Global Offensive")
        if not os.path.exists(cs2_path):
            return None
        return os.path.join(cs2_path, "game", "csgo", "panorama", "fonts")

    def get_global_conf_path(self):
        # 获取全局配置文件路径
        cs2_path = os.path.join(self.steam_library_path, "steamapps", "common", "Counter-Strike Global Offensive")
        if not os.path.exists(cs2_path):
            return None
        return os.path.join(cs2_path, "game", "core", "panorama", "fonts", "conf.d", "42-repl-global.conf")

    def clear_fonts_directory(self, fonts_dir):
        # 清空fonts目录
        try:
            if os.path.exists(fonts_dir):
                for filename in os.listdir(fonts_dir):
                    file_path = os.path.join(fonts_dir, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            else:

                os.makedirs(fonts_dir, exist_ok=True)
        except Exception as e:
            raise Exception(f"清空fonts目录失败: {str(e)}")

    def copy_font_file(self, src_path, dest_dir):
        # 复制字体文件到目标目录
        try:
            filename = os.path.basename(src_path)
            dest_path = os.path.join(dest_dir, filename)
            shutil.copy2(src_path, dest_path)
            return filename
        except Exception as e:
            raise Exception(f"复制字体文件失败: {str(e)}")

    def create_fonts_conf(self, fonts_dir, font_name, font_filename):
        # 生成fonts.conf文件
        try:
            conf_content = self.config_manager.generate_fonts_conf(font_name, font_filename)
            conf_path = os.path.join(fonts_dir, "fonts.conf")
            os.makedirs(fonts_dir, exist_ok=True)
            with open(conf_path, 'w', encoding='utf-8') as f:
                f.write(conf_content)
        except Exception as e:
            raise Exception(f"创建fonts.conf文件失败: {str(e)}")

    def update_global_conf(self, conf_path, font_name):
        # 更新42-repl-global.conf文件
        try:
            conf_content = self.config_manager.generate_global_conf(font_name)
            os.makedirs(os.path.dirname(conf_path), exist_ok=True)
            with open(conf_path, 'w', encoding='utf-8') as f:
                f.write(conf_content)
        except Exception as e:
            raise Exception(f"更新42-repl-global.conf文件失败: {str(e)}")

    @staticmethod
    def _read_text(path):
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except OSError:
            return None

    @staticmethod
    def _font_patterns(fonts_conf):
        return re.findall(r"<fontpattern>([^<]*)</fontpattern>", fonts_conf or "")

    def _is_stock_state(self, fonts_dir, global_conf_path):
        # 原版状态：fonts.conf 没有放行 .ttf，且 42-repl-global.conf 仍是 Valve 的占位模板
        fonts_conf = self._read_text(os.path.join(fonts_dir, "fonts.conf"))
        global_conf = self._read_text(global_conf_path)
        return (
            fonts_conf is not None
            and global_conf is not None
            and TOOLKIT_FONT_PATTERN not in self._font_patterns(fonts_conf)
            and STOCK_GLOBAL_CONF_MARKER in global_conf
        )

    def _stock_font_files(self, fonts_dir):
        # 原版 fonts.conf 只加载文件名匹配 fontpattern 的字体，其余文件是以前替换遗留的自定义字体
        fonts_conf_path = os.path.join(fonts_dir, "fonts.conf")
        patterns = [p.lower() for p in self._font_patterns(self._read_text(fonts_conf_path))]
        files = [fonts_conf_path]
        for name in os.listdir(fonts_dir):
            path = os.path.join(fonts_dir, name)
            if name != "fonts.conf" and os.path.isfile(path) and any(p in name.lower() for p in patterns):
                files.append(path)
        return files

    def _backup_operation(self):
        # 每个 CS2 安装目录各自保存一份原版字体基线
        fonts_dir = os.path.normcase(os.path.abspath(self.get_fonts_directory()))
        return "font-" + hashlib.sha1(fonts_dir.encode("utf-8")).hexdigest()[:12]

    def _recover_pending_replacement(self, operation):
        # 上次异常退出或回滚失败时保留的快照，必须恢复成功后才允许开始下一次操作。
        rollback = ReplacementBackup.latest(self.backup_root, f"{operation}.rollback")
        if rollback is not None:
            rollback.restore()
            os.remove(rollback.manifest_path)
            shutil.rmtree(rollback.operation_dir, ignore_errors=True)

    def is_font_replacement_intact(self, font_path):
        if not font_path or not os.path.isfile(font_path):
            return False

        fonts_dir = self.get_fonts_directory()
        global_conf_path = self.get_global_conf_path()
        if not fonts_dir or not global_conf_path:
            return False

        font_filename = os.path.basename(font_path)
        expected_font_path = os.path.join(fonts_dir, font_filename)
        if not os.path.isfile(expected_font_path) or os.path.getsize(expected_font_path) != os.path.getsize(font_path):
            return False

        # 游戏更新或 Steam 验证文件会把两个配置还原为原版，只检查文件是否存在会漏判
        font_name = self.extract_font_name(font_path)
        return (
            self._read_text(os.path.join(fonts_dir, "fonts.conf")) == self.config_manager.generate_fonts_conf(font_name, font_filename)
            and self._read_text(global_conf_path) == self.config_manager.generate_global_conf(font_name)
        )

    def restore_font(self):
        # 恢复游戏默认字体。needs_verify 为 True 表示没有原版备份，需要通过 Steam 验证游戏文件补回原版字体
        try:
            fonts_dir = self.get_fonts_directory()
            global_conf_path = self.get_global_conf_path()
            if not fonts_dir or not global_conf_path:
                return {"success": False, "error": "CS2安装路径不存在！"}

            operation = self._backup_operation()
            self._recover_pending_replacement(operation)
            baseline = ReplacementBackup.latest(self.backup_root, operation)
            if baseline is not None:
                baseline.restore()
                shutil.rmtree(baseline.operation_dir, ignore_errors=True)
                return {"success": True, "needs_verify": False}

            if self._is_stock_state(fonts_dir, global_conf_path):
                return {"success": True, "needs_verify": False}

            # 没有原版备份（例如由旧版本替换的字体）：移除本工具写入的文件，原版文件交给 Steam 验证补回
            if os.path.exists(fonts_dir):
                self.clear_fonts_directory(fonts_dir)
            global_conf = self._read_text(global_conf_path)
            if global_conf is not None and STOCK_GLOBAL_CONF_MARKER not in global_conf:
                os.remove(global_conf_path)
            return {"success": True, "needs_verify": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def extract_font_name(self, font_path):
        # 尝试从 TTF 文件中提取真实的字体 Family Name
        # 如果提取失败，则回退到使用文件名
        try:
            with open(font_path, 'rb') as f:
                f.seek(4)
                num_tables = int.from_bytes(f.read(2), 'big')
                f.seek(12)
                for _ in range(num_tables):
                    tag = f.read(4)
                    _checksum = f.read(4)
                    offset = int.from_bytes(f.read(4), 'big')
                    _length = int.from_bytes(f.read(4), 'big')
                    if tag == b'name':
                        f.seek(offset)
                        _format = int.from_bytes(f.read(2), 'big')
                        num_records = int.from_bytes(f.read(2), 'big')
                        string_offset = int.from_bytes(f.read(2), 'big')

                        font_names = {}
                        for _ in range(num_records):
                            platform_id = int.from_bytes(f.read(2), 'big')
                            encoding_id = int.from_bytes(f.read(2), 'big')
                            _lang_id = int.from_bytes(f.read(2), 'big')
                            name_id = int.from_bytes(f.read(2), 'big')
                            length = int.from_bytes(f.read(2), 'big')
                            record_offset = int.from_bytes(f.read(2), 'big')

                            if name_id == 1: # 1: Font Family Name
                                pos = f.tell()
                                f.seek(offset + string_offset + record_offset)
                                name_bytes = f.read(length)
                                if platform_id == 3 and encoding_id in (0, 1): # Windows
                                    font_names['win'] = name_bytes.decode('utf-16-be', errors='ignore')
                                elif platform_id == 1 and encoding_id == 0: # Mac
                                    font_names['mac'] = name_bytes.decode('mac_roman', errors='ignore')
                                f.seek(pos)

                        if 'win' in font_names:
                            return font_names['win']
                        elif 'mac' in font_names:
                            return font_names['mac']
                        break
        except Exception as e:
            print(f"解析TTF字体名称失败: {e}")

        # 回退到使用文件名
        filename = os.path.basename(font_path)
        return os.path.splitext(filename)[0]

    def replace_font(self, font_path, progress_callback=None):
        # 执行字体替换
        # 验证路径
        self.validate_paths(font_path)

        font_name = self.extract_font_name(font_path)
        font_filename = os.path.basename(font_path)

        # 定义路径
        fonts_dir = self.get_fonts_directory()
        global_conf_path = self.get_global_conf_path()
        font_target = os.path.join(fonts_dir, font_filename)

        operation = self._backup_operation()
        self._recover_pending_replacement(operation)
        baseline = ReplacementBackup.latest(self.backup_root, operation)

        if self._is_stock_state(fonts_dir, global_conf_path):
            # 游戏更新只会补回有改动的文件，配置恢复原版时被删除的原版字体可能仍然缺失；
            # 只有基线里的原版文件都已回来（首次替换或验证过文件）才用当前文件刷新基线。
            if baseline is None or all(os.path.isfile(path) for path in baseline.backed_up_paths()):
                stock_backup = ReplacementBackup(self.backup_root, operation)
                for path in self._stock_font_files(fonts_dir):
                    stock_backup.snapshot_file(path)
                stock_backup.snapshot_file(global_conf_path)
                stock_backup.commit()
                if baseline is not None:
                    shutil.rmtree(baseline.operation_dir, ignore_errors=True)
                baseline = stock_backup

        # 回滚始终恢复操作前的实际文件，包括只恢复了部分原版文件的状态。
        # 写入前持久化快照，失败时也不能删除尚未恢复的备份。
        rollback = ReplacementBackup(self.backup_root, f"{operation}.rollback")
        rollback.snapshot_directory(fonts_dir)
        rollback.snapshot_file(os.path.join(fonts_dir, "fonts.conf"))
        rollback.snapshot_file(global_conf_path)
        rollback.snapshot_file(font_target)
        rollback.commit()

        try:
            # 步骤1: 清空fonts目录
            if progress_callback:
                progress_callback("清空fonts目录...")
            self.clear_fonts_directory(fonts_dir)

            # 新字体文件由本工具创建：记入基线，恢复默认字体时删除
            if baseline is not None:
                baseline.snapshot_file(font_target)
                baseline.commit()

            # 步骤2: 复制字体文件
            if progress_callback:
                progress_callback("复制字体文件...")
            self.copy_font_file(font_path, fonts_dir)

            # 步骤3: 创建fonts.conf文件
            if progress_callback:
                progress_callback("创建fonts.conf文件...")
            self.create_fonts_conf(fonts_dir, font_name, font_filename)

            # 步骤4: 更新42-repl-global.conf文件
            if progress_callback:
                progress_callback("更新全局配置文件...")
            self.update_global_conf(global_conf_path, font_name)

            if progress_callback:
                progress_callback("字体替换完成！")

            os.remove(rollback.manifest_path)
            shutil.rmtree(rollback.operation_dir, ignore_errors=True)
            return {
                "success": True,
                "font_name": font_name,
                "font_filename": font_filename
            }

        except Exception as e:
            try:
                rollback.restore()
                os.remove(rollback.manifest_path)
                shutil.rmtree(rollback.operation_dir, ignore_errors=True)
            except Exception as restore_error:
                return {
                    "success": False,
                    "error": f"{e}; 回滚字体替换失败: {restore_error}",
                }
            if progress_callback:
                progress_callback("操作失败")
            return {
                "success": False,
                "error": str(e)
            }
