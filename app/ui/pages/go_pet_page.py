import os
from ...logic.image_loader import MEDIA_FILTER

from PySide6.QtCore import QByteArray, QEvent, QMimeData, QPoint, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QApplication, QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    ComboBox,
    FluentIcon as FIF,
    InfoBar,
    LineEdit,
    MessageBoxBase,
    PrimaryPushButton,
    PushButton,
    ScrollArea,
    SettingCard,
    SettingCardGroup,
    SimpleCardWidget,
    Slider,
    SpinBox,
    SubtitleLabel,
    SwitchButton,
    SwitchSettingCard,
    isDarkTheme,
)

from app.ui.styles import UIStyles


PET_EVENT_OPTIONS = [
    ("normal", "满血，状态正常"),
    ("low_health", "血量低于指定值"),
    ("flashed", "被闪白"),
    ("kill", "击杀"),
    ("death", "被击杀"),
    ("bomb", "炸弹安放"),
    ("rich", "经济高于指定值"),
    ("poor", "经济低于指定值"),
    ("win", "回合胜利"),
    ("loss", "回合失败"),
    ("mvp", "回合MVP"),
    ("freeze", "Freeze Time"),
]

PET_EVENT_NAME_MAP = dict(PET_EVENT_OPTIONS)
DISPLAY_MODE_OPTIONS = [
    ("game", "游戏内显示"),
    ("capture", "主播输出窗口"),
]


class DisplayModeSettingCard(SettingCard):
    def __init__(self, icon, title, content=None, texts=None, parent=None):
        super().__init__(icon, title, content, parent)
        self.comboBox = ComboBox(self)
        if texts:
            self.comboBox.addItems(texts)
        self.hBoxLayout.addWidget(self.comboBox, 0, Qt.AlignmentFlag.AlignRight)
        self.hBoxLayout.addSpacing(16)


class PetEventListContainer(QWidget):
    MIME_TYPE = "application/x-go-pet-event"

    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page = page
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(self.MIME_TYPE):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        source = event.source()
        if not isinstance(source, PetEventConfigWidget):
            event.ignore()
            return

        target_index = self._get_drop_index(event.position().toPoint())
        self.page.move_event_widget(source, target_index)
        event.acceptProposedAction()

    def _get_drop_index(self, pos: QPoint):
        for index, widget in enumerate(self.page.event_widgets):
            if pos.y() < widget.geometry().center().y():
                return index
        return len(self.page.event_widgets)

class GoPetPage(ScrollArea):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent=parent)
        self.config_manager = config_manager
        self.parent_window = parent

        self.view = QWidget(self)
        self.view.setObjectName("view")
        self.layout = QVBoxLayout(self.view)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(8)
        self.layout.setAlignment(Qt.AlignTop)
        self.event_widgets = []

        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setObjectName("goPetPage")
        self.setStyleSheet("QScrollArea {background: transparent; border: none;} #view {background: transparent;}")

        self._init_config()
        self._setup_ui()

    def _init_config(self):
        self.pet_config = self.config_manager.get('go_pet', {
            'enabled': False,
            'display_mode': 'game',
            'size': 200,
            'offset_x': 50,
            'offset_y': 50,
            'events': []
        })
        self.pet_config.setdefault('display_mode', 'game')
        removed_legacy_key = self.pet_config.pop('streamer_mode', None) is not None

        # Normalize old / damaged config so the UI can always render correctly.
        events = self.pet_config.get('events', [])
        if not isinstance(events, list):
            self.pet_config['events'] = []
            self._save_config()
        else:
            cleaned_events = []
            for e in events:
                if not isinstance(e, dict):
                    continue
                event_type = e.get('type')
                if not event_type:
                    continue
                normalized = dict(e)
                normalized['type_name'] = normalized.get('type_name') or PET_EVENT_NAME_MAP.get(event_type, 'Unknown')
                cleaned_events.append(normalized)
            if len(cleaned_events) != len(events):
                self.pet_config['events'] = cleaned_events
                self._save_config()
        if removed_legacy_key:
            self._save_config()

    def reload_from_config(self):
        self._init_config()
        self.enable_card.switchButton.blockSignals(True)
        self.enable_card.switchButton.setChecked(self.pet_config.get('enabled', False))
        self.enable_card.switchButton.blockSignals(False)
        display_mode = self.pet_config.get('display_mode', 'game')
        display_index = 0 if display_mode == 'game' else 1
        self.display_mode_card.comboBox.blockSignals(True)
        self.display_mode_card.comboBox.setCurrentIndex(display_index)
        self.display_mode_card.comboBox.blockSignals(False)
        self.size_slider.blockSignals(True)
        self.size_slider.setValue(self.pet_config.get('size', 200))
        self.size_slider.blockSignals(False)
        self.size_label.setText(f"{self.pet_config.get('size', 200)} px")
        self._sync_display_mode_ui()
        self.load_events()

    def _save_config(self):
        self.config_manager.set('go_pet', self.pet_config)

    def _setup_ui(self):
        # 1. 基础设置
        self.basic_group = SettingCardGroup("基础设置", self.view)

        self.enable_card = SwitchSettingCard(
            icon=FIF.HEART,
            title="启用 GO 桌宠",
            content="在游戏上方显示一个动态互动的桌宠",
            configItem=None,
            parent=self.basic_group
        )
        self.enable_card.switchButton.setChecked(self.pet_config.get('enabled', False))
        self.enable_card.switchButton.checkedChanged.connect(self._on_enable_changed)
        self.basic_group.addSettingCard(self.enable_card)

        self.display_mode_card = DisplayModeSettingCard(
            icon=FIF.SEND,
            title="显示模式",
            content="选择在游戏内显示桌宠，或生成专门给 OBS 捕获的输出窗口",
            texts=[label for _, label in DISPLAY_MODE_OPTIONS],
            parent=self.basic_group
        )
        initial_display_mode = self.pet_config.get('display_mode', 'game')
        self.display_mode_card.comboBox.setCurrentIndex(0 if initial_display_mode == "game" else 1)
        self.display_mode_card.comboBox.currentIndexChanged.connect(self._on_display_mode_changed)
        self.basic_group.addSettingCard(self.display_mode_card)

        self.layout.addWidget(self.basic_group)

        # 2. 外观设置
        self.appearance_group = SettingCardGroup("外观与位置", self.view)

        # Edit mode
        self.edit_mode_card = SettingCard(
            icon=FIF.EDIT,
            title="调节模式",
            content="开启后可以直接在屏幕上拖拽桌宠位置",
            parent=self.appearance_group
        )
        self.edit_switch = SwitchButton("关", self.edit_mode_card)
        self.edit_switch.setOnText("开")
        self.edit_switch.setOffText("关")
        self.edit_switch.checkedChanged.connect(self._on_edit_mode_changed)
        self.edit_mode_card.hBoxLayout.addWidget(self.edit_switch, 0, Qt.AlignmentFlag.AlignRight)
        self.edit_mode_card.hBoxLayout.addSpacing(16)
        self.appearance_group.addSettingCard(self.edit_mode_card)

        # Size
        self.size_card = SettingCard(
            icon=FIF.ZOOM_IN,
            title="桌宠大小",
            content="调节桌宠在屏幕上的显示大小",
            parent=self.appearance_group
        )
        size_layout = QHBoxLayout()
        self.size_slider = Slider(Qt.Horizontal, self.size_card)
        self.size_slider.setRange(50, 800)
        self.size_slider.setValue(self.pet_config.get('size', 200))
        self.size_label = BodyLabel(f"{self.size_slider.value()} px")
        self.size_slider.valueChanged.connect(self._on_size_changed)

        size_layout.addWidget(self.size_slider, 1)
        size_layout.addWidget(self.size_label)
        self.size_card.hBoxLayout.addLayout(size_layout)
        self.size_card.hBoxLayout.addSpacing(16)
        self.appearance_group.addSettingCard(self.size_card)

        self.layout.addWidget(self.appearance_group)
        self._sync_display_mode_ui()

        # 3. 事件配置
        self.event_section_title = SubtitleLabel("互动事件配置", self.view)
        self.layout.addWidget(self.event_section_title)

        self.event_card = SimpleCardWidget(self.view)
        self.event_card.setObjectName("actionCard")
        UIStyles.apply_styles(self.event_card)
        event_layout = QVBoxLayout(self.event_card)
        event_layout.setContentsMargins(16, 16, 16, 16)
        event_layout.setSpacing(10)

        event_layout.addWidget(BodyLabel("配置事件触发条件与互动效果"))

        self.event_cards_container = PetEventListContainer(self, self.event_card)
        self.event_cards_container.setObjectName("customPanel")
        self.event_cards_layout = QVBoxLayout(self.event_cards_container)
        self.event_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.event_cards_layout.setSpacing(10)
        event_layout.addWidget(self.event_cards_container)

        self.empty_label = CaptionLabel("暂无桌宠事件，点击“添加新事件”开始配置")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setContentsMargins(0, 8, 0, 8)
        event_layout.addWidget(self.empty_label)

        btn_layout = QHBoxLayout()
        self.save_events_btn = PushButton("保存事件")
        self.add_event_btn = PrimaryPushButton("添加新事件")
        self.save_events_btn.clicked.connect(self.save_events)
        self.add_event_btn.clicked.connect(self.show_add_event_dialog)

        btn_layout.addStretch()
        btn_layout.addWidget(self.save_events_btn)
        btn_layout.addWidget(self.add_event_btn)
        event_layout.addLayout(btn_layout)

        self.layout.addWidget(self.event_card)
        self._apply_event_theme_styles()

        self.load_events()

    def _on_enable_changed(self, is_checked):
        self.pet_config['enabled'] = is_checked
        self._save_config()
        if hasattr(self.parent_window, 'go_pet_manager'):
            self.parent_window.go_pet_manager.set_enabled(is_checked)
        if hasattr(self.parent_window, 'update_home_status'):
            self.parent_window.update_home_status()

    def _on_display_mode_changed(self, index):
        self.pet_config['display_mode'] = DISPLAY_MODE_OPTIONS[index][0]
        self._save_config()
        self._sync_display_mode_ui()
        if hasattr(self.parent_window, 'go_pet_manager'):
            self.parent_window.go_pet_manager._update_config()
        if hasattr(self.parent_window, 'update_home_status'):
            self.parent_window.update_home_status()

    def _sync_display_mode_ui(self):
        display_mode = self.pet_config.get('display_mode', 'game')
        is_capture_mode = display_mode == 'capture'
        self.edit_mode_card.setDisabled(is_capture_mode)
        self.edit_switch.setChecked(False if is_capture_mode else self.edit_switch.isChecked())
        self.edit_switch.setEnabled(not is_capture_mode)

    def _on_edit_mode_changed(self, is_checked):
        if hasattr(self.parent_window, 'go_pet_manager'):
            self.parent_window.go_pet_manager.overlay.set_edit_mode(is_checked)
            # Fetch updated pos when turned off
            if not is_checked:
                self.pet_config['offset_x'] = self.parent_window.go_pet_manager.overlay.offset_x
                self.pet_config['offset_y'] = self.parent_window.go_pet_manager.overlay.offset_y
                self._save_config()

    def _on_size_changed(self, value):
        self.size_label.setText(f"{value} px")
        self.pet_config['size'] = value
        self._save_config()
        if hasattr(self.parent_window, 'go_pet_manager'):
            self.parent_window.go_pet_manager.overlay.set_size(value)

    def _clear_event_widgets(self):
        while self.event_cards_layout.count():
            item = self.event_cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.event_widgets = []

    def _update_empty_state(self):
        self.empty_label.setVisible(len(self.event_widgets) == 0)

    def load_events(self):
        self._clear_event_widgets()
        events = self.pet_config.get('events', [])
        for event_config in events:
            self.add_new_event_widget(event_config)
        self._update_empty_state()

    def add_new_event_widget(self, config):
        widget = PetEventConfigWidget(config, self.delete_event_widget)
        self.event_widgets.append(widget)
        self.event_cards_layout.addWidget(widget)
        widget.apply_theme_style()
        self._update_empty_state()

    def delete_event_widget(self, widget):
        if widget in self.event_widgets:
            self.event_widgets.remove(widget)
        self.event_cards_layout.removeWidget(widget)
        widget.deleteLater()
        self._update_empty_state()
        self.save_events()

    def move_event_widget(self, widget, target_index):
        if widget not in self.event_widgets:
            return

        source_index = self.event_widgets.index(widget)
        if target_index > source_index:
            target_index -= 1
        target_index = max(0, min(target_index, len(self.event_widgets) - 1))

        if target_index == source_index:
            return

        self.event_widgets.pop(source_index)
        self.event_widgets.insert(target_index, widget)
        self.event_cards_layout.removeWidget(widget)
        self.event_cards_layout.insertWidget(target_index, widget)
        self.save_events()

    def save_events(self):
        events = [widget.get_config() for widget in self.event_widgets]
        self.pet_config['events'] = events
        self._save_config()

        if hasattr(self.parent_window, 'go_pet_manager'):
            self.parent_window.go_pet_manager._update_config()

        InfoBar.success("保存成功", "桌宠事件配置已保存", parent=self)

    def show_add_event_dialog(self):
        dialog = PetEventDialog(self)
        if dialog.exec():
            config = dialog.get_config()
            if config:
                self.add_new_event_widget(config)
                self.save_events()

    def _apply_event_theme_styles(self):
        if not hasattr(self, "event_card"):
            return

        dark = isDarkTheme()
        if dark:
            border = "rgba(255, 255, 255, 0.08)"
            bg = "rgba(255, 255, 255, 0.043)"
            hover_bg = "rgba(255, 255, 255, 0.08)"
            hover_border = "rgba(0, 120, 212, 0.6)"
        else:
            border = "rgba(0, 0, 0, 0.08)"
            bg = "rgba(255, 255, 255, 0.6)"
            hover_bg = "rgba(255, 255, 255, 0.9)"
            hover_border = "rgba(0, 120, 212, 0.4)"

        self.event_card.setStyleSheet(f"""
            SimpleCardWidget#actionCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            SimpleCardWidget#actionCard:hover {{
                background-color: {hover_bg};
                border: 1px solid {hover_border};
            }}
        """)
        self.event_cards_container.setStyleSheet("QWidget#customPanel { background-color: transparent; }")
        for widget in self.event_widgets:
            widget.apply_theme_style()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.PaletteChange, QEvent.ThemeChange, QEvent.ApplicationPaletteChange, QEvent.StyleChange):
            self._apply_event_theme_styles()

class PetEventDialog(MessageBoxBase):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.titleLabel = SubtitleLabel('添加桌宠事件', self)
        self.viewLayout.addWidget(self.titleLabel)

        self.image_path = ""
        self.sound_path = ""
        self._setup_ui()
        self._on_event_type_changed(0)

        self.widget.setMinimumWidth(560)
        self.yesButton.setText('确定')
        self.cancelButton.setText('取消')

    def _setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.event_combo = ComboBox()
        self.event_types = PET_EVENT_OPTIONS
        self.event_combo.addItems([t[1] for t in self.event_types])
        self.event_combo.currentIndexChanged.connect(self._on_event_type_changed)
        layout.addWidget(BodyLabel("触发条件"))
        layout.addWidget(self.event_combo)

        self.threshold_container = QWidget()
        self.threshold_layout = QHBoxLayout(self.threshold_container)
        self.threshold_layout.setContentsMargins(0, 0, 0, 0)
        self.threshold_layout.setSpacing(8)
        self.threshold_title = BodyLabel("阈值")
        self.threshold_spin = SpinBox()
        self.threshold_spin.setRange(0, 16000)
        self.threshold_layout.addWidget(self.threshold_title)
        self.threshold_layout.addWidget(self.threshold_spin)
        self.threshold_layout.addStretch()
        self.threshold_container.hide()
        layout.addWidget(self.threshold_container)

        self.image_mode_combo = ComboBox()
        self.image_mode_combo.addItems(["单张图片", "文件夹随机"])
        layout.addWidget(BodyLabel("立绘来源"))
        layout.addWidget(self.image_mode_combo)

        img_layout = QHBoxLayout()
        self.img_input = LineEdit()
        self.img_input.setPlaceholderText("选择图片或图片文件夹")
        self.img_input.setReadOnly(True)
        self.img_btn = PushButton("浏览立绘")
        self.img_btn.clicked.connect(self._browse_image)
        img_layout.addWidget(self.img_input)
        img_layout.addWidget(self.img_btn)
        layout.addWidget(BodyLabel("显示立绘"))
        layout.addLayout(img_layout)

        self.sound_mode_combo = ComboBox()
        self.sound_mode_combo.addItems(["单个音频", "文件夹随机"])
        layout.addWidget(BodyLabel("音效来源"))
        layout.addWidget(self.sound_mode_combo)

        snd_layout = QHBoxLayout()
        self.snd_input = LineEdit()
        self.snd_input.setPlaceholderText("选择音频或音频文件夹")
        self.snd_input.setReadOnly(True)
        self.snd_btn = PushButton("浏览音效")
        self.snd_btn.clicked.connect(self._browse_sound)
        snd_layout.addWidget(self.snd_input)
        snd_layout.addWidget(self.snd_btn)
        layout.addWidget(BodyLabel("播放音效"))
        layout.addLayout(snd_layout)

        self.viewLayout.addLayout(layout)

    def _on_event_type_changed(self, index):
        event_type = self.event_types[index][0]
        if event_type == "low_health":
            self.threshold_title.setText("血量低于")
            self.threshold_spin.setRange(1, 100)
            self.threshold_spin.setValue(30)
            self.threshold_container.show()
        elif event_type == "rich":
            self.threshold_title.setText("经济高于")
            self.threshold_spin.setRange(0, 16000)
            self.threshold_spin.setValue(10000)
            self.threshold_container.show()
        elif event_type == "poor":
            self.threshold_title.setText("经济低于")
            self.threshold_spin.setRange(0, 16000)
            self.threshold_spin.setValue(2000)
            self.threshold_container.show()
        else:
            self.threshold_container.hide()

    def _browse_image(self):
        if self.image_mode_combo.currentIndex() == 0:
            path, _ = QFileDialog.getOpenFileName(self, "选择立绘", "", MEDIA_FILTER)
        else:
            path = QFileDialog.getExistingDirectory(self, "选择立绘文件夹")

        if path:
            self.image_path = path
            self.img_input.setText(os.path.basename(path))

    def _browse_sound(self):
        if self.sound_mode_combo.currentIndex() == 0:
            path, _ = QFileDialog.getOpenFileName(self, "选择音效", "", "音频 (*.mp3 *.wav)")
        else:
            path = QFileDialog.getExistingDirectory(self, "选择音效文件夹")

        if path:
            self.sound_path = path
            self.snd_input.setText(os.path.basename(path))

    def get_config(self):
        idx = self.event_combo.currentIndex()
        event_type = self.event_types[idx][0]
        config = {
            "type": event_type,
            "type_name": self.event_types[idx][1],
            "image": self.image_path,
            "sound": self.sound_path
        }
        if event_type in ["low_health", "rich", "poor"]:
            config["threshold"] = self.threshold_spin.value()
        return config

class PetEventConfigWidget(SimpleCardWidget):
    def __init__(self, config, on_delete):
        super().__init__()
        self.config = config
        self.on_delete = on_delete
        self.setObjectName("actionCard")
        UIStyles.apply_styles(self)
        self.setMinimumHeight(92)
        self._drag_start_pos = QPoint()
        self.setCursor(Qt.OpenHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)

        if isinstance(config, dict):
            event_type = config.get('type')
            type_name = config.get('type_name') or PET_EVENT_NAME_MAP.get(event_type, 'Unknown')
            image_path = config.get('image', '')
            sound_path = config.get('sound', '')
            threshold = config.get('threshold')

            if threshold is not None:
                type_name += f" ({threshold})"
        else:
            type_name = 'Unknown'
            image_path = ''
            sound_path = ''

        title_label = BodyLabel(f"条件: {type_name}")
        title_label.setWordWrap(True)
        self.title_label = title_label
        info_layout.addWidget(self.title_label)

        img_text = os.path.basename(image_path) if image_path else "无"
        snd_text = os.path.basename(sound_path) if sound_path else "无"

        self.details_label = CaptionLabel(f"立绘: {img_text} | 音效: {snd_text}")
        self.details_label.setWordWrap(True)
        info_layout.addWidget(self.details_label)

        layout.addLayout(info_layout)
        layout.addStretch()

        del_btn = PushButton(FIF.DELETE, "删除")
        del_btn.clicked.connect(lambda: self.on_delete(self))
        layout.addWidget(del_btn)
        self.apply_theme_style()

    def get_config(self):
        return self.config

    def apply_theme_style(self):
        dark = isDarkTheme()
        if dark:
            border = "rgba(255, 255, 255, 0.08)"
            bg = "rgba(255, 255, 255, 0.043)"
            hover_bg = "rgba(255, 255, 255, 0.08)"
            hover_border = "rgba(0, 120, 212, 0.6)"
            detail_color = "rgba(255, 255, 255, 0.78)"
        else:
            border = "rgba(0, 0, 0, 0.08)"
            bg = "rgba(255, 255, 255, 0.6)"
            hover_bg = "rgba(255, 255, 255, 0.9)"
            hover_border = "rgba(0, 120, 212, 0.4)"
            detail_color = "rgba(0, 0, 0, 0.65)"

        self.setStyleSheet(f"""
            SimpleCardWidget#actionCard {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            SimpleCardWidget#actionCard:hover {{
                background-color: {hover_bg};
                border: 1px solid {hover_border};
            }}
        """)
        self.details_label.setStyleSheet(f"color: {detail_color};")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton):
            super().mouseMoveEvent(event)
            return

        if (event.position().toPoint() - self._drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(PetEventListContainer.MIME_TYPE, QByteArray(b"move"))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(event.position().toPoint())
        drag.exec(Qt.MoveAction)
        self.setCursor(Qt.OpenHandCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)
