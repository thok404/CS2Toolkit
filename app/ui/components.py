import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QIcon
from qfluentwidgets import StrongBodyLabel, BodyLabel, PushButton


class ActionCard(QWidget):
    def __init__(self, icon, title, description, callback, parent=None):
        super().__init__(parent)
        self.callback = callback
        self.setObjectName("actionCard")
        self.setFixedSize(180, 120)
        self.setCursor(Qt.PointingHandCursor)
        
        self.mousePressEvent = self._mouse_press_event
        self._setup_ui(icon, title, description)
        
        # Apply custom style defined in styles.py
        from app.ui.styles import UIStyles
        UIStyles.apply_styles(self)
    
    def _mouse_press_event(self, event):
        if event.button() == Qt.LeftButton:
            self.callback()
    
    def _setup_ui(self, icon, title, description):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        from qfluentwidgets import FluentIconBase, IconWidget
        icon_label = QLabel()
        if isinstance(icon, QIcon):
            pixmap = icon.pixmap(32, 32)
            icon_label.setPixmap(pixmap)
        elif isinstance(icon, FluentIconBase):
            icon_widget = IconWidget(icon)
            icon_widget.setFixedSize(32, 32)
            layout.addWidget(icon_widget, 0, Qt.AlignCenter)
            icon_label = None # 不再需要添加普通的 icon_label
        else:
            icon_label.setText(icon)
            
        if icon_label:
            icon_label.setStyleSheet("font-size: 32px;")
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)
        
        title_label = StrongBodyLabel(title)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("")
        layout.addWidget(title_label)
        
        desc_label = BodyLabel(description)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #666;")
        layout.addWidget(desc_label)


class VideoPresetWidget(QWidget):
    def __init__(self, preset, apply_callback, parent=None):
        super().__init__(parent)
        self.preset = preset
        self._setup_ui(apply_callback)
    
    def _setup_ui(self, apply_callback):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        thumbnail = QLabel()
        pixmap = QPixmap(self.preset["thumbnail_path"])
        if not pixmap.isNull():
            thumbnail.setPixmap(pixmap.scaled(64, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(thumbnail)

        layout.addWidget(BodyLabel(self.preset["name"]), 1)

        apply_btn = PushButton("应用")
        apply_btn.clicked.connect(lambda: apply_callback(self.preset))
        layout.addWidget(apply_btn)


class FontPresetWidget(QWidget):
    def __init__(self, preset, apply_callback, parent=None):
        super().__init__(parent)
        self.preset = preset
        self._setup_ui(apply_callback)
    
    def _setup_ui(self, apply_callback):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        info_layout = QVBoxLayout()
        info_layout.addWidget(StrongBodyLabel(self.preset["name"]))
        info_layout.addWidget(BodyLabel(f"字体: {self.preset['font_name']}"))
        layout.addLayout(info_layout, 1)

        apply_btn = PushButton("应用")
        apply_btn.clicked.connect(lambda: apply_callback(self.preset))
        layout.addWidget(apply_btn)


class SoundPresetWidget(QWidget):
    def __init__(self, preset, apply_callback, parent=None):
        super().__init__(parent)
        self.preset = preset
        self._setup_ui(apply_callback)
    
    def _setup_ui(self, apply_callback):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        info_layout = QVBoxLayout()
        info_layout.addWidget(StrongBodyLabel(self.preset["name"]))
        info_layout.addWidget(BodyLabel(f"音效: {self.preset['sound_name']}"))
        layout.addLayout(info_layout, 1)

        apply_btn = PushButton("应用")
        apply_btn.clicked.connect(lambda: apply_callback(self.preset))
        layout.addWidget(apply_btn)

from PySide6.QtWidgets import QWidget, QHBoxLayout, QFileDialog, QDialog, QCompleter
from PySide6.QtCore import Qt
from qfluentwidgets import LineEdit, ComboBox, PushButton, FluentIcon, BodyLabel, ToolButton, Slider, EditableComboBox

class EventConfigWidget(QWidget):
    # 用于配置单个GSI事件规则的自定义小部件
    def __init__(self, parent=None, on_delete=None, on_change=None, on_edit=None):
        super().__init__(parent)
        self.on_delete = on_delete
        self.on_change = on_change
        self.on_edit = on_edit
        self.sound_path = ""
        self.is_advanced = False
        self.sounds_1_5 = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.weapon_name_input = EditableComboBox()
        self.weapon_name_input.setPlaceholderText("选择或输入武器名称")

        weapon_names_cn = [
            "所有枪械",
            "AK-47", "M4A4", "M4A1-S消音版", "AWP",
            "沙漠之鹰", "R8 左轮", "格洛克18", "USP消音版", "P250",
            "FN57", "Tec-9", "CZ75-Auto", "P2000",
            "双持贝瑞塔", "P90", "PP-Bizon", "MAC-10",
            "MP7", "MP9", "MP5-SD", "UMP-45", "XM1014",
            "短管霰弹枪", "新星", "MAG-7", "内格夫",
            "M249", "加利尔AR", "法玛斯", "SG 553",
            "AUG", "SCAR-20", "G3SG1", "SSG 08",
            "电击枪 (Zeus x27)", "CT默认刀", "T默认刀", "刺刀", "海豹短刀", "折叠刀",
            "穿肠刀", "爪子刀", "M9刺刀", "猎杀者匕首", "弯刀",
            "鲍伊猎刀", "蝴蝶刀", "暗影双匕", "系绳匕首", "求生匕首",
            "熊刀", "折刀", "流浪者匕首", "短剑", "锯齿爪刀",
            "骷髅匕首", "廓尔喀刀"
        ]
        
        grenade_names_cn = [
            "所有道具", "闪光弹", "烟雾弹", "高爆手雷", "燃烧弹/燃烧瓶", "诱饵弹"
        ]

        weapon_names_en = [
            "all_weapons",
            "weapon_ak47", "weapon_m4a1", "weapon_m4a1_silencer", "weapon_awp",
            "weapon_deagle", "weapon_revolver", "weapon_glock", "weapon_usp_silencer", "weapon_p250",
            "weapon_fiveseven", "weapon_tec9", "weapon_cz75a", "weapon_p2000",
            "weapon_elite", "weapon_p90", "weapon_bizon", "weapon_mac10",
            "weapon_mp7", "weapon_mp9", "weapon_mp5sd", "weapon_ump45", "weapon_xm1014",
            "weapon_sawedoff", "weapon_nova", "weapon_mag7", "weapon_negev",
            "weapon_m249", "weapon_galilar", "weapon_famas", "weapon_sg556",
            "weapon_aug", "weapon_scar20", "weapon_g3sg1", "weapon_ssg08",
            "weapon_taser", "weapon_knife", "weapon_knife_t", "weapon_bayonet", "weapon_knife_css", "weapon_knife_flip",
            "weapon_knife_gut", "weapon_knife_karambit", "weapon_knife_m9_bayonet", "weapon_knife_huntsman", "weapon_knife_falchion",
            "weapon_knife_survival_bowie", "weapon_knife_butterfly", "weapon_knife_push", "weapon_knife_cord", "weapon_knife_tactical",
            "weapon_knife_ursus", "weapon_knife_gypsy_jackknife", "weapon_knife_nomad", "weapon_knife_stiletto", "weapon_knife_widowmaker",
            "weapon_knife_skeleton", "weapon_knife_kukri"
        ]
        
        grenade_names_en = [
            "all_grenades", "weapon_flashbang", "weapon_smokegrenade", "weapon_hegrenade", "weapon_molotov", "weapon_decoy"
        ]
        
        # 创建中英文映射字典
        self.weapon_cn_to_en = dict(zip(weapon_names_cn, weapon_names_en))
        self.weapon_en_to_cn = dict(zip(weapon_names_en, weapon_names_cn))
        self.weapon_cn_to_en.update(dict(zip(grenade_names_cn, grenade_names_en)))
        self.weapon_en_to_cn.update(dict(zip(grenade_names_en, grenade_names_cn)))
        
        # 组合所有的中文名称供下拉框使用
        all_cn_names = weapon_names_cn + grenade_names_cn
        self.weapon_name_input.addItems(all_cn_names)
        
        # 添加搜索/自动补全功能
        completer = QCompleter(all_cn_names, self)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.weapon_name_input.setCompleter(completer)
        
        self.event_type_combo = ComboBox()
        event_items = [
            "--- 全局音效 ---",
            "全局击杀",
            "C4安装", 
            "C4拆除",
            "玩家死亡",
            "--- 其他音效 ---",
            "切换到",
            "换弹", 
            "使用武器击杀",
            "道具投出"
        ]
        self.event_type_combo.addItems(event_items)
        self.event_type_combo.setCurrentIndex(1)  # 默认选择"全局击杀"
        self.event_type_combo.currentIndexChanged.connect(self._on_event_type_changed)
        
        # 音效选择
        self.sound_path_label = PushButton("选择音效文件")
        self.sound_path_label.clicked.connect(self.select_sound_file)
        
        # 音量控制
        self.volume_slider = Slider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)  # 默认音量50%
        self.volume_slider.setFixedWidth(80)
        self.volume_slider.setToolTip("音量: 50%")
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        
        self.volume_label = BodyLabel("50%")
        self.volume_label.setFixedWidth(30)

        self.delete_btn = ToolButton(FluentIcon.DELETE)
        self.delete_btn.clicked.connect(self._handle_delete)
        
        self.edit_btn = ToolButton(FluentIcon.EDIT)
        self.edit_btn.clicked.connect(self._handle_edit)

        self.test_btn = ToolButton(FluentIcon.PLAY)
        self.test_btn.clicked.connect(self._handle_test)

        self.when_label = BodyLabel("当")
        layout.addWidget(self.when_label)
        layout.addWidget(self.weapon_name_input, 1)
        layout.addWidget(self.event_type_combo)
        layout.addWidget(BodyLabel("时，播放"))
        layout.addWidget(self.sound_path_label, 1)
        layout.addWidget(BodyLabel("音量:"))
        layout.addWidget(self.volume_slider)
        layout.addWidget(self.volume_label)
        layout.addWidget(self.test_btn)
        layout.addWidget(self.edit_btn)
        layout.addWidget(self.delete_btn)

        # 列表内直接修改武器时同步到运行中的事件配置（构造完成后再连接，避免初始化时触发保存）
        self.weapon_name_input.currentTextChanged.connect(self._notify_change)

    def _notify_change(self, *_):
        if self.on_change:
            self.on_change()

    def set_on_change(self, callback):
        # 设置配置改变时的回调函数
        self.on_change = callback

    def select_sound_file(self):
        # 选择音效文件
        path, _ = QFileDialog.getOpenFileName(self, "选择音效文件", "", "音效文件 (*.mp3 *.wav)")
        if path:
            self.sound_path_label.setText(os.path.basename(path))
            self.sound_path = path
            if self.on_change:
                self.on_change()
    
    def _on_volume_changed(self, value):
        # 当音量滑块值改变时更新显示，并同步到运行中的事件配置（否则游戏内音量不变）
        self.volume_label.setText(f"{value}%")
        self.volume_slider.setToolTip(f"音量: {value}%")
        self._notify_change()



    def _handle_delete(self):
        if self.on_delete:
            self.on_delete(self)

    def _handle_edit(self):
        if self.on_edit:
            self.on_edit(self)

    def _handle_test(self):
        if self.is_advanced:
            # 播放连杀1的音效
            if self.sounds_1_5 and len(self.sounds_1_5) > 0:
                s = self.sounds_1_5[0]
                if s and s.get("path"):
                    self._play_test_sound(s.get("path"), s.get("volume", 50))
        else:
            if self.sound_path:
                self._play_test_sound(self.sound_path, self.volume_slider.value())

    def _play_test_sound(self, path, volume):
        if not path or not os.path.exists(path): return
        if not hasattr(self, '_test_player'):
            from app.logic.sound_player import SoundPlayer
            self._test_player = SoundPlayer()
        self._test_player.play_sound(path, volume)
    
    def _on_event_type_changed(self, index):
        # 当事件类型改变时调用
        # 防止选择分类标题
        if index in [0, 5]:  # 分类标题索引
            # 如果选择了分类标题，跳转到下一个有效选项
            if index == 0:  # 全局音效分类
                # 阻止信号触发，避免递归调用
                self.event_type_combo.blockSignals(True)
                self.event_type_combo.setCurrentIndex(1)  # 跳转到"全局击杀"
                self.event_type_combo.blockSignals(False)
                # 手动调用更新逻辑
                index = 1
            elif index == 5:  # 其他音效分类
                # 阻止信号触发，避免递归调用
                self.event_type_combo.blockSignals(True)
                self.event_type_combo.setCurrentIndex(6)  # 跳转到"切换到"
                self.event_type_combo.blockSignals(False)
                # 手动调用更新逻辑
                index = 6
        
        if index in [1, 2, 3, 4]:  # 全局击杀、C4安装、C4拆除、玩家死亡（全局事件）
            # 对于全局事件，设置武器名称为固定值并隐藏
            self.weapon_name_input.setCurrentText("全局事件")
            self.when_label.hide()
            self.weapon_name_input.hide()
        elif index == 8:  # 使用武器击杀
            # 对于使用武器击杀事件，启用武器名称输入
            self.when_label.show()
            self.weapon_name_input.show()
            self.weapon_name_input.setEnabled(True)
            if self.weapon_name_input.currentText() == "全局事件":
                self.weapon_name_input.setCurrentText("")
        elif index == 9:  # 道具投出
            self.when_label.show()
            self.weapon_name_input.show()
            self.weapon_name_input.setEnabled(True)
            if self.weapon_name_input.currentText() == "全局事件":
                self.weapon_name_input.setCurrentText("所有道具")
        else:
            # 对于武器事件，启用武器名称输入
            self.when_label.show()
            self.weapon_name_input.show()
            self.weapon_name_input.setEnabled(True)
            if self.weapon_name_input.currentText() == "全局事件":
                self.weapon_name_input.setCurrentText("")
        
        # 触发变化回调，用于动态更新分类显示
        if self.on_change:
            self.on_change()

    def _update_ui_state_for_event_type(self, index):
        # 更新UI状态但不触发回调（用于set_config）
        # 防止选择分类标题
        if index in [0, 5]:  # 分类标题索引
            # 如果选择了分类标题，跳转到下一个有效选项
            if index == 0:  # 全局音效分类
                # 阻止信号触发，避免递归调用
                self.event_type_combo.blockSignals(True)
                self.event_type_combo.setCurrentIndex(1)  # 跳转到"全局击杀"
                self.event_type_combo.blockSignals(False)
                index = 1
            elif index == 5:  # 其他音效分类
                # 阻止信号触发，避免递归调用
                self.event_type_combo.blockSignals(True)
                self.event_type_combo.setCurrentIndex(6)  # 跳转到"切换到"
                self.event_type_combo.blockSignals(False)
                index = 6
        
        if index in [1, 2, 3, 4]:  # 全局击杀、C4安装、C4拆除、玩家死亡（全局事件）
            # 对于全局事件，设置武器名称为固定值并隐藏
            self.weapon_name_input.setCurrentText("全局事件")
            self.when_label.hide()
            self.weapon_name_input.hide()
        elif index == 8:  # 使用武器击杀
            # 对于使用武器击杀事件，显示武器名称输入
            self.when_label.show()
            self.weapon_name_input.show()
            self.weapon_name_input.setEnabled(True)
            if self.weapon_name_input.currentText() == "全局事件":
                self.weapon_name_input.setCurrentText("")
        elif index == 9:  # 道具投出
            self.when_label.show()
            self.weapon_name_input.show()
            self.weapon_name_input.setEnabled(True)
            if self.weapon_name_input.currentText() == "全局事件":
                self.weapon_name_input.setCurrentText("所有道具")
        else:
            # 对于武器事件，显示武器名称输入
            self.when_label.show()
            self.weapon_name_input.show()
            self.weapon_name_input.setEnabled(True)
            if self.weapon_name_input.currentText() == "全局事件":
                self.weapon_name_input.setCurrentText("")

    def get_config(self):
        # 返回此小部件的配置字典
        # 从ComboBox获取当前文本（可能是选中的项目或用户输入的文本）
        weapon_name_cn = self.weapon_name_input.currentText().strip()
        # 将中文武器名称转换为英文（用于配置保存）
        weapon_name = self.weapon_cn_to_en.get(weapon_name_cn, weapon_name_cn)
        event_index = self.event_type_combo.currentIndex()
        # 修正事件类型索引映射，对应下拉框的实际索引
        event_mapping = {
            1: "kill",           # 全局击杀
            2: "bomb_planted",   # C4安装
            3: "bomb_defused",   # C4拆除
            4: "player_death",   # 玩家死亡
            6: "active",         # 切换到
            7: "reloading",      # 换弹
            8: "weapon_kill",    # 使用武器击杀
            9: "grenade_thrown"  # 道具投出
        }
        
        # 强制为全局事件设置武器名称，防止意外覆盖
        if event_index in [1, 2, 3, 4]:
            weapon_name = "全局事件"
            
        config = {
            "weapon": weapon_name,
            "event": event_mapping.get(event_index, "active"),
            "sound": getattr(self, 'sound_path', ''),
            "volume": self.volume_slider.value(),
            "is_advanced": self.is_advanced
        }
        
        if self.is_advanced:
            config["sounds_1_5"] = self.sounds_1_5
        
        return config

    def set_config(self, config):
        # 设置此小部件的配置
        # 临时禁用回调，避免在设置配置时触发保存
        original_callback = self.on_change
        self.on_change = None
        
        try:
            weapon_name = config.get("weapon", "")
            if weapon_name:
                # 将英文武器名称转换为中文显示
                weapon_name_cn = self.weapon_en_to_cn.get(weapon_name, weapon_name)
                # 查找是否在下拉列表中存在该武器名称
                index = self.weapon_name_input.findText(weapon_name_cn)
                if index >= 0:
                    self.weapon_name_input.setCurrentIndex(index)
                else:
                    # 如果不存在，设置为可编辑文本
                    self.weapon_name_input.setCurrentText(weapon_name_cn)
            
            event_type = config.get("event", "active")
            event_index_mapping = {
                "kill": 1,           # 全局击杀
                "bomb_planted": 2,   # C4安装
                "bomb_defused": 3,   # C4拆除
                "player_death": 4,   # 玩家死亡
                "active": 6,         # 切换到
                "reloading": 7,      # 换弹
                "weapon_kill": 8,    # 使用武器击杀
                "grenade_thrown": 9  # 道具投出
            }
            event_index = event_index_mapping.get(event_type, 1)  # 默认选择"全局击杀"
            # 阻止信号触发，避免在设置配置时触发_on_event_type_changed
            self.event_type_combo.blockSignals(True)
            self.event_type_combo.setCurrentIndex(event_index)
            self.event_type_combo.blockSignals(False)
            
            # 手动处理UI状态更新，不触发回调
            self._update_ui_state_for_event_type(event_index)
            
            self.is_advanced = config.get("is_advanced", False)
            self.sounds_1_5 = config.get("sounds_1_5", [])
            
            if self.is_advanced:
                self.sound_path_label.setText("高阶配置 (点击右侧编辑)")
                self.sound_path_label.setEnabled(False)
                self.volume_slider.setEnabled(False)
            else:
                self.sound_path_label.setEnabled(True)
                self.volume_slider.setEnabled(True)
                # 设置音效文件
                sound_path = config.get("sound", "")
                if sound_path:
                    self.sound_path = sound_path
                    self.sound_path_label.setText(os.path.basename(sound_path))
                
                # 设置音量
                volume = config.get("volume", 50)
                self.volume_slider.setValue(volume)
                self._on_volume_changed(volume)
        finally:
            # 恢复回调
            self.on_change = original_callback
