# =============================================================================
# main.py — Entry point for the 8-Ball Pool game.
#
# This file does the minimum needed to bootstrap pygame and hand control to
# the Game class.  All actual logic lives under the game/, physics/, ui/ and
# entities/ packages.
#
# How to run
# ----------
#   python main.py
#
# Requirements
# ------------
#   pip install pygame
# =============================================================================

import argparse
import sys
import pygame

from utils.constants import WINDOW_W, WINDOW_H, FPS
from game.game import Game


# Difficulty presets: (aim error in radians, candidate cap, think seconds).
# The aim error is what a player would call a miss; the other two decide how
# well the AI chooses which shot to attempt in the first place.
#
# The angles look absurdly small because an aiming error is levered up on its
# way to the pocket: the cue ball converts an error of theta at the cue into
# roughly theta * cue_distance / ball_diameter at the object ball, which is a
# factor of ten or more across a table. Measured pot rates on open positions,
# holding the intended shot fixed:
#
#     0.0000 rad -> 100%     0.0025 rad -> 61%
#     0.0006 rad ->  ~85%    0.0100 rad -> 35%
#
# Fouls stay under 4% even at the easy end, so a weaker setting misses pots
# rather than hacking the cue ball around the table.
AI_DIFFICULTIES = {
    "easy":    (0.0100, 20,  0.30),
    "medium":  (0.0025, 60,  0.60),
    "hard":    (0.0006, 140, 0.90),
    "perfect": (0.0000, 220, 1.40),
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 8-Ball Pool.")
    parser.add_argument(
        "--ai-player",
        type=int,
        choices=(1, 2),
        default=None,
        help="Let the selected player be controlled by the AI.",
    )
    parser.add_argument(
        "--ai-policy",
        default=None,
        help="Optional JSON policy produced by python -m ai.train.",
    )
    parser.add_argument(
        "--ai-difficulty",
        choices=sorted(AI_DIFFICULTIES),
        default="hard",
        help="How strong the AI plays.  Sets aim accuracy and search depth.",
    )
    parser.add_argument(
        "--ai-candidates",
        type=int,
        default=None,
        help="Override the difficulty's cap on candidate shots per decision.",
    )
    parser.add_argument(
        "--ai-think-time",
        type=float,
        default=None,
        help="Override the difficulty's search time per decision, in seconds.",
    )
    parser.add_argument(
        "--ai-delay",
        type=float,
        default=0.35,
        help="Seconds the AI waits before placing or shooting.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Initialise pygame, create the window, build the Game, and run it."""
    args = _parse_args(sys.argv[1:] if argv is None else argv)

    # Initialise all pygame modules (display, font, mixer, etc.)
    pygame.init()
    pygame.font.init()   # ensure font subsystem is ready

    # Set window title and icon hint
    pygame.display.set_caption("8-Ball Pool")

    # Create the main display surface
    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))

    # Clock for frame-rate control (returns elapsed ms per tick)
    clock = pygame.time.Clock()

    # Construct and run the game — this call blocks until the player quits
    ai_player_index = None if args.ai_player is None else args.ai_player - 1
    aim_noise, candidates, think_time = AI_DIFFICULTIES[args.ai_difficulty]
    if args.ai_candidates is not None:
        candidates = args.ai_candidates
    if args.ai_think_time is not None:
        think_time = args.ai_think_time

    game = Game(
        screen,
        clock,
        ai_player_index=ai_player_index,
        ai_policy_path=args.ai_policy,
        ai_candidate_count=candidates,
        ai_delay=args.ai_delay,
        ai_time_budget=think_time,
        ai_aim_noise=aim_noise,
    )
    game.run()

    # Clean up pygame resources before exiting
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
