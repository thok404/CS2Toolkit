from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QMenu
from PySide6.QtCore import Qt
from qfluentwidgets import (SubtitleLabel, TitleLabel, BodyLabel, LineEdit, PushButton, 
                           ListWidget, PrimaryPushButton, SimpleCardWidget)
from ..styles import UIStyles


class FontPage(QWidget):
    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(15)

        layout.addWidget(TitleLabel("游戏字体替换"))
        layout.addSpacing(10)

        # 字体文件选择 (Card)
        file_card = SimpleCardWidget(self)
        UIStyles.apply_styles(file_card)
        file_layout = QVBoxLayout(file_card)
        file_layout.setContentsMargins(20, 20, 20, 20)
        file_layout.setSpacing(10)

        file_layout.addWidget(SubtitleLabel("选择字体文件 (TTF格式)"))
        self.font_entry = LineEdit()
        self.font_entry.setPlaceholderText("选择一个ttf格式的字体文件")
        self.browse_font_btn = PushButton("选择字体文件")
        font_file_layout = QHBoxLayout()
        font_file_layout.addWidget(self.font_entry)
        font_file_layout.addWidget(self.browse_font_btn)
        file_layout.addLayout(font_file_layout)

        self.font_name_label = BodyLabel("字体名称: 未选择")
        self.font_name_label.setStyleSheet("color: #666666;")
        self.font_filename_label = BodyLabel("文件名: 未选择")
        self.font_filename_label.setStyleSheet("color: #666666;")
        file_layout.addWidget(self.font_name_label)
        file_layout.addWidget(self.font_filename_label)

        self.execute_font_btn = PrimaryPushButton("替换字体")
        self.restore_font_btn = PushButton("恢复默认字体")
        action_layout = QHBoxLayout()
        action_layout.addWidget(self.execute_font_btn, 1)
        action_layout.addWidget(self.restore_font_btn)
        file_layout.addLayout(action_layout)
        layout.addWidget(file_card)

        # 字体预设 (Card)
        preset_card = SimpleCardWidget(self)
        UIStyles.apply_styles(preset_card)
        preset_layout = QVBoxLayout(preset_card)
        preset_layout.setContentsMargins(20, 20, 20, 20)
        preset_layout.setSpacing(10)

        preset_layout.addWidget(SubtitleLabel("字体预设"))
        self.font_preset_list = ListWidget()
        self.font_preset_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.font_preset_list.customContextMenuRequested.connect(self.show_font_preset_context_menu)
        preset_layout.addWidget(self.font_preset_list)
        
        self.save_font_preset_btn = PushButton("保存当前字体为预设")
        preset_layout.addWidget(self.save_font_preset_btn)
        layout.addWidget(preset_card)

        self._connect_signals()
    
    def _connect_signals(self):
        self.browse_font_btn.clicked.connect(self.parent.browse_font_file)
        self.execute_font_btn.clicked.connect(self.parent.execute_font_replace)
        self.restore_font_btn.clicked.connect(self.parent.restore_default_font)
        self.save_font_preset_btn.clicked.connect(self.parent.save_font_preset)
        self.font_preset_list.itemDoubleClicked.connect(self.parent.apply_font_preset_from_item)
    
    def show_font_preset_context_menu(self, pos):
        item = self.font_preset_list.itemAt(pos)
        if not item:
            return
        
        index = self.font_preset_list.row(item)
        preset = self.parent.config_manager.get_presets('font')[index]
        
        menu = QMenu(self)
        open_folder_action = menu.addAction("打开文件位置")
        open_folder_action.triggered.connect(lambda: self.parent.open_preset_folder(preset["font_path"]))
        
        delete_action = menu.addAction("删除预设")
        delete_action.triggered.connect(lambda: self.parent.delete_font_preset_confirm(index))
        
        menu.exec(self.font_preset_list.mapToGlobal(pos))