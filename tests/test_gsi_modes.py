"""Mode-independent counters, ownership and restart baselines."""
import unittest
from app.logic.gsi_state import PlayerEventTracker, is_observing


def state(mode='competitive', kills=0, health=100, deaths=0, source='round', target=None):
    player = {'steamid': 'self', 'activity': 'playing', 'team': 'CT', 'state': {'health': health},
              'match_stats': {'deaths': deaths}}
    if source == 'round':
        player['state']['round_kills'] = kills
    else:
        player['match_stats']['kills'] = kills
    if target is not None:
        player['spectarget'] = target
    return {'provider': {'steamid': 'self'}, 'map': {'name': 'test', 'mode': mode, 'phase': 'live'}, 'player': player}


class GSIModeTests(unittest.TestCase):
    def test_shared_events_across_modes_without_round_phase(self):
        for mode in ('competitive', 'casual', 'deathmatch', 'gungameprogressive', 'gungametrbomb', 'retakes', 'custom'):
            for source in ('round', 'match'):
                with self.subTest(mode=mode, source=source):
                    tracker = PlayerEventTracker()
                    self.assertEqual(tracker.update(state(mode, 4, source=source)).kills, 0)
                    event = tracker.update(state(mode, 5, source=source))
                    self.assertEqual((event.kills, event.kill_count), (1, 1))
                    self.assertEqual(tracker.update(state(mode, 5, source=source)).kills, 0)
                    self.assertTrue(tracker.update(state(mode, 5, health=0, source=source)).died)
                    self.assertFalse(tracker.update(state(mode, 5, health=0, source=source)).died)
                    self.assertFalse(tracker.update(state(mode, 5, health=100, source=source)).died)
                    self.assertEqual(tracker.update(state(mode, 6, source=source)).kill_count, 1)

    def test_own_target_and_zero_sentinels_are_not_spectators(self):
        for target in ('self', '0', 0, ''):
            with self.subTest(target=target):
                self.assertFalse(is_observing(state(target=target)))

    def test_explicit_other_player_cannot_trigger_events(self):
        tracker = PlayerEventTracker()
        tracker.update(state(kills=1))
        other = state(kills=99)
        other['player']['steamid'] = 'other'
        self.assertTrue(tracker.update(other).observing)
        self.assertEqual(tracker.update(state(kills=1)).kills, 0)
        self.assertEqual(tracker.update(state(kills=2)).kills, 1)

    def test_mode_or_map_change_establishes_new_baseline(self):
        tracker = PlayerEventTracker()
        tracker.update(state(kills=20))
        self.assertEqual(tracker.update(state('deathmatch', 1)).kills, 0)
        self.assertEqual(tracker.update(state('deathmatch', 2)).kills, 1)
        changed = state('deathmatch', 60)
        changed['map']['name'] = 'new-map'
        self.assertEqual(tracker.update(changed).kills, 0)

    def test_counter_reset_recovers_next_kill(self):
        tracker = PlayerEventTracker()
        tracker.update(state(kills=20))
        self.assertEqual(tracker.update(state(kills=0)).kills, 0)
        self.assertEqual(tracker.update(state(kills=1)).kill_count, 1)

    def test_starting_tool_mid_game_does_not_trigger_old_kills_or_deaths(self):
        tracker = PlayerEventTracker()
        event = tracker.update(state(kills=42, health=0, deaths=20))
        self.assertEqual(event.kills, 0)
        self.assertFalse(event.died)
        tracker.update(state(kills=42, health=100, deaths=20))
        self.assertEqual(tracker.update(state(kills=43, deaths=20)).kills, 1)

    def test_health_only_death_is_detected_without_match_stats(self):
        tracker = PlayerEventTracker()
        alive = state()
        del alive['player']['match_stats']
        tracker.update(alive)
        alive['player']['state']['health'] = 0
        self.assertTrue(tracker.update(alive).died)

    def test_missing_team_with_own_identity_does_not_disable_ffa(self):
        data = state('deathmatch')
        del data['player']['team']
        self.assertFalse(is_observing(data))

    def test_menu_disconnect_and_game_restart_reset_old_counters(self):
        tracker = PlayerEventTracker()
        tracker.update(state(kills=50))
        self.assertTrue(tracker.update({'player': {'steamid': 'self', 'activity': 'menu'}}).observing)
        self.assertEqual(tracker.update(state(kills=0)).kills, 0)
        self.assertEqual(tracker.update(state(kills=1)).kills, 1)


if __name__ == '__main__':
    unittest.main()
