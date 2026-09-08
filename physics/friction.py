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
#
# A cue ball carrying spin gets one extra step before any of that: the cloth
# works on the slip between where the ball is rolling and where it is going
# (physics/spin.py).  That step is a no-op for a ball that is already rolling,
# which is every object ball and every centre-ball cue shot, so the deceleration
# below is reached in exactly the state it always was.
# =============================================================================

from utils.vector import Vec2
from utils.constants import (
    GRAVITY,
    FRICTION_SLIDING, FRICTION_ROLLING,
    ROLLING_THRESHOLD, STOP_THRESHOLD,
)
from entities.ball import Ball, BallState
from physics.spin import advance_slip


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

    # -----------------------------------------------------------------------
    # Spin (cue ball only).  Does nothing unless the ball is slipping.
    # -----------------------------------------------------------------------
    slip = None
    sliding = False
    if ball.is_cue_ball:
        advance_slip(ball, dt)
        slip = ball.roll - ball.vel
        sliding = slip.length() >= STOP_THRESHOLD

    speed = ball.vel.length()

    # -----------------------------------------------------------------------
    # Stop condition
    #
    # A ball whose own spin is still driving it is not stopped, however slowly
    # its centre happens to be moving: that instant is the top of the arc of a
    # draw shot, not the end of it.
    # -----------------------------------------------------------------------
    if speed < STOP_THRESHOLD:
        if sliding:
            ball.state = BallState.ROLLING
            return
        ball.vel   = Vec2(0.0, 0.0)
        ball.roll  = Vec2(0.0, 0.0)
        ball.side_spin = 0.0
        ball.state = BallState.STATIONARY
        return

    # -----------------------------------------------------------------------
    # A ball that is still sliding has already paid the cloth this step: the
    # slip friction above *is* its deceleration, and charging it the rolling
    # drag as well would take the same friction twice and kill a draw shot
    # before it reached the object ball.
    # -----------------------------------------------------------------------
    if sliding:
        ball.state = BallState.ROLLING
        ball.spin += (speed * dt) / ball.radius
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
        if slip is not None:
            ball.roll = slip
            if slip.length() >= STOP_THRESHOLD:
                # Still spinning: it will set off again next sub-step.
                ball.state = BallState.ROLLING
    else:
        # Reduce speed along the current direction of travel
        new_speed  = speed - decel_magnitude
        ball.vel   = ball.vel.normalize() * new_speed
        ball.state = BallState.ROLLING
        if slip is not None:
            # Drag slows the ball, not the slip riding on it.
            ball.roll = ball.vel + slip

    # -----------------------------------------------------------------------
    # Visual spin update
    # Angular velocity ≈ translational speed / radius  (no-slip rolling)
    # We accumulate the total rotation angle so the renderer can draw the
    # ball number in the correct orientation.
    # -----------------------------------------------------------------------
    ball.spin += (speed * dt) / ball.radius   # radians
