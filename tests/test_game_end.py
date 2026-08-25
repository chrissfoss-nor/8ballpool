# =============================================================================
# test_game_end.py — end-to-end tests for how a game finishes.
#
# These drive the real Game object: they set up a table, fire a real shot and
# step the real physics until the balls stop, then check the state machine
# landed where 8-ball rules say it should. Random play reaches a finished game
# only rarely, so the endings are worth pinning down directly.
#
# Run with:  python tests/test_game_end.py
# =============================================================================

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import math
import pygame

pygame.init()
pygame.font.init()

from utils.constants     import WINDOW_W, WINDOW_H, BALL_RADIUS
_screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))

from entities.ball       import BallGroup
from game.game           import Game
from game.state_machine  import GameState
from utils.vector        import Vec2


def _new_game():
    game = Game(_screen, pygame.time.Clock())
    game.show_break_prompt = False
    game.is_break = False
    game.state = GameState.PLAYER_AIMING
    return game


def _ball(game, number):
    return next(b for b in game.balls if b.number == number)


def _line_up_on_a_corner_pocket(game, number):
    """Put ball *number* just off a corner pocket with the cue ball behind it.

    Returns the angle to shoot at. The cue ball sits on the line running from
    the pocket through the object ball, so a straight firm shot sends the
    object ball into the pocket.
    """
    pocket = min(
        game.table.pockets,
        key=lambda p: (p.pos.x - game.table.left) ** 2 + (p.pos.y - game.table.top) ** 2,
    )
    target = _ball(game, number)

    # Aim down the diagonal running out of that pocket
    ux, uy = math.cos(math.pi / 4), math.sin(math.pi / 4)
    target.pos = Vec2(pocket.pos.x + ux * BALL_RADIUS * 4,
                      pocket.pos.y + uy * BALL_RADIUS * 4)
    target.vel = Vec2(0.0, 0.0)

    cue = _ball(game, 0)
    cue.pos = Vec2(target.pos.x + ux * BALL_RADIUS * 9,
                   target.pos.y + uy * BALL_RADIUS * 9)
    cue.vel = Vec2(0.0, 0.0)

    # Park every other ball far away so nothing interferes
    for ball in game.balls:
        if ball.number in (0, number) or ball.pocketed:
            continue
        ball.pocketed = True

    return math.atan2(pocket.pos.y - cue.pos.y, pocket.pos.x - cue.pos.x)


def _shoot(game, angle, power=0.5):
    game.cue.angle = angle
    game.cue.power = power
    game._execute_shot()
    frames = 0
    while game.state == GameState.BALLS_MOVING and frames < 3000:
        game._update(1 / 60.0)
        frames += 1
    assert frames < 3000, "balls never came to rest"


def test_potting_the_8_after_clearing_your_group_wins():
    game = _new_game()
    game.turns.assign_groups(BallGroup.SOLID)
    shooter = game.turns.current_name

    for n in range(1, 8):                    # every solid already down
        _ball(game, n).pocketed = True
    angle = _line_up_on_a_corner_pocket(game, 8)
    _shoot(game, angle)

    assert _ball(game, 8).pocketed, "the 8 ball should have dropped"
    assert game.state == GameState.GAME_OVER, f"expected GAME_OVER, got {game.state}"
    assert game.winner_name == shooter, (
        f"{shooter} cleared their group and potted the 8, so they should win; "
        f"winner was {game.winner_name!r}"
    )
    assert not game.loss_reason, f"unexpected loss reason: {game.loss_reason!r}"


def test_potting_the_8_early_loses():
    game = _new_game()
    game.turns.assign_groups(BallGroup.SOLID)
    shooter  = game.turns.current_name
    opponent = game.turns.opponent_name

    # Solids 1-6 down, the 7 still on the table, so the group is not cleared
    for n in range(1, 7):
        _ball(game, n).pocketed = True
    angle = _line_up_on_a_corner_pocket(game, 8)
    _ball(game, 7).pocketed = False
    _ball(game, 7).pos = Vec2(game.table.right - 60, game.table.bottom - 60)
    _shoot(game, angle)

    assert _ball(game, 8).pocketed, "the 8 ball should have dropped"
    assert game.state == GameState.GAME_OVER, f"expected GAME_OVER, got {game.state}"
    assert game.winner_name == opponent, (
        f"{shooter} potted the 8 with a solid still up, so {opponent} should win; "
        f"winner was {game.winner_name!r}"
    )
    assert game.loss_reason, "a loss should carry a reason to show the players"


def test_opponent_clearing_your_group_still_lets_you_win():
    """The bug this guards: balls the opponent pots for you must still count."""
    game = _new_game()
    game.turns.assign_groups(BallGroup.SOLID)
    shooter = game.turns.current_name

    for n in range(1, 8):
        _ball(game, n).pocketed = True
    # Credit them all to the opponent's tally, as if they had potted them
    game.turns.current.pocketed_balls = []

    angle = _line_up_on_a_corner_pocket(game, 8)
    _shoot(game, angle)

    assert game.state == GameState.GAME_OVER
    assert game.winner_name == shooter, (
        "a player whose group was cleared by the opponent must still be able to win"
    )


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
