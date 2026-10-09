from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
from qfluentwidgets import (ScrollArea, ExpandLayout, SettingCardGroup,
                            SettingCard, SwitchButton, ComboBox, FluentIcon as FIF,
                            setTheme, Theme, PushButton, Slider, BodyLabel, MessageBoxBase, SubtitleLabel, LineEdit, CheckBox, PrimaryPushButton)
from PySide6.QtGui import QColor
import winreg
import sys
import os

IMPORT_OPTION_LABELS = {
    "bg": "自定义软件背景",
    "theme": "应用主题",
    "video": "开屏动画",
    "sound": "启动音效",
    "font": "全局字体",
    "visual": "游戏内视觉效果 (闪白/击杀/死亡)",
    "gsi": "游戏内实时音效配置",
    "go_pet": "GO桌宠配置与资源",
}

class BackgroundSettingDialog(MessageBoxBase):
    """ 自定义背景设置对话框 """
    def __init__(self, config_manager, parent_window, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.parent_window = parent_window

        self.titleLabel = SubtitleLabel('自定义背景设置', self)

        # 将组件添加到布局中
        self.viewLayout.addWidget(self.titleLabel)

        # 图片选择
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(BodyLabel("图片路径:"))
        self.path_label = BodyLabel("未选择")
        self.path_label.setStyleSheet("color: #666666;")

        bg_path = self.config_manager.get("bg_path", "")
        if bg_path:
            self.path_label.setText(os.path.basename(bg_path))

        selection_layout.addWidget(self.path_label, 1)
        self.select_btn = PushButton("选择图片", self)
        self.select_btn.clicked.connect(self._on_select_bg)
        selection_layout.addWidget(self.select_btn)

        self.clear_btn = PushButton("清除", self)
        self.clear_btn.clicked.connect(self._on_clear_bg)
        selection_layout.addWidget(self.clear_btn)

        self.viewLayout.addLayout(selection_layout)

        # 缩放方式
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(BodyLabel("缩放方式:"))
        self.scale_combo = ComboBox()
        self.scale_combo.addItems(["等比缩放", "填充", "拉伸", "居中"])
        self.scale_combo.setCurrentIndex(self.config_manager.get("bg_scale", 0))
        self.scale_combo.currentIndexChanged.connect(self._on_bg_scale_changed)
        scale_layout.addWidget(self.scale_combo)
        scale_layout.addStretch(1)
        self.viewLayout.addLayout(scale_layout)

        # 亮度
        bright_layout = QHBoxLayout()
        bright_layout.addWidget(BodyLabel("亮度:"))
        self.bright_slider = Slider(Qt.Horizontal)
        self.bright_slider.setRange(10, 100)
        self.bright_slider.setValue(self.config_manager.get("bg_bright", 100))
        self.bright_slider.valueChanged.connect(self._on_bg_bright_changed)
        bright_layout.addWidget(self.bright_slider)
        self.viewLayout.addLayout(bright_layout)

        # 模糊
        blur_layout = QHBoxLayout()
        blur_layout.addWidget(BodyLabel("模糊:"))
        self.blur_slider = Slider(Qt.Horizontal)
        self.blur_slider.setRange(0, 50)
        self.blur_slider.setValue(self.config_manager.get("bg_blur", 0))
        self.blur_slider.valueChanged.connect(self._on_bg_blur_changed)
        blur_layout.addWidget(self.blur_slider)
        self.viewLayout.addLayout(blur_layout)

        self.widget.setMinimumWidth(360)

    def _on_select_bg(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择背景图片", "", "图片文件 (*.png *.jpg *.jpeg)")
        if path:
            self.config_manager.set("bg_path", path)
            self.path_label.setText(os.path.basename(path))
            if hasattr(self.parent_window, 'apply_custom_background'):
                self.parent_window.apply_custom_background()

    def _on_clear_bg(self):
        self.config_manager.set("bg_path", "")
        self.path_label.setText("未选择")
        if hasattr(self.parent_window, 'apply_custom_background'):
            self.parent_window.apply_custom_background()

    def _on_bg_scale_changed(self, index):
        self.config_manager.set("bg_scale", index)
        if hasattr(self.parent_window, 'apply_custom_background'):
            self.parent_window.apply_custom_background()

    def _on_bg_bright_changed(self, value):
        self.config_manager.set("bg_bright", value)
        if hasattr(self.parent_window, 'apply_custom_background'):
            self.parent_window.apply_custom_background()

    def _on_bg_blur_changed(self, value):
        self.config_manager.set("bg_blur", value)
        if hasattr(self.parent_window, 'apply_custom_background'):
            self.parent_window.apply_custom_background()

class BackgroundSettingCard(SettingCard):
    def __init__(self, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.config_btn = PushButton("设置背景", self)
        self.hBoxLayout.addWidget(self.config_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

class MySwitchSettingCard(SettingCard):
    def __init__(self, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.switchButton = SwitchButton("关", self)
        self.switchButton.setOnText("开")
        self.switchButton.setOffText("关")
        self.hBoxLayout.addWidget(self.switchButton, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

class MyComboBoxSettingCard(SettingCard):
    def __init__(self, icon, title, content=None, texts=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.comboBox = ComboBox(self)
        if texts:
            self.comboBox.addItems(texts)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

class ExportConfigDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('导出配置', self)
        self.viewLayout.addWidget(self.titleLabel)

        self.name_input = LineEdit(self)
        self.name_input.setPlaceholderText("请输入配置名称 (必填)")
        self.name_input.textChanged.connect(self._validate)
        self.viewLayout.addWidget(self.name_input)

        self.desc_input = LineEdit(self)
        self.desc_input.setPlaceholderText("请输入配置描述 (可选)")
        self.viewLayout.addWidget(self.desc_input)

        self.viewLayout.addWidget(BodyLabel("请选择要导出的资源 (包括预设及当前正在使用的资源):"))

        self.checkboxes = {}
        options = {
            "bg": "自定义软件背景",
            "theme": "应用主题",
            "video": "开屏动画",
            "sound": "启动音效",
            "font": "全局字体",
            "visual": "游戏内视觉效果 (闪白/击杀/死亡)",
            "gsi": "游戏内实时音效配置",
            "go_pet": "GO桌宠配置与资源"
        }

        for key, label in options.items():
            cb = CheckBox(label, self)
            cb.setChecked(True)
            self.viewLayout.addWidget(cb)
            self.checkboxes[key] = cb

        self.widget.setMinimumWidth(350)
        self.yesButton.setDisabled(True)

    def _validate(self, text):
        self.yesButton.setDisabled(not bool(text.strip()))

    def get_data(self):
        selections = {k: cb.isChecked() for k, cb in self.checkboxes.items()}
        return self.name_input.text().strip(), self.desc_input.text().strip(), selections

class ImportConfirmDialog(MessageBoxBase):
    def __init__(self, meta, available_sections=None, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('确认导入配置', self)
        self.viewLayout.addWidget(self.titleLabel)
        self.checkboxes = {}

        name = meta.get("name", "未知")
        desc = meta.get("description", "无描述信息")
        available_sections = available_sections or {}

        self.viewLayout.addWidget(BodyLabel(f"配置名称: {name}"))
        self.viewLayout.addWidget(BodyLabel(f"配置描述: {desc}"))

        self.viewLayout.addWidget(BodyLabel("请选择要导入的配置项:"))
        for key, label in IMPORT_OPTION_LABELS.items():
            cb = CheckBox(label, self)
            is_available = bool(available_sections.get(key))
            cb.setChecked(is_available)
            cb.setEnabled(is_available)
            cb.stateChanged.connect(self._validate)
            self.viewLayout.addWidget(cb)
            self.checkboxes[key] = cb

        warning = BodyLabel("导入将覆盖当前对应的设置，是否继续？")
        warning.setStyleSheet("color: #d40000; margin-top: 10px;")
        self.viewLayout.addWidget(warning)

        self.widget.setMinimumWidth(350)
        self._validate()

    def _validate(self):
        self.yesButton.setDisabled(not any(cb.isChecked() for cb in self.checkboxes.values()))

    def get_selections(self):
        return {key: cb.isChecked() for key, cb in self.checkboxes.items()}

class QuickSwitchConfigCard(SettingCard):
    def __init__(self, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.comboBox = ComboBox(self)
        self.comboBox.setMinimumWidth(150)
        self.apply_btn = PushButton("应用", self)
        self.open_folder_btn = PushButton("打开文件夹", self)

        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.apply_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.open_folder_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

class ExportImportCard(SettingCard):
    def __init__(self, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.import_btn = PushButton("导入配置", self)
        self.export_btn = PushButton("导出配置", self)
        self.hBoxLayout.addWidget(self.import_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addWidget(self.export_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)

class DataStorageCard(SettingCard):
    def __init__(self, icon, title, content=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.open_btn = PushButton("打开目录", self)
        self.migrate_btn = PushButton("迁移目录", self)
        self.hBoxLayout.addWidget(self.open_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(8)
        self.hBoxLayout.addWidget(self.migrate_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)


class SettingPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent_window = parent
        self.config_manager = parent.config_manager

        self.view = QWidget(self)
        self.expandLayout = ExpandLayout(self.view)

        self.setObjectName("setting_page")
        self.view.setObjectName("setting_view")
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea {background: transparent; border: none;}")
        self.view.setStyleSheet("QWidget#setting_view {background: transparent;}")

        self._init_ui()

    def _init_ui(self):
        # 1. 个性化设置组
        self.personalGroup = SettingCardGroup("个性化", self.view)

        # 主题设置
        theme_val = self.config_manager.get("theme", "Auto")

        self.themeCard = MyComboBoxSettingCard(
            icon=FIF.BRIGHTNESS,
            title="应用主题",
            content="更改应用程序的外观",
            texts=["浅色", "深色", "跟随系统"],
            parent=self.personalGroup
        )
        # 初始化选中项
        idx_map = {"Light": 0, "Dark": 1, "Auto": 2}
        self.themeCard.comboBox.setCurrentIndex(idx_map.get(theme_val, 2))
        self.themeCard.comboBox.currentIndexChanged.connect(self._on_theme_changed)
        self.personalGroup.addSettingCard(self.themeCard)

        # 背景设置
        self.bgCard = BackgroundSettingCard(
            icon=FIF.PHOTO,
            title="自定义背景",
            content="配置软件背景图片及其显示效果",
            parent=self.personalGroup
        )
        self.bgCard.config_btn.clicked.connect(self._show_bg_dialog)
        self.personalGroup.addSettingCard(self.bgCard)

        # 2. 系统行为设置组
        self.systemGroup = SettingCardGroup("系统", self.view)

        # 关闭行为
        close_val = self.config_manager.get("close_behavior", "prompt")

        self.closeCard = MyComboBoxSettingCard(
            icon=FIF.CLOSE,
            title="关闭窗口行为",
            content="点击右上角关闭按钮时的动作",
            texts=["每次询问", "最小化到托盘", "完全退出"],
            parent=self.systemGroup
        )
        idx_close_map = {"prompt": 0, "tray": 1, "exit": 2}
        self.closeCard.comboBox.setCurrentIndex(idx_close_map.get(close_val, 0))
        self.closeCard.comboBox.currentIndexChanged.connect(self._on_close_behavior_changed)
        self.systemGroup.addSettingCard(self.closeCard)

        # 开机自启
        auto_start_val = self.config_manager.get("auto_start", False)
        self.autoStartCard = MySwitchSettingCard(
            icon=FIF.POWER_BUTTON,
            title="开机自启",
            content="在系统登录时自动运行此程序",
            parent=self.systemGroup
        )
        self.autoStartCard.switchButton.setChecked(auto_start_val)
        self.autoStartCard.switchButton.checkedChanged.connect(self._on_auto_start_changed)
        self.systemGroup.addSettingCard(self.autoStartCard)

        # 3. 配置管理组
        self.configGroup = SettingCardGroup("配置管理", self.view)

        self.exportImportCard = ExportImportCard(
            icon=FIF.FOLDER,
            title="导入与导出",
            content="将当前的所有设置及资源文件打包导出，或从压缩包中导入并覆盖当前配置",
            parent=self.configGroup
        )
        self.exportImportCard.export_btn.clicked.connect(self._on_export_config)
        self.exportImportCard.import_btn.clicked.connect(self._on_import_config)
        self.configGroup.addSettingCard(self.exportImportCard)

        self.quickSwitchCard = QuickSwitchConfigCard(
            icon=FIF.SYNC,
            title="快捷切换配置",
            content="快速应用已保存的配置包",
            parent=self.configGroup
        )
        self.quickSwitchCard.apply_btn.clicked.connect(self._on_quick_switch)
        self.quickSwitchCard.open_folder_btn.clicked.connect(self._on_open_config_folder)
        self.configGroup.addSettingCard(self.quickSwitchCard)

        # 4. 危险操作组
        self.dangerGroup = SettingCardGroup("高级与危险操作", self.view)

        self.gsiControlCard = SettingCard(
            FIF.WIFI,
            "GSI 监听服务管理",
            "手动管理后台服务状态与通信端口",
            self.dangerGroup
        )
        self.gsi_port_input = LineEdit(self.gsiControlCard)
        self.gsi_port_input.setPlaceholderText("端口(默认3000)")
        self.gsi_port_input.setFixedWidth(100)
        self.gsi_toggle_btn = PushButton("启动服务", self.gsiControlCard)

        if hasattr(self.parent_window, 'gsi_manager'):
            mgr = self.parent_window.gsi_manager
            self.gsi_port_input.setText(str(mgr.current_port))
            if mgr.is_running():
                self.gsi_toggle_btn.setText("停止服务")
                self.gsi_port_input.setEnabled(False)

        self.gsi_regen_btn = PushButton("重新生成GSI配置", self.gsiControlCard)

        self.gsiControlCard.hBoxLayout.addWidget(self.gsi_port_input, 0, Qt.AlignmentFlag.AlignRight)
        self.gsiControlCard.hBoxLayout.addSpacing(8)
        self.gsiControlCard.hBoxLayout.addWidget(self.gsi_toggle_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.gsiControlCard.hBoxLayout.addSpacing(8)
        self.gsiControlCard.hBoxLayout.addWidget(self.gsi_regen_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.gsiControlCard.hBoxLayout.addSpacing(16)

        self.gsi_toggle_btn.clicked.connect(self._on_gsi_toggle)
        self.gsi_regen_btn.clicked.connect(self._on_gsi_regen)
        self.dangerGroup.addSettingCard(self.gsiControlCard)

        self.troubleshootCard = SettingCard(
            FIF.HELP,
            "自动疑难解答",
            "自动检查游戏路径、GSI端口、CFG文件等常见环境问题并提供修复建议",
            self.dangerGroup
        )
        self.troubleshoot_btn = PrimaryPushButton("开始检测", self.troubleshootCard)
        self.troubleshoot_btn.clicked.connect(self._on_troubleshoot)
        self.troubleshootCard.hBoxLayout.addWidget(self.troubleshoot_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.troubleshootCard.hBoxLayout.addSpacing(16)
        self.dangerGroup.addSettingCard(self.troubleshootCard)

        self.resetCard = SettingCard(
            FIF.DELETE,
            "重置所有设置",
            "将软件设置恢复为默认，并尝试清除已替换的开屏动画、音效、字体及自定义资源",
            self.dangerGroup
        )
        self.reset_btn = PrimaryPushButton("恢复默认", self.resetCard)
        self.reset_btn.setStyleSheet("QPushButton { background-color: #c42b1c; border: 1px solid #c42b1c; border-radius: 4px; padding: 5px 15px; } QPushButton:hover { background-color: #b02719; }")
        self.resetCard.hBoxLayout.addWidget(self.reset_btn, 0, Qt.AlignmentFlag.AlignRight)
        self.resetCard.hBoxLayout.addSpacing(16)
        self.reset_btn.clicked.connect(self._on_reset_all)
        self.dangerGroup.addSettingCard(self.resetCard)

        # 5. 数据存储组
        self.storageGroup = SettingCardGroup("数据存储", self.view)

        self.dataStorageCard = DataStorageCard(
            icon=FIF.FOLDER,
            title="数据保存目录",
            content=self.config_manager.work_dir,
            parent=self.storageGroup
        )
        self.dataStorageCard.open_btn.clicked.connect(self._on_open_data_dir)
        self.dataStorageCard.migrate_btn.clicked.connect(self._on_migrate_data_dir)
        self.storageGroup.addSettingCard(self.dataStorageCard)

        self.expandLayout.addWidget(self.personalGroup)
        self.expandLayout.addWidget(self.systemGroup)
        self.expandLayout.addWidget(self.configGroup)
        self.expandLayout.addWidget(self.storageGroup)
        self.expandLayout.addWidget(self.dangerGroup)

        self._load_quick_switch_configs()

    def _on_open_data_dir(self):
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.config_manager.work_dir))

    def _on_migrate_data_dir(self):
        from qfluentwidgets import MessageBox
        new_dir = QFileDialog.getExistingDirectory(self, "选择新的数据保存目录", self.config_manager.work_dir)
        if not new_dir:
            return

        success, msg = self.config_manager.change_work_dir(new_dir)
        if success:
            self.dataStorageCard.setContent(new_dir)
            dialog = MessageBox(
                "迁移成功",
                msg,
                self.parent_window
            )
            dialog.yesButton.setText("立即退出")
            dialog.cancelButton.hide()
            if dialog.exec():
                import sys
                sys.exit(0)
        else:
            self.parent_window.show_error("迁移失败", msg)

    def _show_bg_dialog(self):
        dialog = BackgroundSettingDialog(self.config_manager, self.parent_window, self)
        dialog.exec()

    def _on_gsi_toggle(self):
        if not hasattr(self.parent_window, 'gsi_manager'): return
        mgr = self.parent_window.gsi_manager
        if mgr.is_running():
            mgr.stop_server()
            self.gsi_toggle_btn.setText("启动服务")
            self.gsi_toggle_btn.setEnabled(True)
            self.gsi_port_input.setEnabled(True)
            self.parent_window.show_info("GSI 服务已停止", "监听服务已手动关闭")
            self.parent_window.update_home_status()
        else:
            try:
                new_port = int(self.gsi_port_input.text().strip())
            except ValueError:
                self.parent_window.show_error("端口错误", "请输入有效的数字端口")
                return

            if not 1 <= new_port <= 65535:
                self.parent_window.show_error("端口错误", "端口号必须在 1 到 65535 之间")
                return

            mgr.current_port = new_port
            started = mgr.start_server()
            if not started:
                self.parent_window.show_warning("提示", "GSI 服务正在启动或已经在运行中，请稍后重试。")
                return

            self.gsi_toggle_btn.setText("启动中...")
            self.gsi_toggle_btn.setEnabled(False)
            self.gsi_port_input.setEnabled(False)
            self.parent_window.update_home_status()

    def _on_gsi_regen(self):
        if not hasattr(self.parent_window, 'gsi_manager'): return
        mgr = self.parent_window.gsi_manager

        # 确保 steam_path 被传递到 mgr
        if hasattr(self.parent_window, 'steam_path') and self.parent_window.steam_path:
            mgr.set_cs2_path(self.parent_window.steam_path)

        # 尝试使用输入的端口更新
        try:
            new_port = int(self.gsi_port_input.text().strip())
        except ValueError:
            self.parent_window.show_error("端口错误", "请输入有效的数字端口")
            return

        if not 1 <= new_port <= 65535:
            self.parent_window.show_error("端口错误", "端口号必须在 1 到 65535 之间")
            return

        mgr.current_port = new_port
        success, msg = mgr.create_gsi_cfg()
        if success:
            self.config_manager.set("gsi_port", new_port)
            self.parent_window.show_success("GSI配置已重新生成", f"{msg}\n请【重启游戏】以使配置生效。")
        else:
            self.parent_window.show_error("生成失败", msg)

    def _on_troubleshoot(self):
        results = []
        all_passed = True

        # 1. 检查游戏路径
        steam_path = getattr(self.parent_window, 'steam_path', None)
        if not steam_path or not os.path.exists(steam_path):
            results.append("❌ 游戏路径: 未检测到有效路径。建议在主页手动指定。")
            all_passed = False
        else:
            exe_path = os.path.join(steam_path, "game", "bin", "win64", "cs2.exe")
            if not os.path.exists(exe_path):
                results.append(f"❌ 游戏路径: 找到文件夹，但不存在 cs2.exe ({exe_path})。路径可能已失效。")
                all_passed = False
            else:
                results.append("✅ 游戏路径: 正常。")

        # 2. 检查GSI服务与端口
        mgr = getattr(self.parent_window, 'gsi_manager', None)
        if mgr:
            if not mgr.is_running():
                results.append("❌ GSI服务: 未运行。如果无法启动，可能是端口被杀毒软件拦截。")
                all_passed = False
            else:
                import socket
                # 检查端口连通性 (仅做简单测试，可能被占用)
                try:
                    # 尝试连一下
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.5)
                    res = s.connect_ex(('127.0.0.1', mgr.current_port))
                    s.close()
                    if res == 0:
                        results.append(f"✅ GSI服务: 运行中 (端口 {mgr.current_port})。")
                    else:
                        results.append(f"⚠️ GSI服务: 端口 {mgr.current_port} 连接异常，可能被拦截。")
                except Exception as e:
                    results.append(f"⚠️ GSI服务: 测试异常 ({e})。")
        else:
            results.append("❌ GSI服务: 未初始化。")
            all_passed = False

        # 3. 检查 CFG 文件
        if steam_path and os.path.exists(steam_path):
            cfg_path = os.path.join(steam_path, "game", "csgo", "cfg", "gamestate_integration_cs2toolkit.cfg")
            if os.path.exists(cfg_path):
                results.append("✅ GSI配置: 存在于 CFG 目录。")
            else:
                results.append("❌ GSI配置: 缺失。请在“高级与危险操作”点击“重新生成GSI配置”。")
                all_passed = False

        # 总结
        summary = "\n\n".join(results)
        if all_passed:
            self.parent_window.show_success("检测通过", f"未发现明显异常，如果仍无声音，请尝试验证游戏完整性。\n\n检测报告:\n{summary}")
        else:
            self.parent_window.show_error("检测到异常", f"检测报告:\n{summary}")

    def _on_reset_all(self):
        dialog = MessageBoxBase(self.parent_window)
        dialog.titleLabel = SubtitleLabel("确认重置所有设置？", dialog)
        dialog.viewLayout.addWidget(dialog.titleLabel)

        warning = BodyLabel("此操作将清除您在软件内保存的所有预设、事件、自定义图片，并尝试移除游戏中已替换的视频、音效和字体。此操作不可逆！\n\n注意：如果遇到游戏资源问题，请通过 Steam 验证游戏完整性。")
        warning.setWordWrap(True)
        dialog.viewLayout.addWidget(warning)
        dialog.widget.setMinimumWidth(380)

        if dialog.exec():
            # 1. 恢复游戏资源
            font_result = None
            steam_path = self.parent_window.steam_path
            if steam_path and os.path.exists(steam_path):
                from ...logic.steam_utils import SteamUtils
                steam_lib = SteamUtils.extract_steam_library_from_cs2_path(steam_path)

                # 恢复音效
                from ...logic.sound_replacer import SoundReplacer
                SoundReplacer(steam_path).restore_sound()

                if steam_lib:
                    # 恢复字体
                    from ...logic.font_replacer import FontReplacer
                    font_result = FontReplacer(steam_lib, self.config_manager.replacement_backups_dir).restore_font()

                    # 恢复视频
                    from ...logic.video_replacer import VideoReplacer
                    v_replacer = VideoReplacer(steam_lib)
                    if hasattr(v_replacer, 'restore_video'):
                        v_replacer.restore_video()

            # 2. 恢复软件配置
            self.config_manager.reset_all()

            # 3. 刷新 UI
            self.parent_window.show_success("重置成功", "所有设置已恢复为初始状态。")
            if font_result and not font_result.get("success"):
                self.parent_window.show_warning("默认字体恢复失败", f"{font_result.get('error')}\n请关闭游戏后在“个性化 - 全局字体”中点击“恢复默认字体”重试。")
            elif font_result and font_result.get("needs_verify"):
                self.parent_window.show_warning("需要验证游戏文件", "已移除自定义字体，请通过 Steam 验证游戏文件完整性以补回默认字体。")
            self.parent_window.load_all_presets()
            self.parent_window.update_home_status()
            self.parent_window.apply_custom_background()
            if hasattr(self.parent_window, 'integrated_sound_page'):
                self.parent_window.integrated_sound_page.load_events()
            if hasattr(self.parent_window, 'visual_tab'):
                self.parent_window.visual_tab.config_manager = self.config_manager
                self.parent_window.visual_tab._update_ui_from_config()
            if hasattr(self.parent_window, 'go_pet_tab'):
                self.parent_window.go_pet_tab.reload_from_config()
            if hasattr(self.parent_window, 'go_pet_manager'):
                self.parent_window.go_pet_manager._update_config()

            # 刷新主题
            self.themeCard.comboBox.blockSignals(True)
            self.themeCard.comboBox.setCurrentIndex(2) # Auto
            self.themeCard.comboBox.blockSignals(False)
            self._on_theme_changed(2)

    def _on_theme_changed(self, index):
        val_map = {0: "Light", 1: "Dark", 2: "Auto"}
        theme_val = val_map.get(index, "Auto")
        self.config_manager.set("theme", theme_val)

        if theme_val == "Light":
            setTheme(Theme.LIGHT)
            self.parent_window.is_dark_mode = False
        elif theme_val == "Dark":
            setTheme(Theme.DARK)
            self.parent_window.is_dark_mode = True
        else:
            setTheme(Theme.AUTO)
            # Auto模式下判断实际颜色较为复杂，这里简单处理
            self.parent_window.is_dark_mode = False

    def _on_close_behavior_changed(self, index):
        val_map = {0: "prompt", 1: "tray", 2: "exit"}
        behavior = val_map.get(index, "prompt")
        self.config_manager.set("close_behavior", behavior)
        # 如果用户主动修改了这个选项，我们将 hide_close_prompt 置为 True
        if behavior != "prompt":
            self.config_manager.set("hide_close_prompt", True)
        else:
            self.config_manager.set("hide_close_prompt", False)

    def _on_auto_start_changed(self, is_checked):
        self.config_manager.set("auto_start", is_checked)
        self._set_windows_auto_start(is_checked)

    def _on_export_config(self):
        dialog = ExportConfigDialog(self)
        if dialog.exec():
            name, desc, selections = dialog.get_data()
            default_path = os.path.join(self.config_manager.configs_dir, f"{name}.zip")
            path, _ = QFileDialog.getSaveFileName(self, "导出配置", default_path, "ZIP 压缩包 (*.zip)")
            if path:
                success, msg = self.config_manager.export_config(path, name, desc, selections)
                if success:
                    # 如果用户选择保存到别的地方，我们也保存一份到 configs_dir 以便快捷切换
                    if os.path.dirname(os.path.abspath(path)) != os.path.abspath(self.config_manager.configs_dir):
                        import shutil
                        try:
                            shutil.copy2(path, os.path.join(self.config_manager.configs_dir, os.path.basename(path)))
                        except Exception:
                            pass
                    self._load_quick_switch_configs()
                    self.parent_window.show_success("导出成功", msg)
                else:
                    self.parent_window.show_error("导出失败", msg)

    def _on_import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入配置", "", "ZIP 压缩包 (*.zip)")
        if path:
            if not self.config_manager.is_valid_config_zip(path):
                self.parent_window.show_error("导入失败", "这不是有效的CS2Toolkit配置包。")
                return

            meta = self.config_manager.get_zip_meta(path)
            available_sections = self.config_manager.get_importable_sections(path)
            dialog = ImportConfirmDialog(meta, available_sections, self)
            if dialog.exec():
                selections = dialog.get_selections()
                import shutil
                dest_path = os.path.join(self.config_manager.configs_dir, os.path.basename(path))
                if os.path.abspath(path) != os.path.abspath(dest_path):
                    try:
                        if os.path.exists(dest_path):
                            import time
                            base, ext = os.path.splitext(os.path.basename(path))
                            dest_path = os.path.join(self.config_manager.configs_dir, f"{base}_{int(time.time())}{ext}")
                        shutil.copy2(path, dest_path)
                    except Exception as e:
                        print(f"复制配置文件失败: {e}")
                        dest_path = path

                self._apply_config_zip(dest_path, selections)
                self._load_quick_switch_configs()

    def _on_quick_switch(self):
        idx = self.quickSwitchCard.comboBox.currentIndex()
        if idx >= 0:
            zip_path = self.quickSwitchCard.comboBox.itemData(idx)
            if zip_path and os.path.exists(zip_path):
                meta = self.config_manager.get_zip_meta(zip_path)
                available_sections = self.config_manager.get_importable_sections(zip_path)
                dialog = ImportConfirmDialog(meta, available_sections, self)
                if dialog.exec():
                    self._apply_config_zip(zip_path, dialog.get_selections())
            else:
                self.parent_window.show_error("错误", "配置文件不存在。")
                self._load_quick_switch_configs()

    def _apply_config_zip(self, zip_path, selections=None):
        success, msg = self.config_manager.import_config(zip_path, selections)
        if success:
            self.parent_window.show_success("导入成功", "配置导入成功，界面即将刷新。")
            selections = selections or {}

            # Apply imported current selections to game files
            if selections.get("video", True):
                current_video = self.config_manager.get("current_video")
            else:
                current_video = ""
            if current_video:
                video_path = self.config_manager.get("current_video_path")
                if video_path and os.path.exists(video_path):
                    from ...logic.video_replacer import VideoReplacer
                    from ...logic.steam_utils import SteamUtils
                    steam_lib = SteamUtils.extract_steam_library_from_cs2_path(self.parent_window.steam_path)
                    if steam_lib:
                        replacer = VideoReplacer(steam_lib)
                        replacer.replace_video(video_path)

            current_sound = self.config_manager.get("current_sound") if selections.get("sound", True) else ""
            if current_sound:
                sound_path = self.config_manager.get("current_sound_path")
                if sound_path and os.path.exists(sound_path):
                    from ...logic.sound_replacer import SoundReplacer
                    replacer = SoundReplacer(self.parent_window.steam_path)
                    replacer.replace_sound(sound_path)

            current_font = self.config_manager.get("current_font") if selections.get("font", True) else ""
            if current_font:
                font_path = self.config_manager.get("current_font_path")
                if font_path and os.path.exists(font_path):
                    from ...logic.font_replacer import FontReplacer
                    from ...logic.steam_utils import SteamUtils
                    steam_lib = SteamUtils.extract_steam_library_from_cs2_path(self.parent_window.steam_path)
                    if steam_lib:
                        replacer = FontReplacer(steam_lib, self.config_manager.replacement_backups_dir)
                        replacer.replace_font(font_path, lambda msg: None)

            if selections.get("video", True) or selections.get("sound", True) or selections.get("font", True):
                self.parent_window.load_all_presets()
            self.parent_window.update_home_status()
            if selections.get("bg", True):
                self.parent_window.apply_custom_background()
            if selections.get("gsi", True) and hasattr(self.parent_window, 'integrated_sound_page'):
                self.parent_window.integrated_sound_page.load_events()
            if selections.get("visual", True) and hasattr(self.parent_window, 'visual_tab'):
                self.parent_window.visual_tab.config_manager = self.config_manager
                self.parent_window.visual_tab._update_ui_from_config()
            if selections.get("go_pet", True) and hasattr(self.parent_window, 'go_pet_tab'):
                self.parent_window.go_pet_tab.reload_from_config()
            if selections.get("go_pet", True) and hasattr(self.parent_window, 'go_pet_manager'):
                self.parent_window.go_pet_manager._update_config()

            # 刷新主题 (根据导入的配置)
            if selections.get("theme", True):
                theme_val = self.config_manager.get("theme", "Auto")
                idx_map = {"Light": 0, "Dark": 1, "Auto": 2}
                self.themeCard.comboBox.blockSignals(True)
                self.themeCard.comboBox.setCurrentIndex(idx_map.get(theme_val, 2))
                self.themeCard.comboBox.blockSignals(False)
                self._on_theme_changed(idx_map.get(theme_val, 2))

        else:
            self.parent_window.show_error("导入失败", msg)

    def _load_quick_switch_configs(self):
        self.quickSwitchCard.comboBox.clear()
        configs_dir = self.config_manager.configs_dir
        if not os.path.exists(configs_dir):
            return

        for f in os.listdir(configs_dir):
            if f.endswith('.zip'):
                zip_path = os.path.join(configs_dir, f)
                if self.config_manager.is_valid_config_zip(zip_path):
                    meta = self.config_manager.get_zip_meta(zip_path)
                    name = meta.get("name", f)
                    self.quickSwitchCard.comboBox.addItem(name, userData=zip_path)

    def _on_open_config_folder(self):
        import os
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        configs_dir = self.config_manager.configs_dir
        if not os.path.exists(configs_dir):
            os.makedirs(configs_dir, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(configs_dir))

    def _set_windows_auto_start(self, enable: bool):
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "CS2Toolkit"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                # 判断是否为打包后的独立可执行文件
                if getattr(sys, 'frozen', False):
                    exe_path = sys.executable
                else:
                    # 如果在开发环境，使用 main.py
                    main_py = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "main.py"))
                    exe_path = f'"{sys.executable}" "{main_py}"'

                # 如果只是字符串，加上引号防止路径包含空格
                if not exe_path.startswith('"'):
                    exe_path = f'"{exe_path}"'

                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"设置开机自启失败: {e}")
