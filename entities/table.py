# =============================================================================
# table.py — Pool table geometry: felt rect, six pockets, cushion boundaries.
#
# The Table is a passive data container.  It is constructed once at game start
# and never mutated.  The physics engine reads cushion boundaries from it;
# the renderer draws the table using the same geometry.
#
# Coordinate system
# -----------------
#   (0,0) is the top-left corner of the window.
#   x increases to the right, y increases downwards (pygame convention).
#
# Felt rect corners
# -----------------
#   top-left  : (TABLE_OFFSET_X,           TABLE_OFFSET_Y)
#   top-right : (TABLE_OFFSET_X + TABLE_W, TABLE_OFFSET_Y)
#   etc.
# =============================================================================

import pygame
from dataclasses import dataclass, field
from typing import List

from utils.vector import Vec2
from utils.constants import (
    TABLE_OFFSET_X, TABLE_OFFSET_Y, TABLE_W, TABLE_H,
    CUSHION_THICKNESS, WOOD_THICKNESS,
)
from entities.pocket import Pocket


@dataclass
class Table:
    """Immutable geometry of the pool table.

    Attributes
    ----------
    felt_rect : pygame.Rect
        The inner green playing surface (inside the cushions).
    pockets : List[Pocket]
        All six pockets in order: TL, TM, TR, BL, BM, BR.
    cushion_rect : pygame.Rect
        The rectangle that includes the cushion band (felt + cushion thickness).
        Balls must remain inside this rectangle; hitting the boundary triggers
        a cushion reflection.
    wood_rect : pygame.Rect
        Outer wooden border (visual only, not used in physics).
    """

    felt_rect    : pygame.Rect
    cushion_rect : pygame.Rect
    wood_rect    : pygame.Rect
    pockets      : List[Pocket] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Convenience geometry helpers
    # ------------------------------------------------------------------

    @property
    def left(self) -> float:
        """Left edge of the playable felt area."""
        return float(self.felt_rect.left)

    @property
    def right(self) -> float:
        """Right edge of the playable felt area."""
        return float(self.felt_rect.right)

    @property
    def top(self) -> float:
        """Top edge of the playable felt area."""
        return float(self.felt_rect.top)

    @property
    def bottom(self) -> float:
        """Bottom edge of the playable felt area."""
        return float(self.felt_rect.bottom)

    @property
    def center(self) -> Vec2:
        """Centre of the felt area."""
        return Vec2(self.felt_rect.centerx, self.felt_rect.centery)

    @property
    def head_x(self) -> float:
        """X coordinate of the head spot (1/4 from left — cue ball start zone)."""
        return self.left + TABLE_W * 0.25

    @property
    def foot_x(self) -> float:
        """X coordinate of the foot spot (3/4 from left — rack apex)."""
        return self.left + TABLE_W * 0.75

    @property
    def head_string_x(self) -> float:
        """X coordinate of the head string.

        On break, or after a scratch during the break, the incoming player
        places the cue ball anywhere to the *left* of (behind) this line.
        """
        return self.head_x


# ---------------------------------------------------------------------------
# Factory function — build the standard table
# ---------------------------------------------------------------------------

def create_table() -> Table:
    """Construct and return the standard 8-ball pool table geometry.

    The six pocket positions are placed at the four corners and the two
    mid-rail positions on the long sides.  Pocket centres are slightly
    *outside* the felt rect corners so they look natural.
    """
    # The felt area (inside the cushions)
    felt_rect = pygame.Rect(TABLE_OFFSET_X, TABLE_OFFSET_Y, TABLE_W, TABLE_H)

    # The cushion boundary (where balls bounce)
    cushion_rect = pygame.Rect(
        TABLE_OFFSET_X - CUSHION_THICKNESS,
        TABLE_OFFSET_Y - CUSHION_THICKNESS,
        TABLE_W + CUSHION_THICKNESS * 2,
        TABLE_H + CUSHION_THICKNESS * 2,
    )

    # The outer wooden border (visual only)
    wood_rect = pygame.Rect(
        TABLE_OFFSET_X - CUSHION_THICKNESS - WOOD_THICKNESS,
        TABLE_OFFSET_Y - CUSHION_THICKNESS - WOOD_THICKNESS,
        TABLE_W + (CUSHION_THICKNESS + WOOD_THICKNESS) * 2,
        TABLE_H + (CUSHION_THICKNESS + WOOD_THICKNESS) * 2,
    )

    # Pocket positions — corners sit just inside the cushion band
    fx = float(felt_rect.left)
    fy = float(felt_rect.top)
    fw = float(felt_rect.width)
    fh = float(felt_rect.height)

    pockets = [
        Pocket(Vec2(fx,        fy),            label="TL", kind="corner"),
        Pocket(Vec2(fx + fw/2, fy),            label="TM", kind="side"),
        Pocket(Vec2(fx + fw,   fy),            label="TR", kind="corner"),
        Pocket(Vec2(fx,        fy + fh),        label="BL", kind="corner"),
        Pocket(Vec2(fx + fw/2, fy + fh),       label="BM", kind="side"),
        Pocket(Vec2(fx + fw,   fy + fh),        label="BR", kind="corner"),
    ]

    return Table(
        felt_rect    = felt_rect,
        cushion_rect = cushion_rect,
        wood_rect    = wood_rect,
        pockets      = pockets,
    )
