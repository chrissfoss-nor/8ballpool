# =============================================================================
# cue.py — The cue stick: angle, power, shot vector and rendering.
#
# The player controls the cue via the mouse:
#   • Moving the mouse sets the aim angle.
#   • Scrolling the mouse wheel changes power.
#   • Holding right-click and dragging also changes power.
#   • Left-clicking fires the shot.
#
# The Cue object is stateless between shots (angle and power reset after
# every shot) and only exists while the player is in PLAYER_AIMING state.
# =============================================================================

import math
import pygame

from utils.vector import Vec2
from utils.constants import (
    MAX_SHOT_IMPULSE, MIN_SHOT_IMPULSE,
    POWER_DRAG_DISTANCE,
    CUE_LENGTH, CUE_WIDTH_BASE, CUE_WIDTH_TIP, CUE_GAP_BASE, CUE_GAP_POWER,
    COLOR_WOOD, COLOR_TEXT,
)


class Cue:
    """Represents the player's cue stick.

    Attributes
    ----------
    angle : float
        Current aim angle in radians (measured from +x axis, CCW positive).
        Points FROM the cue ball TOWARDS where the player wants to hit.
    power : float
        Shot strength in [0.0, 1.0].  0 = min impulse, 1 = max impulse.
    visible : bool
        Whether to draw the cue.  Hidden while balls are moving.
    _drag_start : Vec2 | None
        Mouse position when right-click drag began (for power control).
    _drag_start_power : float
        Power value at the moment the right-click drag started.
    """

    def __init__(self):
        self.angle            : float        = 0.0
        self.power            : float        = 0.5      # default half power
        self.visible          : bool         = False
        self._drag_start      : Vec2 | None  = None
        self._drag_start_power: float        = 0.5

    # ------------------------------------------------------------------
    # Input handlers  (called by game.py event loop)
    # ------------------------------------------------------------------

    def on_mouse_move(self, mouse_pos: tuple, cue_ball_pos: Vec2):
        """Update aim angle based on current mouse position."""
        dx = mouse_pos[0] - cue_ball_pos.x
        dy = mouse_pos[1] - cue_ball_pos.y
        self.angle = math.atan2(dy, dx)

    def on_scroll(self, direction: int):
        """Adjust power with scroll wheel.

        *direction* is +1 for scroll-up (more power) and -1 for scroll-down.
        """
        self.power = max(0.0, min(1.0, self.power + direction * 0.05))

    def start_drag(self, mouse_pos: tuple):
        """Begin a right-click drag to adjust power."""
        self._drag_start       = Vec2(mouse_pos[0], mouse_pos[1])
        self._drag_start_power = self.power

    def update_drag(self, mouse_pos: tuple, cue_ball_pos: Vec2):
        """Update power based on how far the mouse has been dragged away.

        The drag direction is *away* from the cue ball (pulling the cue back).
        """
        if self._drag_start is None:
            return
        # Compute how far the mouse has moved from the drag start point
        current = Vec2(mouse_pos[0], mouse_pos[1])
        # Distance from cue ball in the direction opposite the shot
        shot_dir = Vec2(math.cos(self.angle), math.sin(self.angle))
        drag_vec = current - self._drag_start
        # Project drag onto the *backwards* direction to get pull distance
        pull = -drag_vec.dot(shot_dir)
        delta_power = pull / POWER_DRAG_DISTANCE
        self.power = max(0.0, min(1.0, self._drag_start_power + delta_power))

    def end_drag(self):
        """End the right-click drag."""
        self._drag_start = None

    def reset(self):
        """Reset cue state for a new turn."""
        self.power   = 0.5
        self.visible = False
        self._drag_start = None

    # ------------------------------------------------------------------
    # Shot vector
    # ------------------------------------------------------------------

    def get_shot_vector(self) -> Vec2:
        """Return the velocity impulse to apply to the cue ball.

        The magnitude is linearly interpolated between MIN and MAX impulse
        based on the current power value.
        """
        speed = MIN_SHOT_IMPULSE + self.power * (MAX_SHOT_IMPULSE - MIN_SHOT_IMPULSE)
        return Vec2(math.cos(self.angle) * speed, math.sin(self.angle) * speed)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface, cue_ball_pos: Vec2):
        """Draw the cue stick on *surface*.

        The stick is a trapezoid (wider at the butt, narrower at the tip)
        drawn along the aim angle, starting with a gap from the cue ball.
        The gap increases with power so it looks like the cue is being
        pulled back.
        """
        if not self.visible:
            return

        # Gap between cue tip and ball centre (increases with power)
        gap = CUE_GAP_BASE + self.power * CUE_GAP_POWER

        # Direction unit vectors
        dx = math.cos(self.angle)
        dy = math.sin(self.angle)

        # Cue tip position (near the ball)
        tip_x = cue_ball_pos.x - dx * gap
        tip_y = cue_ball_pos.y - dy * gap

        # Cue butt position (far from the ball)
        butt_x = cue_ball_pos.x - dx * (gap + CUE_LENGTH)
        butt_y = cue_ball_pos.y - dy * (gap + CUE_LENGTH)

        # Perpendicular unit vector (for width)
        perp_x = -dy
        perp_y =  dx

        # Half-widths at each end
        hw_tip  = CUE_WIDTH_TIP  / 2
        hw_butt = CUE_WIDTH_BASE / 2

        # Four corners of the cue trapezoid
        pts = [
            (tip_x  + perp_x * hw_tip,  tip_y  + perp_y * hw_tip),
            (tip_x  - perp_x * hw_tip,  tip_y  - perp_y * hw_tip),
            (butt_x - perp_x * hw_butt, butt_y - perp_y * hw_butt),
            (butt_x + perp_x * hw_butt, butt_y + perp_y * hw_butt),
        ]

        # Draw filled cue body (wood color)
        pygame.draw.polygon(surface, COLOR_WOOD, pts)

        # Draw a thin dark outline for definition
        pygame.draw.polygon(surface, (40, 20, 10), pts, 1)

        # Draw a white tip highlight at the narrow end
        tip_pts = [
            (tip_x + perp_x * hw_tip, tip_y + perp_y * hw_tip),
            (tip_x - perp_x * hw_tip, tip_y - perp_y * hw_tip),
            (tip_x - dx * 6 - perp_x * hw_tip, tip_y - dy * 6 - perp_y * hw_tip),
            (tip_x - dx * 6 + perp_x * hw_tip, tip_y - dy * 6 + perp_y * hw_tip),
        ]
        pygame.draw.polygon(surface, (220, 220, 180), tip_pts)
