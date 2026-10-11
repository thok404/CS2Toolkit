"""Player ownership and event counters independent of the game mode."""

from dataclasses import dataclass


def is_observing(game_state):
    player = game_state.get('player', {})
    own_id = game_state.get('provider', {}).get('steamid')
    player_id = player.get('steamid')
    if player.get('activity') in ('menu', 'spectating'):
        return True
    if own_id and player_id:
        return str(own_id) != str(player_id)
    target = player.get('spectarget')
    if target not in (None, '', 0, '0') and str(target) not in (str(own_id), str(player_id)):
        return True
    return player.get('team') not in ('T', 'CT') and player.get('activity') != 'playing'


def _counter(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


@dataclass
class PlayerEvents:
    kills: int = 0
    kill_count: int = 0
    died: bool = False
    observing: bool = False
    new_session: bool = False


class PlayerEventTracker:
    def __init__(self):
        self.reset()

    def reset(self):
        self.context = None
        self.counter_source = None
        self.kills = None
        self.deaths = None
        self.health = None
        self.round = None
        self.kill_count = 0
        self.phase = None

    def update(self, game_state):
        player = game_state.get('player', {})
        if not player or is_observing(game_state):
            self.reset()
            return PlayerEvents(observing=True)
        map_info = game_state.get('map', {})
        state = player.get('state', {})
        stats = player.get('match_stats', {})
        context = (player.get('steamid'), map_info.get('name'), map_info.get('mode'))
        phase = map_info.get('phase')
        new_session = context != self.context or (self.phase in ('gameover', 'intermission') and phase in ('live', 'warmup'))
        if new_session:
            self.reset()
            self.context = context
        round_number = map_info.get('round')
        if round_number != self.round or game_state.get('round', {}).get('phase') == 'freezetime':
            self.kill_count = 0
        health = _counter(state.get('health'))
        deaths = _counter(stats.get('deaths'))
        died = (health == 0 and self.health is not None and self.health > 0) or (
            deaths is not None and self.deaths is not None and deaths > self.deaths)
        if died or (self.health == 0 and health is not None and health > 0):
            self.kill_count = 0

        # 各模式都可能提供回合/当前生命击杀数；缺少时再使用比赛累计数。
        kills = _counter(state.get('round_kills'))
        source = 'round'
        if kills is None:
            kills = _counter(stats.get('kills'))
            source = 'match'
        increment = 0
        if kills is not None:
            if source == self.counter_source and self.kills is not None:
                increment = max(0, kills - self.kills)
                if kills < self.kills:
                    self.kill_count = 0
            self.kills = kills
            self.counter_source = source
        self.kill_count += increment
        if health is not None:
            self.health = health
        if deaths is not None:
            self.deaths = deaths
        self.round = round_number
        self.phase = phase
        return PlayerEvents(increment, self.kill_count, died, False, new_session)
