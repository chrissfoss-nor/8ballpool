# =============================================================================
# pocket.py — Pocket entity: position and detection radius.
#
# Six pockets sit at the corners and midpoints of the long rails.
# The physics engine checks every active ball against every pocket each
# sub-step; when a ball's centre is within POCKET_COLLISION_RADIUS of a
# pocket centre it is removed from play.
# =============================================================================

from dataclasses import dataclass
from utils.vector import Vec2
from utils.constants import POCKET_VISUAL_RADIUS, POCKET_COLLISION_RADIUS


@dataclass
class Pocket:
    """A single pocket on the pool table.

    Attributes
    ----------
    pos : Vec2
        Centre of the pocket hole in screen pixels.
    visual_radius : float
        Radius used when drawing the black circle.
    collision_radius : float
        Slightly larger radius used for physics detection so pockets feel
        natural — balls don't bounce off the edge of the hole.
    label : str
        Optional human-readable label (e.g. "TL" for top-left) used in
        debugging and tests.
    """

    pos              : Vec2
    visual_radius    : float = POCKET_VISUAL_RADIUS
    collision_radius : float = POCKET_COLLISION_RADIUS
    label            : str   = ""

    def contains(self, ball_pos: Vec2) -> bool:
        """Return True if *ball_pos* is within the collision radius."""
        return ball_pos.distance_sq_to(self.pos) <= self.collision_radius ** 2
