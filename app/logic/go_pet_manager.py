import os
import random
from PySide6.QtCore import QObject, QTimer
from app.ui.go_pet_overlay import GoPetCaptureWindow, GoPetOverlay
from app.logic.sound_player import SoundPlayer
from .gsi_state import PlayerEventTracker

class GoPetManager(QObject):
    def __init__(self, config_manager):
        super().__init__()
        self.config_manager = config_manager
        self.overlay = GoPetOverlay()
        self.capture_window = GoPetCaptureWindow()
        self.sound_player = SoundPlayer()
        
        self.enabled = False
        self.display_mode = "game"
        self.events_config = {}
        self.current_priority = -1
        
        # State tracking
        self.is_flashed = False
        self.is_dead = False
        self.health = 100
        self.bomb_planted = False
        self.phase = ""
        self._player_events = PlayerEventTracker()
        
        self.priority_map = {
            "death": 100,
            "mvp": 95,
            "win": 90,
            "loss": 90,
            "bomb": 85,
            "flashed": 80,
            "low_health": 60,
            "kill": 70,
            "rich": 40,
            "poor": 40,
            "freeze": 30,
            "normal": 0
        }
        
        # Timer to reset transient events (like kill)
        self.reset_timer = QTimer(self)
        self.reset_timer.timeout.connect(self._reset_to_persistent_state)
        self.reset_timer.setSingleShot(True)
        
        self._update_config()
        
    def _update_config(self):
        config = self.config_manager.get('go_pet', {})
        self.enabled = config.get('enabled', False)
        self.display_mode = config.get('display_mode', 'game')
        
        self.overlay.set_size(config.get('size', 200))
        self.overlay.set_position(config.get('offset_x', 50), config.get('offset_y', 50))
        self.capture_window.set_size(config.get('size', 200))
        
        events_list = config.get('events', [])
        if isinstance(events_list, list):
            self.events_config = {}
            for e in events_list:
                if isinstance(e, dict) and 'type' in e:
                    self.events_config[e['type']] = e
        else:
            self.events_config = {}
        
        if self.enabled:
            if self.display_mode == "capture":
                self.overlay.hide_pet()
                self.capture_window.show_output_shell()
            else:
                self.capture_window.hide_output_shell()
            self._reset_to_persistent_state()
        else:
            self.overlay.hide_pet()
            self.capture_window.hide_output_shell()
            
    def set_enabled(self, enabled):
        self.enabled = enabled
        if enabled:
            self._update_config()
        else:
            self.overlay.hide_pet()
            self.capture_window.hide_output_shell()

    def _get_active_display(self):
        return self.capture_window if self.display_mode == "capture" else self.overlay

    def _hide_inactive_display(self):
        if self.display_mode == "capture":
            self.overlay.hide_pet()
            self.capture_window.show_output_shell()
        else:
            self.capture_window.hide_output_shell()

    def _is_low_health_active(self, health=None):
        if health is None:
            health = self.health
        if "low_health" not in self.events_config:
            return False
        threshold = self.events_config["low_health"].get("threshold", 30)
        return health < threshold

    def _parse_float(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_random_file(self, path, is_sound=False):
        if not path or not os.path.exists(path):
            return None
            
        if os.path.isdir(path):
            if is_sound:
                exts = {'.mp3', '.wav'}
            else:
                exts = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp', '.mp4', '.webm', '.avi', '.mov', '.mkv'}
                
            files = [os.path.join(path, f) for f in os.listdir(path) if os.path.splitext(f)[1].lower() in exts]
            if not files:
                return None
            return random.choice(files)
        return path
        
    def _trigger_event(self, event_type, transient=False):
        if not self.enabled:
            return
            
        priority = self.priority_map.get(event_type, 0)
        
        # Only override if priority is strictly higher, unless it's normal
        if priority >= self.current_priority or event_type == "normal":
            self.current_priority = priority
            active_display = self._get_active_display()
            self._hide_inactive_display()
            
            cfg = self.events_config.get(event_type)
            if cfg:
                img = self._get_random_file(cfg.get('image'), is_sound=False)
                snd = self._get_random_file(cfg.get('sound'), is_sound=True)
                
                if img:
                    active_display.update_pet(img)
                if snd:
                    self.sound_player.play_sound(snd, volume=100, channel="pet")
            elif event_type == "normal" and self.display_mode == "capture":
                self.capture_window.show_output_shell()
                    
            if transient:
                self.reset_timer.start(3000) # 3 seconds
            else:
                self.reset_timer.stop()

    def _reset_to_persistent_state(self):
        # Re-evaluate persistent state
        self.current_priority = -1 # Reset priority to allow re-evaluation
        
        if self.is_dead:
            self._trigger_event("death")
        elif self.is_flashed:
            self._trigger_event("flashed")
        elif self._is_low_health_active():
            self._trigger_event("low_health")
        elif self.phase == "freezetime":
            self._trigger_event("freeze")
        else:
            self._trigger_event("normal")

    def process_gsi(self, game_state):
        if not self.enabled:
            self._player_events.reset()
            return
            
        player = game_state.get('player', {})
        events = self._player_events.update(game_state)
        if not player:
            return
            
        state = player.get('state', {})
        round_info = game_state.get('round', {})
        phase = round_info.get('phase', '')
        match_stats = player.get('match_stats', {})
        
        is_observing = events.observing
        
        if is_observing:
            return

        # Phase tracking
        if phase != self.phase:
            previous_phase = self.phase
            self.phase = phase
            if phase in ("freezetime", "over"):
                self.bomb_planted = False
            if previous_phase == "over" and hasattr(self, '_round_over_triggered'):
                del self._round_over_triggered
            self._reset_to_persistent_state()
        
        # Health & Death
        health = state.get('health', 100)
        was_low_health = self._is_low_health_active()
        if health == 0 and not self.is_dead:
            self.is_dead = True
            self._trigger_event("death")
        elif health > 0 and self.is_dead:
            self.is_dead = False
            self._reset_to_persistent_state()
            
        self.health = health
        is_low_health = self._is_low_health_active()
        if is_low_health != was_low_health and not self.is_dead:
            self._reset_to_persistent_state()
        
        # Flashed
        flashed = state.get('flashed', 0) > 0
        if flashed and not self.is_flashed:
            self.is_flashed = True
            self._trigger_event("flashed")
        elif not flashed and self.is_flashed:
            self.is_flashed = False
            self._reset_to_persistent_state()
            
        # Bomb
        bomb_data = game_state.get('bomb', {})
        bomb_state = round_info.get('bomb', '') or bomb_data.get('state', '')
        if bomb_state == 'planted':
            if not self.bomb_planted:
                self.bomb_planted = True
                self._trigger_event("bomb", transient=True)
        elif self.bomb_planted:
            self.bomb_planted = False
            self._reset_to_persistent_state()
            
        # Kills
        if events.kills:
            self._trigger_event("kill", transient=True)
            
        # Economy (only evaluate during freezetime)
        if phase == "freezetime":
            money = state.get('money', 0)
            if "rich" in self.events_config and money >= self.events_config["rich"].get("threshold", 10000):
                self._trigger_event("rich", transient=True)
            elif "poor" in self.events_config and money <= self.events_config["poor"].get("threshold", 2000):
                self._trigger_event("poor", transient=True)
                
        # MVP / Win / Loss
        current_mvps = match_stats.get('mvps', 0)
        if not hasattr(self, '_last_mvps'):
            self._last_mvps = current_mvps

        if phase == "over" and round_info.get('win_team') in ('T', 'CT') and not hasattr(self, '_round_over_triggered'):
            self._round_over_triggered = True
            win_team = round_info.get('win_team')
            my_team = player.get('team')
            won_round = win_team == my_team
            got_mvp = current_mvps > self._last_mvps
            if won_round and got_mvp and "mvp" in self.events_config:
                self._trigger_event("mvp", transient=True)
            elif won_round:
                self._trigger_event("win", transient=True)
            else:
                self._trigger_event("loss", transient=True)
        elif phase != "over":
            if hasattr(self, '_round_over_triggered'):
                del self._round_over_triggered
        self._last_mvps = current_mvps

        # main_window processes visual_handler before go_pet_manager.
        # Re-raise the pet overlay at the end of each GSI frame so flash/death
        # overlays do not cover the pet.
        if self.display_mode == "game":
            self.overlay.ensure_on_top()

    def reset_game_state(self):
        self._player_events.reset()
        self.reset_timer.stop()
        self.is_dead = False
        self.is_flashed = False
        self.health = 100
        self.phase = ''
        self.bomb_planted = False
        self._last_mvps = 0
        if hasattr(self, '_round_over_triggered'):
            del self._round_over_triggered
        self._reset_to_persistent_state()
