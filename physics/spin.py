# =============================================================================
# spin.py — Cue-ball spin: where it comes from, what it does, how it dies.
#
# A ball has two motions that matter here: the velocity of its centre and the
# velocity its contact patch would have if it were rolling without slipping.
# The difference between them is *slip*, and slip is the whole story:
#
#   slip = roll - vel
#
#   slip == 0   the ball is rolling; nothing to do
#   slip  > 0   top spin, the cloth drags the ball forward   (follow)
#   slip  < 0   back spin, the cloth drags the ball backward (draw)
#
# Cloth friction pushes the centre of mass along the slip and kills the slip
# itself 3.5x faster, which is the standard result for a solid sphere and the
# reason a stunned ball settles into a roll instead of skidding for ever.
# After a full-ball collision the cue ball keeps the roll it arrived with —
# the balls touch for far too short a time for the cloth to change it — so a
# ball struck high rolls on through the contact and one struck low comes back.
# That conservation is what makes position play possible at all.
#
# Side spin is kept separately, as the surface speed at the ball's equator.
# It survives contact with things rather than with the cloth: it throws an
# object ball off the aiming line, and it kicks the cue ball sideways out of a
# cushion.
#
# Only the cue ball carries any of this.  It is the only ball a tip touches,
# and an object ball is taken to acquire natural roll the moment it is struck,
# which keeps every object-ball path identical to what it was before spin
# existed.
# =============================================================================

from utils.vector import Vec2
from utils.constants import (
    GRAVITY,
    FRICTION_SLIDING,
    STOP_THRESHOLD,
    SPIN_MAX_TIP_OFFSET,
    SPIN_FOLLOW_GAIN,
    SPIN_DRAW_GAIN,
    SPIN_SIDE_GAIN,
    SPIN_SLIP_RATIO,
    SPIN_SIDE_DECAY,
    CUSHION_ROLL_RETENTION,
    CUSHION_SPIN_RETENTION,
    CUSHION_SPIN_GAIN,
    SPIN_THROW_GAIN,
    SPIN_THROW_RETENTION,
)
from entities.ball import Ball, BallState


# ---------------------------------------------------------------------------
# Tip offset
# ---------------------------------------------------------------------------

def clamp_tip_offset(tip_x: float, tip_y: float) -> tuple[float, float]:
    """Clamp a tip offset to the part of the ball a cue can actually strike.

    The offset is measured in ball radii from the centre: +x is the right-hand
    side of the ball seen from behind the shot, +y is above centre.  Past
    SPIN_MAX_TIP_OFFSET a real tip slides off the ball and miscues, so the
    length is clamped rather than the components — the limit is a circle.
    """
    length_sq = tip_x * tip_x + tip_y * tip_y
    limit = SPIN_MAX_TIP_OFFSET
    if length_sq <= limit * limit:
        return (tip_x, tip_y)
    scale = limit / (length_sq ** 0.5)
    return (tip_x * scale, tip_y * scale)


def apply_cue_strike(
    ball: Ball,
    velocity: Vec2,
    tip_x: float = 0.0,
    tip_y: float = 0.0,
) -> None:
    """Send *ball* off at *velocity*, with the spin a tip at that offset gives.

    A centre-ball hit (0, 0) leaves the ball rolling naturally, which is what
    every shot did before spin existed, so nothing about a centre-ball shot
    changes.
    """
    tip_x, tip_y = clamp_tip_offset(tip_x, tip_y)
    speed = velocity.length()

    ball.vel = Vec2(velocity.x, velocity.y)
    gain = SPIN_FOLLOW_GAIN if tip_y >= 0.0 else SPIN_DRAW_GAIN
    ball.roll = velocity * (1.0 + gain * tip_y)
    ball.side_spin = -SPIN_SIDE_GAIN * tip_x * speed
    ball.state = BallState.ROLLING


# ---------------------------------------------------------------------------
# Cloth
# ---------------------------------------------------------------------------

def advance_slip(ball: Ball, dt: float) -> None:
    """Let the cloth work on the ball's slip for *dt* seconds.

    Returns immediately for a ball that is already rolling, which is every
    ball on the table except a cue ball that has been given spin or has just
    come off a collision.
    """
    if ball.side_spin:
        decay = 1.0 - SPIN_SIDE_DECAY * dt
        ball.side_spin = ball.side_spin * decay if decay > 0.0 else 0.0

    slip = ball.roll - ball.vel
    slip_speed = slip.length()
    if slip_speed < STOP_THRESHOLD:
        ball.set_natural_roll()
        return

    # Speed the centre of mass picks up from the cloth over this step.  The
    # slip itself dies SPIN_SLIP_RATIO times faster.
    gain = FRICTION_SLIDING * GRAVITY * dt

    if gain * SPIN_SLIP_RATIO >= slip_speed:
        # The slip runs out inside this step, so land exactly on the rolling
        # velocity the two would have met at: v = (5 * vel + 2 * roll) / 7.
        # A ball sliding with no spin at all therefore settles into a roll at
        # five sevenths of its speed, which is the textbook answer.
        rolling = (ball.vel * 5.0 + ball.roll * 2.0) / 7.0
        ball.vel = rolling
        ball.set_natural_roll()
    else:
        direction = slip / slip_speed
        ball.vel = ball.vel + direction * gain
        ball.roll = ball.roll - direction * (gain * (SPIN_SLIP_RATIO - 1.0))

    ball.state = BallState.ROLLING


# ---------------------------------------------------------------------------
# Contact with other things
# ---------------------------------------------------------------------------

def throw_off_side_spin(cue_ball: Ball, object_ball: Ball, normal: Vec2) -> None:
    """Throw *object_ball* off the aiming line with the cue ball's side spin.

    *normal* is the unit vector from the cue ball's centre to the object
    ball's.  The cue ball's surface is sweeping across the contact point, and
    the friction that rubs the object ball sideways pushes the cue ball the
    other way by the same amount.
    """
    spin = cue_ball.side_spin
    if not spin:
        return
    tangent = Vec2(-normal.y, normal.x)
    kick = tangent * (SPIN_THROW_GAIN * spin)
    object_ball.vel += kick
    cue_ball.vel -= kick
    cue_ball.side_spin = spin * SPIN_THROW_RETENTION


def bounce_spin_off_cushion(ball: Ball, normal: Vec2) -> None:
    """Take *ball* out of a cushion carrying only part of the spin it brought.

    Call this after the velocity has been reflected; *normal* points away from
    the cushion, into the table.

    A rail is rubber, not cloth: it grips the ball hard enough that what comes
    out is mostly a ball rolling naturally again.  Only the deviation from
    natural roll survives, reflected and damped — which is also what keeps a
    rolling ball from absurdly driving itself back into the rail it just left.
    Side spin survives better, and pushes the ball along the cushion as it
    leaves: running english widens the angle, reverse english tightens it.
    """
    slip = ball.roll - ball.vel
    ball.roll = ball.vel + slip.reflect(normal) * CUSHION_ROLL_RETENTION

    spin = ball.side_spin
    if not spin:
        return
    kick = Vec2(-normal.y, normal.x) * (CUSHION_SPIN_GAIN * spin)
    ball.vel += kick
    ball.roll += kick          # the kick moves the ball, not its slip
    ball.side_spin = spin * CUSHION_SPIN_RETENTION
