# =============================================================================
# ball.py — Ball entity: position, velocity, state, group membership and color.
#
# Every ball on the table — including the cue ball — is an instance of Ball.
# The physics engine mutates pos, vel, spin and state directly.
# The rules engine reads group, number and pocketed.
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto

from utils.vector import Vec2
from utils.constants import BALL_RADIUS, BALL_COLORS


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class BallState(Enum):
    """Lifecycle state of a ball on the table."""
    ROLLING    = auto()   # Ball is moving (any speed above stop threshold)
    STATIONARY = auto()   # Ball has come to rest on the felt
    POCKETED   = auto()   # Ball has fallen into a pocket and is off the table


class BallGroup(Enum):
    """Which scoring group a ball belongs to.

    NONE  — not yet assigned (used for the cue ball before it's "free"
            or for numbered balls before group assignment).
    SOLID — balls 1–7 (solid colour, no stripe)
    EIGHT — ball 8 (the money ball)
    STRIPE— balls 9–15 (white base with a coloured stripe)
    CUE   — ball 0 (the white cue ball, never scored)
    """
    NONE   = auto()
    CUE    = auto()
    SOLID  = auto()
    EIGHT  = auto()
    STRIPE = auto()


def _group_for_number(number: int) -> BallGroup:
    """Return the natural group for a ball given its number."""
    if number == 0:
        return BallGroup.CUE
    if 1 <= number <= 7:
        return BallGroup.SOLID
    if number == 8:
        return BallGroup.EIGHT
    if 9 <= number <= 15:
        return BallGroup.STRIPE
    raise ValueError(f"Invalid ball number: {number}")


# ---------------------------------------------------------------------------
# Ball dataclass
# ---------------------------------------------------------------------------

@dataclass
class Ball:
    """A single pool ball.

    Attributes
    ----------
    number : int
        Official ball number: 0 = cue, 1-7 = solid, 8 = eight, 9-15 = stripe.
    pos : Vec2
        Centre position on the table in pixels.
    vel : Vec2
        Current velocity in pixels per second.
    spin : float
        Cumulative rotation angle in radians (for drawing the number rotated).
    radius : float
        Collision radius in pixels (all balls share BALL_RADIUS from constants).
    state : BallState
        Current motion state.
    group : BallGroup
        Scoring group this ball belongs to.
    color : tuple[int,int,int]
        Base RGB color used when drawing.
    pocketed : bool
        Convenience flag — True once the ball has been removed from play.
    roll : Vec2
        Rolling velocity: the speed the ball's contact patch would travel at
        if it were rolling without slipping.  The difference roll - vel is the
        slip the cloth works on, which is what makes a ball follow or draw.
        Only the cue ball ever carries a value that differs from vel.
    side_spin : float
        Spin about the vertical axis, as the surface speed at the ball's
        equator in px/s.  Positive spins the contact point counter-clockwise
        in screen coordinates.  Only the cue ball ever carries it.
    """

    number : int
    pos    : Vec2      = field(default_factory=Vec2)
    vel    : Vec2      = field(default_factory=Vec2)
    spin   : float     = 0.0
    radius : float     = BALL_RADIUS
    state  : BallState = BallState.STATIONARY
    group  : BallGroup = BallGroup.NONE
    color  : tuple     = field(default_factory=lambda: (200, 200, 200))
    pocketed: bool     = False
    roll     : Vec2    = field(default_factory=Vec2)
    side_spin: float   = 0.0

    def __post_init__(self):
        """Set group and color from ball number if not explicitly provided."""
        # Group assignment
        if self.group is BallGroup.NONE:
            self.group = _group_for_number(self.number)
        # Color lookup from constants
        if self.color == (200, 200, 200):   # still the placeholder default
            self.color = BALL_COLORS.get(self.number, (200, 200, 200))

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """True if the ball is still on the table (not pocketed)."""
        return not self.pocketed

    @property
    def is_moving(self) -> bool:
        """True if the ball is currently rolling / sliding."""
        return self.state == BallState.ROLLING

    @property
    def is_stripe(self) -> bool:
        """True for stripe balls (9-15) — used by the renderer."""
        return self.group == BallGroup.STRIPE

    @property
    def is_cue_ball(self) -> bool:
        """True if this is the white cue ball (number == 0)."""
        return self.number == 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def set_natural_roll(self) -> None:
        """Declare the ball to be rolling at its current velocity (no slip)."""
        self.roll = Vec2(self.vel.x, self.vel.y)

    @property
    def slip(self) -> Vec2:
        """Velocity of the contact patch relative to the cloth."""
        return self.roll - self.vel

    def stop(self):
        """Immediately halt the ball and mark it stationary."""
        self.vel = Vec2(0.0, 0.0)
        self.roll = Vec2(0.0, 0.0)
        self.side_spin = 0.0
        self.state = BallState.STATIONARY

    def pocket(self):
        """Mark the ball as pocketed and remove it from physics."""
        self.pocketed = True
        self.state    = BallState.POCKETED
        self.vel      = Vec2(0.0, 0.0)
        self.roll     = Vec2(0.0, 0.0)
        self.side_spin = 0.0

    def reset_for_placement(self):
        """Re-activate a pocketed cue ball for ball-in-hand placement."""
        self.pocketed = False
        self.state    = BallState.STATIONARY
        self.vel      = Vec2(0.0, 0.0)
        self.roll     = Vec2(0.0, 0.0)
        self.side_spin = 0.0

    def __repr__(self) -> str:
        return (f"Ball(#{self.number} {self.group.name} "
                f"pos={self.pos} vel={self.vel} {self.state.name})")
