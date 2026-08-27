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
from game.state_machine import GameState
from physics.cushion_collision import resolve_cushions_and_pockets
from ui.hud import get_power_bar_track_rect
from utils.constants import (
    BALL_DIAMETER,
    BALL_RADIUS,
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
