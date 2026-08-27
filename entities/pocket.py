# =============================================================================
# pocket.py - Pocket entity: position, mouth width and capture radius.
#
# Six pockets sit at the corners and midpoints of the long rails.  The physics
# engine checks active balls against the capture radius, while cushion handling
# uses mouth_width to leave real openings between cushion jaws.
# =============================================================================

from dataclasses import dataclass
from typing import Optional

from utils.vector import Vec2
from utils.constants import (
    POCKET_CORNER_COLLISION_RADIUS,
    POCKET_CORNER_MOUTH_WIDTH,
    POCKET_CORNER_VISUAL_RADIUS,
    POCKET_SIDE_COLLISION_RADIUS,
    POCKET_SIDE_MOUTH_WIDTH,
    POCKET_SIDE_VISUAL_RADIUS,
)


@dataclass
class Pocket:
    """A single pocket on the pool table.

    Attributes
    ----------
    pos : Vec2
        Centre of the pocket hole in screen pixels.
    label : str
        Optional human-readable label (e.g. "TL" for top-left) used in
        debugging and tests.
    kind : str
        Either "corner" or "side"; used to choose standard pocket dimensions.
    mouth_width : float
        Width of the cushion opening in pixels.
    visual_radius : float
        Radius used when drawing the black circle.
    collision_radius : float
        Slightly larger radius used for physics detection so balls do not
        bounce off the invisible edge of a pocket mouth.
    """

    pos: Vec2
    label: str = ""
    kind: str = "corner"
    mouth_width: Optional[float] = None
    visual_radius: Optional[float] = None
    collision_radius: Optional[float] = None

    def __post_init__(self) -> None:
        if self.kind not in ("corner", "side"):
            raise ValueError(f"Invalid pocket kind: {self.kind}")

        if self.kind == "side":
            default_mouth = POCKET_SIDE_MOUTH_WIDTH
            default_visual = POCKET_SIDE_VISUAL_RADIUS
            default_collision = POCKET_SIDE_COLLISION_RADIUS
        else:
            default_mouth = POCKET_CORNER_MOUTH_WIDTH
            default_visual = POCKET_CORNER_VISUAL_RADIUS
            default_collision = POCKET_CORNER_COLLISION_RADIUS

        if self.mouth_width is None:
            self.mouth_width = default_mouth
        if self.visual_radius is None:
            self.visual_radius = default_visual
        if self.collision_radius is None:
            self.collision_radius = default_collision

    @property
    def mouth_half_width(self) -> float:
        """Half the playable opening between the cushion jaws."""
        return float(self.mouth_width) / 2.0

    def contains(self, ball_pos: Vec2) -> bool:
        """Return True if *ball_pos* is within the capture radius."""
        return ball_pos.distance_sq_to(self.pos) <= float(self.collision_radius) ** 2
