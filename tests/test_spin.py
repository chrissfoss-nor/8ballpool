# =============================================================================
# test_spin.py - regression tests for cue-ball spin (english).
#
# The claims worth pinning down are the ones a player would recognise from a
# real table: bottom brings the cue ball back, top sends it on, side changes
# the angle it comes off a cushion at - and none of it moves an object ball
# that was struck without side spin.
#
# Run with:  python tests/test_spin.py
# =============================================================================

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from ai.simulation import GameSnapshot, HeadlessSimulator, Shot
from entities.ball import Ball, BallGroup, BallState
from entities.cue import Cue
from entities.table import create_table
from game.turn_manager import TurnManager
from physics.ball_collision import resolve_pair
from physics.engine import PhysicsEngine
from physics.spin import apply_cue_strike, clamp_tip_offset
from ui.hud import SPIN_DIAL_CENTER, SPIN_DIAL_RADIUS, spin_from_pointer
from utils.constants import BALL_RADIUS, SPIN_MAX_TIP_OFFSET
from utils.vector import Vec2


def _cue_x_after(tip_y, speed=1100.0):
    """Play a dead-straight full-ball hit and return where the cue ball stops.

    The physics engine is driven directly: what is being measured is where the
    cloth leaves the cue ball, not what the rules make of the shot.  The object
    ball is lifted off the table the moment it is struck, so a follow shot that
    catches up with it cannot muddle the reading.
    """
    table = create_table()
    engine = PhysicsEngine(table)
    engine.reset_for_shot()

    y = table.center.y
    cue = Ball(number=0, pos=Vec2(400.0, y))
    target = Ball(number=1, pos=Vec2(600.0, y))
    apply_cue_strike(cue, Vec2(speed, 0.0), 0.0, tip_y)

    balls = [cue, target]
    for _ in range(1200):
        engine.update(1.0 / 60.0, balls)
        if target.vel.length_sq() > 0.0 and not target.pocketed:
            target.pocket()
        if engine.all_stationary:
            break

    assert not cue.pocketed, "the cue ball should still be on the table"
    return cue.pos.x


def test_bottom_draws_back_top_follows_through_and_centre_lands_between():
    draw = _cue_x_after(-SPIN_MAX_TIP_OFFSET)
    centre = _cue_x_after(0.0)
    follow = _cue_x_after(SPIN_MAX_TIP_OFFSET)

    assert draw < centre < follow, (
        f"expected draw < centre < follow, got {draw:.1f} {centre:.1f} {follow:.1f}"
    )


def test_a_full_draw_shot_sends_the_cue_ball_back_past_where_it_started():
    """The cue ball is struck at x=400 and the 1 sits at x=600.

    Coming back past the point it was struck from is the whole difference
    between a draw shot and a stun.
    """
    draw = _cue_x_after(-SPIN_MAX_TIP_OFFSET)

    assert draw < 400.0, f"a full draw shot should come back past 400, stopped at {draw:.1f}"


def test_side_spin_changes_the_angle_off_a_cushion():
    table = create_table()

    def rebound_y(tip_x):
        engine = PhysicsEngine(table)
        engine.reset_for_shot()
        # Away from the middle of the rail: that is where the side pocket is.
        ball = Ball(number=0, pos=Vec2(table.center.x - 200.0, table.center.y))
        apply_cue_strike(ball, Vec2(0.0, -900.0), tip_x, 0.0)
        balls = [ball]
        for _ in range(240):
            engine.update(1.0 / 60.0, balls)
            if engine.all_stationary:
                break
        return ball.pos.x

    left = rebound_y(-SPIN_MAX_TIP_OFFSET)
    none = rebound_y(0.0)
    right = rebound_y(SPIN_MAX_TIP_OFFSET)

    assert math.isclose(none, table.center.x - 200.0, abs_tol=1e-6), (
        "a centre-ball shot straight into a cushion must come straight back"
    )
    assert left < none < right, (
        f"side spin should swing the rebound both ways, got {left:.1f} {none:.1f} {right:.1f}"
    )


def test_top_and_bottom_spin_do_not_move_the_object_ball():
    """Only the cue ball's own path may change; the pot must not."""

    def struck_velocity(tip_y):
        cue = Ball(number=0, pos=Vec2(400.0, 400.0))
        apply_cue_strike(cue, Vec2(500.0, 0.0), 0.0, tip_y)
        cue.pos = Vec2(400.0, 400.0)
        target = Ball(number=1, pos=Vec2(400.0 + BALL_RADIUS * 2 - 0.5, 400.0))
        resolve_pair(cue, target)
        return (target.vel.x, target.vel.y)

    plain = struck_velocity(0.0)
    for tip_y in (-SPIN_MAX_TIP_OFFSET, -0.2, 0.2, SPIN_MAX_TIP_OFFSET):
        assert struck_velocity(tip_y) == plain, (
            f"tip offset {tip_y} changed how the object ball was struck"
        )


def test_side_spin_throws_the_object_ball_off_the_aiming_line():
    def struck_velocity(tip_x):
        cue = Ball(number=0, pos=Vec2(400.0, 400.0))
        apply_cue_strike(cue, Vec2(500.0, 0.0), tip_x, 0.0)
        cue.pos = Vec2(400.0, 400.0)
        target = Ball(number=1, pos=Vec2(400.0 + BALL_RADIUS * 2 - 0.5, 400.0))
        resolve_pair(cue, target)
        return target.vel.y

    left = struck_velocity(-SPIN_MAX_TIP_OFFSET)
    none = struck_velocity(0.0)
    right = struck_velocity(SPIN_MAX_TIP_OFFSET)

    assert none == 0.0, "a centre-ball hit must send the object ball straight"
    assert left * right < 0.0, "left and right english must throw opposite ways"
    assert abs(left) < 60.0, f"throw is meant to be a nudge, not a swerve: {left:.1f}"


def test_a_ball_with_no_spin_settles_exactly_as_it_always_did():
    """The spin model must be invisible to a centre-ball shot."""
    table = create_table()
    engine = PhysicsEngine(table)
    engine.reset_for_shot()

    ball = Ball(number=0, pos=Vec2(300.0, 400.0))
    apply_cue_strike(ball, Vec2(400.0, 0.0), 0.0, 0.0)
    assert ball.slip.length() == 0.0, "a centre-ball hit leaves no slip to work on"

    balls = [ball]
    for _ in range(600):
        engine.update(1.0 / 60.0, balls)
        assert ball.slip.length() == 0.0, "slip appeared out of nowhere"
        if engine.all_stationary:
            break

    assert ball.state is BallState.STATIONARY
    assert ball.roll.length() == 0.0


def test_the_tip_cannot_be_placed_where_a_cue_would_miscue():
    x, y = clamp_tip_offset(2.0, 0.0)
    assert math.isclose(x, SPIN_MAX_TIP_OFFSET) and y == 0.0

    x, y = clamp_tip_offset(1.0, 1.0)
    assert math.isclose(math.hypot(x, y), SPIN_MAX_TIP_OFFSET)

    cue = Cue()
    cue.set_tip(0.0, -3.0)
    assert math.isclose(cue.tip.y, -SPIN_MAX_TIP_OFFSET)
    cue.reset_tip()
    assert cue.tip.x == 0.0 and cue.tip.y == 0.0


def test_the_spin_dial_maps_its_edge_to_the_maximum_tip_offset():
    cx, cy = SPIN_DIAL_CENTER

    assert spin_from_pointer((cx, cy)) == (0.0, 0.0)

    # Straight up on the dial is top spin, because screen y grows downwards.
    _x, top = spin_from_pointer((cx, cy - SPIN_DIAL_RADIUS))
    assert math.isclose(top, SPIN_MAX_TIP_OFFSET)

    right, _y = spin_from_pointer((cx + SPIN_DIAL_RADIUS, cy))
    assert math.isclose(right, SPIN_MAX_TIP_OFFSET)


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
