# =============================================================================
# test_ai.py - regression tests for headless simulation and AI decisions.
#
# Run with:  python tests/test_ai.py
# =============================================================================

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from ai.geometry import active_obstacles, bank_shots, pot_shots
from ai.policy import AIPlayer, _pot_power
from ai.simulation import GameSnapshot, HeadlessSimulator, Shot, legal_target_numbers
from entities.ball import Ball, BallGroup
from entities.table import create_table
from game.turn_manager import TurnManager
from utils.constants import BALL_RADIUS
from utils.vector import Vec2


def _easy_solid_snapshot(ball_in_hand=False):
    table = create_table()
    turns = TurnManager("Player 1", "Player 2")
    turns.assign_groups(BallGroup.SOLID)
    turns.current.has_ball_in_hand = ball_in_hand

    balls = [Ball(number=n, pos=Vec2(200.0 + n * 32.0, table.center.y)) for n in range(16)]
    for ball in balls:
        if ball.number not in (0, 1, 8):
            ball.pocketed = True

    pocket = min(
        table.pockets,
        key=lambda p: (p.pos.x - table.left) ** 2 + (p.pos.y - table.top) ** 2,
    )
    diagonal = Vec2(math.cos(math.pi / 4), math.sin(math.pi / 4))
    target = balls[1]
    target.pos = pocket.pos + diagonal * (BALL_RADIUS * 4)

    cue = balls[0]
    cue.pos = target.pos + diagonal * (BALL_RADIUS * 9)
    if ball_in_hand:
        cue.pocketed = True

    eight = balls[8]
    eight.pos = Vec2(table.right - 90.0, table.bottom - 90.0)
    eight.pocketed = False

    snapshot = GameSnapshot.from_runtime(
        balls=balls,
        turns=turns,
        is_break=False,
    )
    angle = (pocket.pos - cue.pos).angle()
    return table, snapshot, angle


def test_headless_simulation_uses_real_rules_for_a_legal_shot():
    table, snapshot, angle = _easy_solid_snapshot()
    # Straight in off a rolling cue ball is an in-off, so the shot is played
    # with bottom - which also puts the tip offset through the simulator.
    result = HeadlessSimulator(table).simulate(snapshot, Shot(angle, 0.5, spin_y=-0.5))

    assert result.legal, result.shot_result.foul_reason
    assert result.first_contact_number == 1
    assert 1 in result.pocketed_numbers
    assert not result.next_state.current_player.has_ball_in_hand


def test_ai_decision_is_deterministic_and_pots_the_easy_ball():
    table, snapshot, _angle = _easy_solid_snapshot()
    ai_a = AIPlayer(candidate_count=24, seed=7, table=table)
    ai_b = AIPlayer(candidate_count=24, seed=7, table=table)

    decision_a = ai_a.choose_decision(snapshot)
    decision_b = ai_b.choose_decision(snapshot)

    assert math.isclose(decision_a.shot.angle, decision_b.shot.angle)
    assert math.isclose(decision_a.shot.power, decision_b.shot.power)
    assert decision_a.result.legal, decision_a.result.shot_result.foul_reason
    assert 1 in decision_a.result.pocketed_numbers


def test_ai_places_the_cue_ball_when_it_has_ball_in_hand():
    table, snapshot, _angle = _easy_solid_snapshot(ball_in_hand=True)
    ai = AIPlayer(candidate_count=24, seed=3, table=table)

    decision = ai.choose_decision(snapshot)

    assert decision.shot.cue_ball_pos is not None
    assert not decision.result.error
    assert decision.result.legal, decision.result.shot_result.foul_reason


def _two_ball_snapshot(cue_xy, object_xy):
    """A cleared table holding only the cue ball, the 1 and the 8."""
    table = create_table()
    turns = TurnManager("Player 1", "Player 2")
    turns.assign_groups(BallGroup.SOLID)

    balls = [Ball(number=n, pos=Vec2(0.0, 0.0)) for n in range(16)]
    for ball in balls:
        ball.pocketed = True

    for number, pos in (
        (0, cue_xy),
        (1, object_xy),
        (8, (table.right - 60.0, table.bottom - 60.0)),
    ):
        balls[number].pos = Vec2(pos[0], pos[1])
        balls[number].pocketed = False

    snapshot = GameSnapshot.from_runtime(balls=balls, turns=turns, is_break=False)
    return table, snapshot


def _legal_targets(snapshot):
    legal = set(legal_target_numbers(snapshot))
    return [ball for ball in active_obstacles(snapshot) if ball[0] in legal]


def test_geometry_rejects_every_shot_into_a_full_rack():
    """Nothing in a tight rack has a clear run to a pocket."""
    table = create_table()
    snapshot = GameSnapshot.new_game(seed=1)
    cue = snapshot.active_cue_position()

    found = pot_shots(
        cue.x, cue.y, _legal_targets(snapshot), table, active_obstacles(snapshot)
    )

    assert found == [], f"expected no feasible pots off the rack, got {len(found)}"


def test_geometry_finds_the_open_shot_and_rates_it_straight():
    table, snapshot, _angle = _easy_solid_snapshot()
    cue = snapshot.active_cue_position()

    found = pot_shots(
        cue.x, cue.y, _legal_targets(snapshot), table, active_obstacles(snapshot)
    )

    assert len(found) == 1, f"expected exactly one feasible pot, got {len(found)}"
    assert found[0].target_number == 1
    assert found[0].cut_cos > 0.99, "a dead-straight shot should have cut_cos ~ 1"


def test_bank_geometry_finds_a_shot_that_actually_pots():
    """The bank mirror has to account for the cushion, not just reflect."""
    table, snapshot = _two_ball_snapshot((523.0, 266.0), (693.0, 319.0))
    cue = snapshot.active_cue_position()

    banks = bank_shots(
        cue.x, cue.y, _legal_targets(snapshot), table, active_obstacles(snapshot)
    )
    assert banks, "expected at least one bank shot to be proposed"

    potted = False
    for bank in banks[:4]:
        result = HeadlessSimulator(table).simulate(
            snapshot, Shot(bank.aim_angle, _pot_power(bank))
        )
        if bank.target_number in result.pocketed_numbers:
            potted = True
            break

    assert potted, "none of the proposed banks actually reached a pocket"


def test_a_sliced_search_matches_an_uninterrupted_one():
    """Handing the search out a few milliseconds at a time must not change it."""
    snapshot = GameSnapshot.new_game(seed=1)

    whole = AIPlayer(candidate_count=30, seed=0).choose_decision(snapshot)

    search = AIPlayer(candidate_count=30, seed=0).start_search(snapshot)
    while not search.advance(0.003):
        pass
    sliced = search.decision()

    assert math.isclose(whole.shot.angle, sliced.shot.angle)
    assert math.isclose(whole.shot.power, sliced.shot.power)
    assert math.isclose(whole.score, sliced.score)
    assert whole.candidates_evaluated == sliced.candidates_evaluated


def test_position_value_rates_an_easy_leave_above_an_awkward_one():
    table = create_table()
    player = AIPlayer(candidate_count=1, seed=0, table=table)

    # Short, straight, close to a pocket.
    _t, easy = _two_ball_snapshot((260.0, 250.0), (200.0, 210.0))
    # Long and thin, with the object ball out in open space.
    _t, awkward = _two_ball_snapshot((1080.0, 640.0), (600.0, 400.0))

    assert player.position_value(easy) > player.position_value(awkward)


def test_position_value_is_zero_when_nothing_can_be_potted():
    table = create_table()
    player = AIPlayer(candidate_count=1, seed=0, table=table)
    snapshot = GameSnapshot.new_game(seed=1)

    assert player.position_value(snapshot) == 0.0


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {name}: {exc}")
    print()
    print("all tests passed" if not failures else f"{failures} test(s) failed")
    sys.exit(1 if failures else 0)
