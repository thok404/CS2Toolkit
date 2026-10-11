from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QSlider, QGroupBox, QGridLayout,
    QListWidgetItem, QMenu, QApplication, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon
from qfluentwidgets import (
    FluentIcon as FIF, PushButton, ComboBox, Slider,
    TitleLabel, SubtitleLabel, BodyLabel, InfoBar, InfoBarPosition,
    SwitchButton, ListWidget, PrimaryPushButton, SimpleCardWidget, MessageBox
)
import os
import time
from .components import EventConfigWidget
from .event_dialog import AddEventDialog
from ..logic.sound_player import SoundPlayer
from ..logic.gsi_state import PlayerEventTracker, is_observing
from .styles import UIStyles

DEBUG_GSI_LOG = False
_builtin_print = print

def print(*args, **kwargs):
    if DEBUG_GSI_LOG:
        _builtin_print(*args, **kwargs)


class IntegratedSoundPage(QWidget):
    # 音效管理页面 - 实时音效配置

    # 信号
    sound_pack_changed = Signal(str)  # 音效包改变
    volume_changed = Signal(float)    # 音量改变
    test_sound_requested = Signal(str)  # 测试音效请求

    def __init__(self, gsi_manager=None, config_manager=None, parent=None):
        super().__init__(parent)
        self.gsi_manager = gsi_manager
        self.config_manager = config_manager
        self.parent = parent
        self.sound_player = SoundPlayer()
        self.previous_weapon_states = {}  # 存储之前的武器状态
        self._player_events = PlayerEventTracker()
        self.current_pack_path = None

        # 观战状态跟踪变量
        self.previous_observing_state = False
        self.previous_observer_slot = None
        self.previous_round_phase = None

        # 初始化状态跟踪变量
        self.previous_kills = 0
        self.previous_deaths = 0
        self.previous_bomb_state = ''
        self.previous_health = 100
        self.previous_is_alive = True
        self._runtime_events = []
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.timeout.connect(self._flush_debounced_save)

        # 连杀数跟踪
        self.round_kills = 0  # 当前回合的击杀数
        self.previous_round_kills = 0  # 上一次记录的回合击杀数

        # 道具投出防抖记录
        self.last_grenade_throw_time = {}

        self.init_ui()
        self._connect_signals()
        self.load_events()

    def init_ui(self):
        # 初始化用户界面
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(20)

        # 页面标题与提示
        header_layout = QHBoxLayout()
        header_layout.addWidget(TitleLabel("实时音效管理"))

        notice_label = BodyLabel("通用事件根据 GSI 数据触发，适用于不同游戏模式。\n首次创建 GSI 配置后，请重启游戏一次。")
        notice_label.setStyleSheet("color: #d4a373; font-size: 12px;")
        header_layout.addStretch()
        header_layout.addWidget(notice_label)

        layout.addLayout(header_layout)

        # 实时音效配置板块
        self.create_realtime_sound_section(layout)

    def create_realtime_sound_section(self, parent_layout):
        # 创建实时音效配置板块
        realtime_card = SimpleCardWidget(self)
        UIStyles.apply_styles(realtime_card)
        realtime_layout = QVBoxLayout(realtime_card)
        realtime_layout.setContentsMargins(20, 20, 20, 20)
        realtime_layout.setSpacing(15)

        # 事件配置
        realtime_layout.addWidget(SubtitleLabel("事件配置"))

        self.event_list = ListWidget()
        self.event_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.event_list.customContextMenuRequested.connect(self.show_event_context_menu)
        self.event_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        # 启用拖拽排序功能
        self.event_list.setDragDropMode(ListWidget.InternalMove)
        self.event_list.setDefaultDropAction(Qt.MoveAction)
        # 监听拖拽结束（顺序改变）事件，自动保存
        self.event_list.model().rowsMoved.connect(self._on_list_order_changed)
        self.event_list.itemSelectionChanged.connect(self._update_selection_actions)
        realtime_layout.addWidget(self.event_list)

        # 事件操作按钮
        add_event_layout = QHBoxLayout()
        self.save_events_btn = PushButton("保存配置")
        self.delete_selected_btn = PushButton("删除选中")
        self.delete_selected_btn.setEnabled(False)
        self.add_event_btn = PrimaryPushButton("添加新事件")
        add_event_layout.addStretch()
        add_event_layout.addWidget(self.save_events_btn)
        add_event_layout.addWidget(self.delete_selected_btn)
        add_event_layout.addWidget(self.add_event_btn)
        realtime_layout.addLayout(add_event_layout)

        parent_layout.addWidget(realtime_card)



    def _connect_signals(self):
        # 连接信号
        # 实时音效信号
        self.add_event_btn.clicked.connect(self.show_add_event_dialog)
        self.save_events_btn.clicked.connect(self.save_events)
        self.delete_selected_btn.clicked.connect(self.delete_selected_events)

    # ==================== 实时音效相关方法 ====================

    def show_add_event_dialog(self):
        # 显示添加事件对话框
        dialog = AddEventDialog(self)
        # 根据当前应用主题设置弹窗样式
        from qfluentwidgets import isDarkTheme
        if not isDarkTheme():
            dialog.widget.setStyleSheet("""
                QDialog {
                    background-color: white;
                }
                QLabel {
                    color: black;
                }
            """)

        if dialog.exec():
            config = dialog.get_config()
            if config:
                # 保存新事件配置到config_manager
                events = self.config_manager.config.get('gsi_events', [])
                events.append(config)
                self.config_manager.config['gsi_events'] = events
                self.config_manager.save_config()

                # 重新加载事件列表以正确分类新事件
                self.load_events()

                InfoBar.success(
                    title="添加成功",
                    content="新事件已添加",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP,
                    duration=2000,
                    parent=self
                )

    def add_new_event_widget(self, config=None, enable_change_callback=True):
        # 添加新的事件配置组件
        if config is None:
            config = {}

        item = QListWidgetItem()
        # 根据参数决定是否设置on_change回调
        on_change = self._on_event_config_changed if enable_change_callback else None
        widget = EventConfigWidget(parent=None, on_delete=self.delete_event_widget, on_change=on_change, on_edit=self.edit_event_widget)
        if config:
            widget.set_config(config)
        item.setSizeHint(widget.sizeHint())
        self.event_list.addItem(item)
        self.event_list.setItemWidget(item, widget)

    def edit_event_widget(self, widget):
        config = widget.get_config()
        dialog = AddEventDialog(self)

        from qfluentwidgets import isDarkTheme
        if not isDarkTheme():
            dialog.widget.setStyleSheet("""
                QDialog {
                    background-color: white;
                }
                QLabel {
                    color: black;
                }
            """)

        dialog.set_config(config)
        dialog.titleLabel.setText('编辑事件')

        if dialog.exec():
            new_config = dialog.get_config()
            if new_config:
                widget.set_config(new_config)
                self.save_events()

    def delete_event_widget(self, widget):
        # 删除事件配置组件
        # 遍历列表找到对应的QListWidgetItem
        for i in range(self.event_list.count()):
            item = self.event_list.item(i)
            if self.event_list.itemWidget(item) == widget:
                self.event_list.takeItem(i)
                break
        self.save_events()
        # 重新加载事件列表以更新分类显示
        self.load_events()

    def _selected_event_items(self):
        selected_items = []
        for item in self.event_list.selectedItems():
            widget = self.event_list.itemWidget(item)
            if hasattr(widget, 'get_config'):
                selected_items.append(item)
        return selected_items

    def _update_selection_actions(self):
        self.delete_selected_btn.setEnabled(bool(self._selected_event_items()))

    def delete_selected_events(self):
        selected_items = self._selected_event_items()
        if not selected_items:
            InfoBar.warning(
                title="未选择事件",
                content="请先按住 Ctrl 或 Shift 选择需要删除的事件。",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )
            return

        count = len(selected_items)
        dialog = MessageBox("确认删除", f"确定删除选中的 {count} 个事件吗？", self)
        dialog.yesButton.setText("删除")
        dialog.cancelButton.setText("取消")
        if not dialog.exec():
            return

        indices = sorted((self.event_list.row(item) for item in selected_items), reverse=True)
        for index in indices:
            self.event_list.takeItem(index)

        self.save_events(silent=True)
        self.load_events()
        InfoBar.success(
            title="删除成功",
            content=f"已删除 {count} 个事件。",
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def _on_list_order_changed(self, parent, start, end, destination, row):
        """当用户拖拽改变列表顺序时触发"""
        # 由于列表中包含了分类标题(QLabel)和实际的事件(EventConfigWidget)，
        # 拖拽后直接按当前的列表顺序重新提取并保存配置即可。
        self.save_events(silent=True)
        # 不调用 load_events，否则拖拽的动画和焦点会丢失或闪烁

    def save_events(self, silent=False):
        # 保存事件配置
        if not self.config_manager:
            return

        events = self._collect_events_from_ui()
        self._runtime_events = list(events)
        self._save_timer.stop()
        self.config_manager.config['gsi_events'] = events
        self.config_manager.save_config()

        if not silent:
            # 重新加载列表以确保分类正确，且UI状态与保存的数据一致
            self.load_events()

            InfoBar.success(
                title="保存成功",
                content=f"已保存 {len(events)} 个音效事件配置",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

        # 更新主页状态
        if self.parent and hasattr(self.parent, 'update_home_status'):
            self.parent.update_home_status()

        self.has_unsaved_changes = False

    def show_event_context_menu(self, pos):
        item = self.event_list.itemAt(pos)
        if not item:
            return

        widget = self.event_list.itemWidget(item)
        if not hasattr(widget, 'get_config'):
            return

        menu = QMenu(self)
        duplicate_action = menu.addAction("复制事件")
        duplicate_action.triggered.connect(lambda: self._duplicate_event(widget))
        delete_selected_action = menu.addAction("删除选中")
        delete_selected_action.setEnabled(bool(self._selected_event_items()))
        delete_selected_action.triggered.connect(self.delete_selected_events)

        menu.exec(self.event_list.mapToGlobal(pos))

    def _duplicate_event(self, widget):
        config = widget.get_config()

        if self.config_manager:
            events = self.config_manager.config.get('gsi_events', [])
            events.append(config)
            self.config_manager.config['gsi_events'] = events
            self.config_manager.save_config()

            # 重新加载事件列表以正确分类新事件
            self.load_events()

        InfoBar.success("复制成功", "已成功复制该事件。", parent=self)

    def load_events(self):
        # 加载事件配置
        if not self.config_manager:
            return

        self.event_list.clear()
        events = self.config_manager.config.get('gsi_events', [])
        self._save_timer.stop()

        # 检查并修复配置
        config_updated = False

        # 修复现有的武器击杀事件：将 event='kill' 改为 event='weapon_kill'
        # 但排除全局事件（武器名称为"全局事件"的情况）
        for event in events:
            weapon_name = event.get('weapon', '')
            event_type = event.get('event', '')
            # 只有当武器名称不是"全局事件"且事件类型是'kill'时，才转换为'weapon_kill'
            # 这样可以保护真正的全局击杀事件不被错误转换
            if (weapon_name != '全局事件' and
                event_type == 'kill' and
                weapon_name.startswith('weapon_')):
                event['event'] = 'weapon_kill'
                config_updated = True

        # 如果配置有更新，保存配置
        if config_updated:
            self.config_manager.config['gsi_events'] = events
            self.config_manager.save_config()

        self._runtime_events = list(events)

        # 移除强制的分类排序，完全尊重 JSON 文件中的顺序
        # 这样用户拖拽保存的顺序在重新启动/加载时才能保持原样

        # 只在有事件时显示分类标题（为了兼容之前的显示效果，如果用户喜欢拖拽排序，其实不加标题更好，
        # 但为了UI美观，我们现在取消强行分类，只在最顶部加一个统一的提示，或者保持原样按原数组顺序渲染）

        # 为了实现真正的任意拖拽排序，我们不再将其硬性拆分为 global_events 和 other_events。
        # 否则一调用 load_events，刚刚拖拽的顺序又会被强行归类打乱。

        for event_config in events:
            self.add_new_event_widget(event_config, enable_change_callback=False)

        # 如果没有任何事件，显示提示信息
        if not events:
            self._add_empty_hint()
        else:
            # 加载完成后，为所有事件组件启用回调
            self._enable_all_event_callbacks()
        self._update_selection_actions()

    def _add_category_header(self, category_name):
        # 添加分类标题
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import Qt

        item = QListWidgetItem()
        header_label = QLabel(f"--- {category_name} ---")
        header_label.setAlignment(Qt.AlignCenter)
        header_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                font-size: 14px;
                color: #0078d4;
                padding: 8px;
                background-color: #f5f5f5;
                border-radius: 4px;
                margin: 4px 0px;
            }
        """)

        item.setSizeHint(header_label.sizeHint())
        self.event_list.addItem(item)
        self.event_list.setItemWidget(item, header_label)

        # 设置分类标题不可选择
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)

    def _add_empty_hint(self):
        # 添加空状态提示信息
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import Qt

        item = QListWidgetItem()
        hint_label = QLabel("暂无事件配置，点击\"添加新事件\"按钮开始配置")
        hint_label.setAlignment(Qt.AlignCenter)
        hint_label.setStyleSheet("""
            QLabel {
                font-size: 13px;
                color: #888888;
                padding: 20px;
                border: 1px dashed #666666;
                border-radius: 6px;
                margin: 10px;
                background: transparent;
            }
        """)

        item.setSizeHint(hint_label.sizeHint())
        self.event_list.addItem(item)
        self.event_list.setItemWidget(item, hint_label)

        # 设置提示信息不可选择
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)

    def _enable_all_event_callbacks(self):
        # 为所有事件组件启用回调
        for i in range(self.event_list.count()):
            item = self.event_list.item(i)
            widget = self.event_list.itemWidget(item)
            # 只为EventConfigWidget启用回调
            if hasattr(widget, 'set_on_change'):
                widget.set_on_change(self._on_event_config_changed)

    def _on_event_config_changed(self):
        # 当事件配置改变时调用，只保存配置不重新加载列表
        # 静默保存配置，不重新加载列表以避免重置用户正在编辑的状态
        if not self.config_manager:
            return

        events = self._collect_events_from_ui()
        self._runtime_events = list(events)
        self.config_manager.config['gsi_events'] = events
        self._save_timer.start(300)

        # 注释掉重新加载，避免重置用户正在编辑的状态
        # self.load_events()

    def _collect_events_from_ui(self):
        events = []
        for i in range(self.event_list.count()):
            item = self.event_list.item(i)
            widget = self.event_list.itemWidget(item)
            if hasattr(widget, 'get_config'):
                config = widget.get_config()
                if config.get("weapon"):
                    events.append(config)
        return events

    def _flush_debounced_save(self):
        if not self.config_manager:
            return
        self.config_manager.config['gsi_events'] = list(self._runtime_events)
        self.config_manager.save_config()

    def process_game_state(self, game_state: dict):
        """处理游戏状态数据"""
        self._player_update = self._player_events.update(game_state)
        if self.config_manager and not self.config_manager.get("gsi_enabled", True):
            return

        player = game_state.get('player', {})
        if not player:
            return

        # Get observation status properly using the existing logic
        player_state = player.get('state', {})
        is_alive = player_state.get('health', 0) > 0
        observing = self._player_update.observing

        # Do not process any events if we are observing someone else
        if observing:
            # We still want to update our internal tracking state to not falsely trigger on respawn
            match_stats = player.get('match_stats', {})
            self.previous_kills = match_stats.get('kills', 0)
            self.previous_deaths = match_stats.get('deaths', 0)
            self.previous_round_phase = game_state.get('round', {}).get('phase', '')
            self.previous_observing_state = observing
            self.previous_is_alive = is_alive
            return

        # 处理武器相关事件
        self._process_weapon_events(game_state, player)

        # 处理C4和击杀事件
        self._process_bomb_and_kill_events(game_state, player)

    def reset_game_state(self):
        self._player_events.reset()
        self.previous_weapon_states.clear()
        self.previous_kills = 0
        self.previous_deaths = 0
        self.previous_health = 100
        self.previous_is_alive = True
        self.previous_round_phase = None
        self.previous_observer_slot = None
        self.previous_observing_state = False
        self.previous_bomb_state = ''
        self.previous_grenade_ammo = {}
        self.last_grenade_throw_time.clear()
        self.round_kills = 0
        for attribute in ('_current_active_weapon', '_last_active_weapon', '_last_fired_weapon', '_last_switch_time'):
            if hasattr(self, attribute):
                delattr(self, attribute)

    def _process_weapon_events(self, game_state: dict, player: dict):
        # 检查武器事件
        weapons = player.get('weapons', {})
        if not weapons:
            return

        # 找出当前正在触发 'active' 或 'reloading' 状态转换的武器
        triggered_events = [] # 元素格式: (武器名称, 事件类型)

        # 记录最后开火的武器（可能不准，因为GSI可能漏掉firing状态）
        # 同时记录 active 武器的历史，用于处理切枪延迟
        current_active = None
        for weapon_slot, weapon_info in weapons.items():
            weapon_name = weapon_info.get('name')
            current_state = weapon_info.get('state')
            if current_state == 'firing':
                self._last_fired_weapon = weapon_name
            if current_state == 'active':
                current_active = weapon_name

            # 检查状态转换
            for e_type in ['active', 'reloading']:
                state_key = f"{weapon_name}:{e_type}"
                prev_state = self.previous_weapon_states.get(state_key)

                if e_type == 'active':
                    if current_state == 'active' and prev_state == 'holstered':
                        triggered_events.append((weapon_name, 'active'))
                elif e_type == 'reloading':
                    if current_state == 'reloading' and prev_state != 'reloading':
                        triggered_events.append((weapon_name, 'reloading'))

                # 更新状态
                self.previous_weapon_states[state_key] = current_state

        # 更新 active 武器历史
        if current_active:
            if not hasattr(self, '_current_active_weapon'):
                self._current_active_weapon = current_active
                self._last_active_weapon = current_active
                self._last_switch_time = time.time()
            elif self._current_active_weapon != current_active:
                self._last_active_weapon = self._current_active_weapon
                self._current_active_weapon = current_active
                self._last_switch_time = time.time()

        if not triggered_events:
            return

        # 对于每一个触发了转换的事件，去事件列表中寻找最匹配的配置
        # 优先级：精确匹配 > "所有枪械"
        for t_weapon, t_event in triggered_events:
            best_sound = None
            best_volume = 50
            matched_specificity = 0 # 0=未匹配, 1=匹配到"所有枪械", 2=精确匹配特定武器

            for config in self._runtime_events:
                c_weapon = config.get('weapon')
                c_event = config.get('event')
                c_sound = config.get('sound')

                if not all([c_weapon, c_event, c_sound]):
                    continue

                if c_event == t_event:
                    if c_weapon == t_weapon:
                        # 精确匹配，最高优先级
                        if matched_specificity < 2:
                            best_sound = c_sound
                            best_volume = config.get('volume', 50)
                            matched_specificity = 2
                    elif c_weapon == 'all_weapons':
                        # "所有枪械"匹配，次级优先级
                        if matched_specificity < 1:
                            best_sound = c_sound
                            best_volume = config.get('volume', 50)
                            matched_specificity = 1

            # 如果找到了合适的音效，则播放
            if best_sound and os.path.exists(best_sound):
                self.sound_player.play_sound(best_sound, best_volume, channel="weapon")
                print(f"[GSI音效] 触发武器事件音效: {t_weapon} ({t_event}), 音量: {best_volume}%")

    def _process_bomb_and_kill_events(self, game_state: dict, player: dict):
        """处理炸弹、击杀和死亡事件"""
        # 初始化之前的状态
        if not hasattr(self, 'previous_kills'):
            self.previous_kills = player.get('match_stats', {}).get('kills', 0)
        if not hasattr(self, 'previous_deaths'):
            self.previous_deaths = player.get('match_stats', {}).get('deaths', 0)
        if not hasattr(self, 'previous_bomb_state'):
            round_bomb_state = game_state.get('round', {}).get('bomb', '')
            bomb_state = game_state.get('bomb', {}).get('state', '')
            self.previous_bomb_state = round_bomb_state or bomb_state

        # 获取当前状态信息
        match_stats = player.get('match_stats', {})
        current_kills = self.previous_kills + self._player_update.kills
        current_deaths = self.previous_deaths + int(self._player_update.died)
        self.round_kills = max(0, self._player_update.kill_count - self._player_update.kills)

        # Tracking grenade ammo
        weapons = player.get('weapons', {})
        if not hasattr(self, 'previous_grenade_ammo'):
            self.previous_grenade_ammo = {}

        current_grenade_ammo = {}
        for weapon_slot, weapon_info in weapons.items():
            weapon_name = weapon_info.get('name')
            # 只有道具才会触发投出事件
            if weapon_name and weapon_name.startswith('weapon_') and weapon_name in ['weapon_flashbang', 'weapon_smokegrenade', 'weapon_hegrenade', 'weapon_molotov', 'weapon_incgrenade', 'weapon_decoy']:
                # CS2 GSI 燃烧瓶T是molotov, CT是incgrenade，我们在配置里统称molotov
                if weapon_name == 'weapon_incgrenade':
                    weapon_name = 'weapon_molotov'
                # 道具的数量 = 本身(1) + 备弹数(如果有)
                # CS2 GSI 中，道具本身占据一个槽位，有的变体里可能没有 ammo_reserve 字段
                amt = 1 + weapon_info.get('ammo_reserve', 0)
                current_grenade_ammo[weapon_name] = current_grenade_ammo.get(weapon_name, 0) + amt

        observer_slot = player.get('observer_slot')
        current_round_phase = game_state.get('round', {}).get('phase', 'unknown')
        player_state = player.get('state', {})
        player_team = player.get('team', '')
        round_info = game_state.get('round', {})
        current_health = player_state.get('health', 0)

        # 检查玩家是否有有效的队伍和在正确的回合阶段
        has_valid_team = player_team in ['T', 'CT']
        valid_round_phases = ['live', 'freezetime', 'unknown']
        current_phase = round_info.get('phase', 'unknown')
        is_in_round = current_phase in valid_round_phases
        is_alive = player_state.get('health', 0) > 0

        # 检查是否在观战状态（更精确的检测）
        spectarget = player.get('spectarget')
        activity = player.get('activity', '')

        # 观战检测逻辑：
        # 1. 有观战目标 或
        # 2. 活动状态为观战 或
        # 3. 活动状态不是游玩 或
        # 4. 没有有效队伍（可能是观战者）
        # 注意：不要将死亡状态直接判断为观战，因为死亡时仍需要触发死亡音效
        observing = is_observing(game_state)

        # 添加详细的观战状态调试信息
        print(f"[GSI音效] 观战状态详细信息:")
        print(f"  - spectarget: {spectarget}")
        print(f"  - activity: {activity}")
        print(f"  - observer_slot: {observer_slot}")
        print(f"  - is_alive: {is_alive}")
        print(f"  - 计算出的观战状态: {observing}")
        print(f"  - 上次观战状态: {self.previous_observing_state}")
        print(f"  - 击杀数: {current_kills}, 上次击杀数: {self.previous_kills}")

        # 检测观察位置变化：当observer_slot发生变化时，重置击杀数跟踪
        if observing and observer_slot != self.previous_observer_slot:
            print(f"[GSI音效] 检测到观察位置变化: {self.previous_observer_slot} -> {observer_slot}，重置击杀数跟踪")
            self.previous_kills = current_kills
            self.previous_deaths = current_deaths
            self.previous_observer_slot = observer_slot
            self.previous_round_phase = current_round_phase
            self.previous_observing_state = observing
            self.previous_health = current_health
            self.previous_is_alive = is_alive
            return  # 直接返回，避免在观察位置切换时触发音效

        # 检测观战状态变化：当观战状态发生变化时，重置击杀数跟踪
        if observing != self.previous_observing_state:
            print(f"[GSI音效] 检测到观战状态变化: {self.previous_observing_state} -> {observing}，重置击杀数跟踪")
            self.previous_kills = current_kills
            self.previous_deaths = current_deaths
            self.previous_round_phase = current_round_phase
            self.previous_observing_state = observing
            self.previous_health = current_health
            self.previous_is_alive = is_alive
            self.previous_grenade_ammo = current_grenade_ammo
            return  # 直接返回，避免在观战状态切换时触发音效

        # 如果当前在观战状态，只处理死亡音效，跳过其他音效
        skip_non_death_events = observing
        if skip_non_death_events:
            print(f"[GSI音效] 当前在观战状态，只处理死亡音效")

        # 添加事件配置调试信息（只在第一次或配置变化时显示）
        if not hasattr(self, 'debug_events_shown'):
            self.debug_events_shown = True
            print(f"[GSI音效] 当前配置的事件列表:")
            for config in self._runtime_events:
                event_type = config.get('event')
                weapon_name = config.get('weapon', '')
                sound_path = config.get('sound')
                volume = config.get('volume', 50)

                print(f"  - 事件类型: {event_type}, 武器: {weapon_name}, 音效文件: {sound_path}, 音量: {volume}%")

            if not self._runtime_events:
                print(f"  - 没有配置任何事件")

        # 添加血量和死亡数的调试信息
        if not hasattr(self, 'previous_health'):
            self.previous_health = current_health
        if not hasattr(self, 'previous_is_alive'):
            self.previous_is_alive = is_alive

        # 检查血量变化（用于死亡检测）
        if current_health != self.previous_health:
            print(f"[GSI音效] 血量变化: {self.previous_health} -> {current_health}")

        # 检查存活状态变化（主要的死亡检测方式）
        if is_alive != self.previous_is_alive:
            print(f"[GSI音效] 存活状态变化: {self.previous_is_alive} -> {is_alive}")

        # 检查死亡数变化
        if current_deaths != self.previous_deaths:
            print(f"[GSI音效] 死亡数变化: {self.previous_deaths} -> {current_deaths}")
            print(f"[GSI音效] 玩家存活: {is_alive}, 有效队伍: {has_valid_team}, 回合状态: {is_in_round}")
            print(f"[GSI音效] 观战状态: {observing}, 观战位置: {observer_slot}, 观战目标: {spectarget}, 活动: {activity}")
            print(f"[GSI音效] 玩家血量: {current_health}, 队伍: {player_team}, 回合阶段: {round_info.get('phase', 'unknown')}")

        # 检查基于存活状态的死亡事件（从存活变为死亡）
        # 移除这个，因为它会与 based_on_deaths 逻辑重复触发
        # 仅保留 self.round_kills = 0 的逻辑
        if not is_alive and self.previous_is_alive:
            print(f"[GSI音效] 玩家死亡，重置连杀数: {self.round_kills} -> 0")
            self.round_kills = 0

        # 检查道具投出事件
        if is_in_round and is_alive and not skip_non_death_events:
            # 遍历之前持有的所有道具，检查是否数量减少或消失
            for nade, prev_amt in self.previous_grenade_ammo.items():
                current_amt = current_grenade_ammo.get(nade, 0)
                # 弹药减少，且不是从有到无的掉落（无法完美区分丢弃和投掷，但投掷会减备弹，所以如果减了1通常是投出）
                if prev_amt > current_amt:
                    # 加入防抖机制，避免CS2 GSI状态抖动导致的连续多次触发
                    current_time = time.time()
                    last_throw_time = self.last_grenade_throw_time.get(nade, 0)
                    if current_time - last_throw_time < 1.0:  # 1秒内同一种雷不重复触发投掷
                        print(f"[GSI音效] 忽略连续触发的道具投出事件: {nade}")
                        continue

                    self.last_grenade_throw_time[nade] = current_time

                    # 触发了道具投出
                    thrown_nade = nade
                    best_sound = None
                    best_volume = 50
                    matched_specificity = 0

                    for config in self._runtime_events:
                        c_event = config.get('event')
                        c_weapon = config.get('weapon')
                        c_sound = config.get('sound')

                        if c_event == 'grenade_thrown' and c_sound and os.path.exists(c_sound):
                            if c_weapon == thrown_nade and matched_specificity < 2:
                                best_sound = c_sound
                                best_volume = config.get('volume', 50)
                                matched_specificity = 2
                            elif c_weapon == 'all_grenades' and matched_specificity < 1:
                                best_sound = c_sound
                                best_volume = config.get('volume', 50)
                                matched_specificity = 1

                    if best_sound:
                        self.sound_player.play_sound(best_sound, best_volume, channel="grenade")
                        print(f"[GSI音效] 触发道具投出音效: {thrown_nade}, 音量: {best_volume}%")

        self.previous_grenade_ammo = current_grenade_ammo

        # 检查玩家死亡事件
        if current_deaths > self.previous_deaths:
            print(f"[GSI音效] 确认死亡事件，开始查找死亡音效")
            print(f"[GSI音效] 玩家死亡，重置连杀数: {self.round_kills} -> 0")
            self.round_kills = 0

            # 触发玩家死亡音效
            death_sound_found = False
            for config in self._runtime_events:

                event_type = config.get('event')
                sound_path = config.get('sound')

                print(f"[GSI音效] 检查事件配置: event_type={event_type}, sound_path={sound_path}")

                if event_type == 'player_death' and sound_path and os.path.exists(sound_path):
                    volume = config.get('volume', 50)
                    self.sound_player.play_sound(sound_path, volume, channel="death")
                    print(f"[GSI音效] 触发玩家死亡音效, 音量: {volume}%")
                    death_sound_found = True
                    break

            if not death_sound_found:
                print(f"[GSI音效] 未找到可用的死亡音效配置")

        # 检查击杀事件（观战状态下跳过）
        if current_kills > self.previous_kills and not skip_non_death_events:
            # 计算连杀数（每次击杀+1）
            kill_increment = current_kills - self.previous_kills
            self.round_kills += kill_increment

            print(f"[GSI音效] 击杀事件: 总击杀数 {self.previous_kills} -> {current_kills}, 本次击杀增量: {kill_increment}, 当前回合连杀数: {self.round_kills}")

            # 获取产生击杀时的实际武器 (如果有的话)
            weapon_used = None
            if hasattr(self, 'previous_weapon_states'):
                # 尝试从之前的武器状态中找到导致击杀的武器
                # 但是 GSI 没有直接提供 "用什么武器击杀" 的字段
                # 所以我们还是只能获取当前 active 的武器
                pass

            # 获取当前手中 active 的武器
            current_weapon = None
            weapons = player.get('weapons', {})
            for weapon_info in weapons.values():
                if weapon_info.get('state') == 'active':
                    current_weapon = weapon_info.get('name')
                    break

            # TODO: CS2 GSI 实际上有严重的时间差缺陷
            # 当用A武器击杀后瞬间切枪，收到击杀事件(kills+1)时的 active 武器已经是新武器了

            # 解决方案：使用历史记录来纠正
            last_fired_weapon = getattr(self, '_last_fired_weapon', None)

            # 方案1: 如果有明确的最后开火武器，且当前是刀，纠正为最后开火武器
            if current_weapon and ('knife' in current_weapon.lower() or 'bayonet' in current_weapon.lower()):
                if last_fired_weapon and not ('knife' in last_fired_weapon.lower() or 'bayonet' in last_fired_weapon.lower()):
                    print(f"[GSI音效] 纠正切刀击杀误判(方案1): 当前武器是刀，但判定击杀武器为最后开火的 {last_fired_weapon}")
                    current_weapon = last_fired_weapon

            # 方案2: 更加强大的历史推断。如果我们在过去 0.5 秒内切换了武器，
            # 那么这次击杀有极大概率是由"上一个"手持武器造成的（狙击枪盲狙切刀、步枪点射切刀、刀人后切枪）
            last_switch_time = getattr(self, '_last_switch_time', 0)
            last_active_weapon = getattr(self, '_last_active_weapon', None)

            if last_active_weapon and (time.time() - last_switch_time) < 0.5:
                print(f"[GSI音效] 纠正切枪击杀误判(方案2): 检测到极限切枪操作。当前 {current_weapon} -> 纠正为 {last_active_weapon}")
                current_weapon = last_active_weapon

            # 优先级：特定武器击杀 > 全局击杀
            played_sound = False

            # 1. 尝试播放特定武器击杀音效 (必须满足武器名称精确匹配)
            if not played_sound and current_weapon:
                played_sound = self._play_kill_sound('weapon_kill', current_weapon, self.round_kills)

            # 1.5. 尝试播放 "所有枪械" 击杀音效 (如果特定武器没匹配到)
            if not played_sound and current_weapon:
                played_sound = self._play_kill_sound('weapon_kill', 'all_weapons', self.round_kills)

            # 2. 如果都没有播放，或者根本没有匹配的特定武器音效，则播放全局击杀音效
            if not played_sound:
                # 传入 None 而不是 '全局事件'，让底层只匹配 'kill' 类型
                self._play_kill_sound('kill', None, self.round_kills)

        # 处理C4事件
        self._handle_bomb_events(game_state, skip_non_death_events)

        # 检查回合重置（新回合开始时重置连杀数）
        round_data = game_state.get('round', {})
        current_round_phase = round_data.get('phase', '')
        if current_round_phase != self.previous_round_phase:
            if current_round_phase in ['live', 'freezetime']:
                print(f"[GSI音效] 回合阶段变化: {self.previous_round_phase} -> {current_round_phase}, 重置连杀数")
                self.round_kills = 0

        # 更新状态
        self.previous_kills = current_kills
        self.previous_deaths = current_deaths
        round_bomb_state = game_state.get('round', {}).get('bomb', '')
        bomb_state = game_state.get('bomb', {}).get('state', '')
        self.previous_bomb_state = round_bomb_state or bomb_state
        self.previous_observing_state = observing
        self.previous_observer_slot = observer_slot
        self.previous_round_phase = current_round_phase
        self.previous_health = current_health
        self.previous_is_alive = is_alive
        self.round_kills = self._player_update.kill_count

    def _play_kill_sound(self, event_type, weapon_name, kill_count):
        """播放击杀音效，支持高级连杀配置"""
        played = False

        for config in self._runtime_events:

            config_event = config.get('event')
            config_weapon = config.get('weapon')

            # 初始化 sound_path 避免 UnboundLocalError
            sound_path = None
            volume = 50

            # 检查事件类型和武器匹配
            # 对于全局击杀事件，只检查事件类型，不检查武器名称
            if config_event == event_type:
                # 当查找 weapon_kill 时，匹配传入的武器名称 (可能是特定武器，也可能是 'all_weapons')
                if event_type == 'kill' or (event_type == 'weapon_kill' and config_weapon == weapon_name):
                    print(f"[GSI音效] 找到匹配的配置!")

                    sound_path = config.get('sound')
                    volume = config.get('volume', 50)

                    if config.get('is_advanced', False):
                        sounds_1_5 = config.get('sounds_1_5', [])
                        # kill_count 是 1-5，对应索引 0-4
                        # 如果超过5杀，继续播放5杀音效
                        idx = min(kill_count - 1, 4)
                        if idx >= 0 and idx < len(sounds_1_5):
                            adv_sound_path = sounds_1_5[idx].get('path')
                            if adv_sound_path and os.path.exists(adv_sound_path):
                                sound_path = adv_sound_path
                                volume = sounds_1_5[idx].get('volume', 50)

                    if sound_path and os.path.exists(sound_path):
                        self.sound_player.play_sound(sound_path, volume, channel="kill")
                        print(f"[GSI音效] 触发击杀音效: {weapon_name if event_type == 'weapon_kill' else '全局击杀'}, 连杀数: {kill_count}, 音量: {volume}%")
                        played = True
                        break
                    else:
                        print(f"[GSI音效] 击杀音效文件不存在: {sound_path}")

        if not played:
            print(f"[GSI音效] 未找到匹配的击杀音效: {event_type}, {weapon_name}, 连杀数: {kill_count}")

        return played

    def _handle_bomb_events(self, game_state, skip_non_death_events):
        """处理C4相关事件"""
        # 检查C4事件（观战状态下跳过）
        round_data = game_state.get('round', {})
        bomb_data = game_state.get('bomb', {})
        current_bomb_state = round_data.get('bomb', '') or bomb_data.get('state', '')

        if current_bomb_state != self.previous_bomb_state and not skip_non_death_events:
            if current_bomb_state == 'planted':
                # 触发C4安装音效
                for config in self._runtime_events:

                    event_type = config.get('event')
                    sound_path = config.get('sound')

                    if event_type == 'bomb_planted' and sound_path and os.path.exists(sound_path):
                        volume = config.get('volume', 50)
                        self.sound_player.play_sound(sound_path, volume, channel="bomb")
                        print(f"[GSI音效] 触发C4安装音效, 音量: {volume}%")
                        break
            elif current_bomb_state == 'defused':
                # 只在明确收到 defused 状态时触发C4拆除，避免爆炸时误触发
                for config in self._runtime_events:

                    event_type = config.get('event')
                    sound_path = config.get('sound')

                    if event_type == 'bomb_defused' and sound_path and os.path.exists(sound_path):
                        volume = config.get('volume', 50)
                        self.sound_player.play_sound(sound_path, volume, channel="bomb")
                        print(f"[GSI音效] 触发C4拆除音效, 音量: {volume}%")
                        break
