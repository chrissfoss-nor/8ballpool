# =============================================================================
# test_mechanics.py - regression tests for shot power and pocket geometry.
#
# Run with:  python tests/test_mechanics.py
# =============================================================================

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

pygame.init()
pygame.font.init()

from entities.ball import Ball, BallState
from entities.cue import Cue
from entities.table import create_table
from game.game import Game
from game.shot_animation import ShotAnimation
from game.state_machine import GameState
from physics.cushion_collision import resolve_cushions_and_pockets
from ui.hud import get_power_bar_track_rect
from utils.constants import (
    BALL_DIAMETER,
    BALL_RADIUS,
    CUE_PULL_BASE,
    SHOT_AIM_HOLD_SECONDS,
    POCKET_CORNER_MOUTH_WIDTH,
    POCKET_SIDE_MOUTH_WIDTH,
    POWER_SCROLL_STEP,
    WINDOW_H,
    WINDOW_W,
)
from utils.vector import Vec2

_screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))


def _new_aiming_game():
    game = Game(_screen, pygame.time.Clock())
    game.show_break_prompt = False
    game.is_break = False
    game.state = GameState.PLAYER_AIMING
    return game


def test_cue_power_setter_clamps_and_zero_has_no_impulse():
    cue = Cue()

    cue.set_power(1.25)
    assert cue.power == 1.0

    cue.set_power(-0.25)
    assert cue.power == 0.0
    assert cue.get_shot_vector().length() == 0.0

    cue.on_scroll(1)
    assert math.isclose(cue.power, POWER_SCROLL_STEP)


def test_power_bar_click_sets_power_without_shooting():
    game = _new_aiming_game()
    track = get_power_bar_track_rect()
    target_x = track.left + track.width * 0.75

    event = pygame.event.Event(
        pygame.MOUSEBUTTONDOWN,
        {"button": 1, "pos": (target_x, track.centery)},
    )
    game._handle_mouse_down(event)

    assert game._power_dragging
    assert game.state == GameState.PLAYER_AIMING
    assert math.isclose(game.cue.power, 0.75, abs_tol=0.01)


def test_zero_power_does_not_start_a_shot():
    game = _new_aiming_game()
    cue_ball = next(ball for ball in game.balls if ball.is_cue_ball)

    game.cue.set_power(0.0)
    game._execute_shot()

    assert game.state == GameState.PLAYER_AIMING
    assert cue_ball.state == BallState.STATIONARY
    assert cue_ball.vel.length() == 0.0


def test_the_cue_draws_back_before_it_strikes_and_the_ball_waits():
    """The wind-up has to move the cue and leave the ball alone until it lands."""
    game = _new_aiming_game()
    cue_ball = next(ball for ball in game.balls if ball.is_cue_ball)
    game.cue.set_power(0.8)

    game._execute_shot()
    assert game.state == GameState.PLAYER_AIMING, "the shot must not fire on the click"

    furthest_back = 0.0
    frames = 0
    while game.state == GameState.PLAYER_AIMING and frames < 300:
        assert cue_ball.vel.length() == 0.0, "the ball moved before the tip reached it"
        furthest_back = max(furthest_back, game.cue.pullback)
        game._update(1 / 60.0)
        frames += 1

    assert game.state == GameState.BALLS_MOVING, "the cue never struck the ball"
    assert furthest_back > CUE_PULL_BASE, (
        f"the cue barely moved: {furthest_back:.1f} px"
    )
    assert cue_ball.vel.length() > 0.0
    assert game.cue.pullback == 0.0, "the cue should be back at rest after the strike"


def test_a_second_click_during_the_wind_up_is_ignored():
    """Once the cue is moving the shot is committed: aim and power are locked."""
    game = _new_aiming_game()
    game.cue.set_power(0.5)
    game._execute_shot()

    game._update(1 / 60.0)
    committed = game._shot_anim

    # Routed through the real event handler: the lock lives in the input
    # gating, not in the cue itself.
    game._handle_event(pygame.event.Event(pygame.MOUSEWHEEL, {"y": 1, "x": 0}))
    game._handle_left_click((600, 400))

    assert game._shot_anim is committed, "the second click started another shot"
    assert math.isclose(game.cue.power, 0.5), "power changed after the shot was committed"


def test_the_ai_holds_its_aim_before_drawing_back():
    """The hold is the whole point: it is when you can read where it aims."""
    held = ShotAnimation(0.6, reach=10.0, aim_hold=SHOT_AIM_HOLD_SECONDS)
    held.update(SHOT_AIM_HOLD_SECONDS * 0.5)
    assert held.offset == 0.0, "the cue should sit still on the line while holding"

    # Your own shots skip it -- you have been aiming down that line already.
    own = ShotAnimation(0.6, reach=10.0, aim_hold=0.0)
    own.update(0.01)
    assert own.offset > 0.0, "your own shot should start drawing back at once"

    assert held.total_seconds > own.total_seconds


def test_the_tip_finishes_on_the_ball_not_short_of_it():
    """The strike ends where the ball is, whatever the power was."""
    for power in (0.1, 0.5, 1.0):
        reach = 30.0
        anim = ShotAnimation(power, reach=reach, aim_hold=0.0)
        anim.update(anim.total_seconds)
        assert anim.struck
        assert math.isclose(anim.offset, -reach), (
            f"power {power}: tip stopped at {anim.offset:.1f}, wanted {-reach:.1f}"
        )


def test_pocket_mouths_use_standard_ball_relative_sizes():
    table = create_table()
    corner = next(pocket for pocket in table.pockets if pocket.label == "TL")
    side = next(pocket for pocket in table.pockets if pocket.label == "TM")

    assert math.isclose(corner.mouth_width, POCKET_CORNER_MOUTH_WIDTH)
    assert math.isclose(side.mouth_width, POCKET_SIDE_MOUTH_WIDTH)
    assert math.isclose(corner.mouth_width, BALL_DIAMETER * 2.0)
    assert side.mouth_width > corner.mouth_width


def test_side_pocket_is_open_but_normal_rail_still_bounces():
    table = create_table()
    side = next(pocket for pocket in table.pockets if pocket.label == "TM")

    potted = Ball(
        number=1,
        pos=Vec2(side.pos.x, table.top + BALL_RADIUS),
        vel=Vec2(0.0, -300.0),
        state=BallState.ROLLING,
    )
    resolve_cushions_and_pockets(potted, table)
    assert potted.pocketed

    rail_ball = Ball(
        number=2,
        pos=Vec2(side.pos.x + side.mouth_half_width + BALL_DIAMETER, table.top + BALL_RADIUS - 2),
        vel=Vec2(0.0, -300.0),
        state=BallState.ROLLING,
    )
    resolve_cushions_and_pockets(rail_ball, table)
    assert not rail_ball.pocketed
    assert rail_ball.pos.y == table.top + BALL_RADIUS
    assert rail_ball.vel.y > 0.0


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
