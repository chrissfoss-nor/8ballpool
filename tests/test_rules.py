# =============================================================================
# test_rules.py — regression tests for the rack layout and the win condition.
#
# Both cover bugs that made the game unplayable rather than merely ugly, so
# they are worth pinning down:
#
#   • the rack was stepped by a full ball width per row, leaving a stretched
#     triangle whose rows never touched;
#   • group progress was counted per shooter, so a ball your opponent potted
#     for you never counted and you could never legally play the 8 ball.
#
# Run with:  python tests/test_rules.py
# =============================================================================

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from entities.ball       import Ball, BallGroup
from game.game           import _compute_rack_positions, _make_rack_order
from game.turn_manager   import TurnManager
from utils.constants     import BALL_RADIUS, RACK_BALL_SPACING
from utils.vector        import Vec2


def test_rack_is_a_tight_triangle():
    """Every ball touches its neighbours, and none of them overlap."""
    positions = _compute_rack_positions(905.0, 380.0)
    assert len(positions) == 15

    for i, a in enumerate(positions):
        nearest = min(math.dist(a, b) for j, b in enumerate(positions) if j != i)
        # Neighbours sit exactly one spacing apart -- not stretched, not overlapping
        assert abs(nearest - RACK_BALL_SPACING) < 1e-6, (
            f"ball {i} nearest neighbour at {nearest:.2f}, expected {RACK_BALL_SPACING}"
        )
        assert nearest >= BALL_RADIUS * 2, f"ball {i} overlaps a neighbour"

    # Five rows of 1..5, each stepped back by the triangle height
    rows = {}
    for x, y in positions:
        rows.setdefault(round(x, 3), []).append(y)
    assert sorted(len(v) for v in rows.values()) == [1, 2, 3, 4, 5]


def test_rack_order_follows_the_8_ball_rules():
    """Apex is the 1, the 8 sits mid third row, back corners split the groups."""
    for _ in range(200):          # the fill is randomised, so check it repeatedly
        rack = _make_rack_order()
        assert sorted(rack) == list(range(1, 16)), "rack must hold each ball once"
        assert rack[0] == 1,  "apex must be the 1 ball"
        assert rack[4] == 8,  "8 ball must sit in the centre of the third row"
        corners = (rack[10], rack[14])
        assert any(1 <= n <= 7 for n in corners),  "one back corner must be a solid"
        assert any(9 <= n <= 15 for n in corners), "one back corner must be a stripe"


def _table_with(pocketed_numbers):
    """Build a full set of balls with *pocketed_numbers* marked as potted."""
    balls = [Ball(number=n, pos=Vec2(100.0 + n * 40, 200.0)) for n in range(16)]
    for ball in balls:
        if ball.number in pocketed_numbers:
            ball.pocketed = True
    return balls


def test_opponent_pots_still_clear_your_group():
    """A group is cleared once its balls are down, whoever sank them."""
    turns = TurnManager("Player 1", "Player 2")
    turns.assign_groups(BallGroup.SOLID)      # current player takes solids
    solids_player = turns.current

    # Every solid is off the table, but the player never recorded a single pot
    balls = _table_with(range(1, 8))
    assert solids_player.pocketed_balls == []

    assert solids_player.balls_remaining(balls) == 0
    assert solids_player.has_cleared_group(balls), (
        "group must count as cleared even when the opponent potted the balls"
    )


def test_group_is_not_cleared_while_a_ball_remains():
    turns = TurnManager("Player 1", "Player 2")
    turns.assign_groups(BallGroup.STRIPE)
    striper = turns.current

    balls = _table_with(range(9, 15))          # 9-14 down, 15 still on the table
    assert striper.balls_remaining(balls) == 1
    assert not striper.has_cleared_group(balls)


def test_no_group_assigned_means_not_cleared():
    turns = TurnManager("Player 1", "Player 2")
    balls = _table_with([])
    assert not turns.current.has_cleared_group(balls)
    assert turns.current.balls_remaining(balls) == 0


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
