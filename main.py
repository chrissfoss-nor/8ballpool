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

import sys
import pygame

from utils.constants import WINDOW_W, WINDOW_H, FPS
from game.game import Game


def main() -> None:
    """Initialise pygame, create the window, build the Game, and run it."""

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
    game = Game(screen, clock)
    game.run()

    # Clean up pygame resources before exiting
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
