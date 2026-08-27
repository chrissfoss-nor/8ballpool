# =============================================================================
# friction.py — Two-phase friction model for pool balls.
#
# Phase 1 — Sliding friction  (high deceleration, right after a cue hit or
#            cushion bounce where the ball is skidding fast).
# Phase 2 — Rolling friction  (low deceleration, once the ball has slowed
#            to the rolling threshold).
#
# Both phases use a simple linear deceleration:
#   friction_magnitude = coefficient * GRAVITY * dt
# If that would reduce speed below zero the ball stops exactly.
#
# Visual spin (for rotating the number label on each ball) is also updated
# here: spin angle grows at a rate proportional to rolling speed / radius.
# =============================================================================

from utils.vector import Vec2
from utils.constants import (
    GRAVITY,
    FRICTION_SLIDING, FRICTION_ROLLING,
    ROLLING_THRESHOLD, STOP_THRESHOLD,
)
from entities.ball import Ball, BallState


def apply_friction(ball: Ball, dt: float) -> None:
    """Apply rolling/sliding friction to *ball* over time step *dt* seconds.

    Mutates ball.vel, ball.spin and ball.state in place.

    Parameters
    ----------
    ball : Ball
        The ball to update.
    dt : float
        Duration of this physics sub-step in seconds.
    """
    # Skip balls that are already stopped or pocketed
    if ball.state in (BallState.STATIONARY, BallState.POCKETED):
        return

    speed = ball.vel.length()

    # -----------------------------------------------------------------------
    # Stop condition
    # -----------------------------------------------------------------------
    if speed < STOP_THRESHOLD:
        ball.vel   = Vec2(0.0, 0.0)
        ball.state = BallState.STATIONARY
        return

    # -----------------------------------------------------------------------
    # Choose friction coefficient based on current speed
    # -----------------------------------------------------------------------
    if speed > ROLLING_THRESHOLD:
        # Sliding / skidding phase — high deceleration
        coeff = FRICTION_SLIDING
    else:
        # Rolling phase — gentler deceleration
        coeff = FRICTION_ROLLING

    # -----------------------------------------------------------------------
    # Apply deceleration
    # Deceleration magnitude = coeff * GRAVITY  (in px/s²)
    # Over dt seconds the speed reduces by: coeff * GRAVITY * dt
    # -----------------------------------------------------------------------
    decel_magnitude = coeff * GRAVITY * dt

    if decel_magnitude >= speed:
        # Friction would overshoot zero — just stop
        ball.vel   = Vec2(0.0, 0.0)
        ball.state = BallState.STATIONARY
    else:
        # Reduce speed along the current direction of travel
        new_speed  = speed - decel_magnitude
        ball.vel   = ball.vel.normalize() * new_speed
        ball.state = BallState.ROLLING

    # -----------------------------------------------------------------------
    # Visual spin update
    # Angular velocity ≈ translational speed / radius  (no-slip rolling)
    # We accumulate the total rotation angle so the renderer can draw the
    # ball number in the correct orientation.
    # -----------------------------------------------------------------------
    ball.spin += (speed * dt) / ball.radius   # radians
