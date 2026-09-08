# =============================================================================
# ball_collision.py — Elastic ball-ball collision resolution.
#
# Algorithm (equal-mass elastic collision with restitution)
# ---------------------------------------------------------
# 1.  Compute the displacement vector from ball_a to ball_b.
# 2.  If the distance is greater than the sum of radii there is no contact.
# 3.  Compute the unit collision normal  n = delta / dist.
# 4.  Compute relative velocity along the normal:
#         dv = (vel_a - vel_b) · n
#     If dv <= 0 the balls are already moving apart — skip.
# 5.  Apply impulse:
#         impulse = dv * (1 + e) / 2     (equal masses cancel out)
#     where e = RESTITUTION_BALL.
#         vel_a -= n * impulse
#         vel_b += n * impulse
# 6.  Positional correction: push the balls apart so they no longer overlap.
#     This prevents the "sinking balls" artefact that occurs when collisions
#     are resolved but positions are not corrected.
#
# The engine calls resolve_pair() for every unique (a, b) combination every
# sub-step.  With 16 balls that is at most 120 checks — entirely negligible.
# =============================================================================

from utils.vector import Vec2
from utils.constants import RESTITUTION_BALL
from entities.ball import Ball, BallState
from physics.spin import throw_off_side_spin


def resolve_pair(
    ball_a: Ball,
    ball_b: Ball,
    first_contact_callback=None,
) -> bool:
    """Resolve a potential collision between *ball_a* and *ball_b*.

    Parameters
    ----------
    ball_a, ball_b : Ball
        The two balls to test.  Both must be active (not pocketed).
    first_contact_callback : callable | None
        Optional callable(ball_a, ball_b) invoked on the FIRST contact
        during a shot.  The physics engine uses this to track which ball
        the cue ball touched first.

    Returns
    -------
    bool
        True if a collision was detected and resolved, False otherwise.
    """
    # ------------------------------------------------------------------
    # Skip pocketed balls
    # ------------------------------------------------------------------
    if ball_a.pocketed or ball_b.pocketed:
        return False

    # ------------------------------------------------------------------
    # Distance check
    #
    # This is the hot path: the engine calls resolve_pair() for every pair
    # every sub-step, and the overwhelming majority return here.  The check
    # is written against raw floats rather than Vec2 arithmetic so the common
    # "no contact" case allocates nothing at all.
    # ------------------------------------------------------------------
    pa = ball_a.pos
    pb = ball_b.pos
    dx = pb.x - pa.x
    dy = pb.y - pa.y
    dist_sq = dx * dx + dy * dy
    min_dist = ball_a.radius + ball_b.radius

    if dist_sq >= min_dist * min_dist:
        return False   # No contact

    delta = Vec2(dx, dy)                     # vector from a → b
    dist = dist_sq ** 0.5

    # ------------------------------------------------------------------
    # Degenerate case: balls are exactly on top of each other
    # (can happen during rack setup with tiny floating-point errors)
    # ------------------------------------------------------------------
    if dist < 1e-6:
        delta = Vec2(1.0, 0.0)
        dist  = 1.0

    # ------------------------------------------------------------------
    # Collision normal (unit vector from a towards b)
    # ------------------------------------------------------------------
    n = delta / dist

    # ------------------------------------------------------------------
    # Relative velocity along the collision normal
    # ------------------------------------------------------------------
    rel_vel = ball_a.vel - ball_b.vel
    dv = rel_vel.dot(n)

    # If dv <= 0 the balls are separating — no impulse needed
    if dv <= 0.0:
        # Still do positional correction if overlapping
        _correct_overlap(ball_a, ball_b, n, dist, min_dist)
        return True   # collision detected but already separating

    # ------------------------------------------------------------------
    # Notify the first-contact callback (used by PhysicsEngine)
    # ------------------------------------------------------------------
    if first_contact_callback is not None:
        first_contact_callback(ball_a, ball_b)

    # ------------------------------------------------------------------
    # Impulse (equal mass, so impulse is symmetric)
    # impulse = dv * (1 + e) / 2
    # ------------------------------------------------------------------
    impulse = dv * (1.0 + RESTITUTION_BALL) / 2.0

    ball_a.vel -= n * impulse
    ball_b.vel += n * impulse

    # ------------------------------------------------------------------
    # Spin.  The two balls are in contact for far too short a time for the
    # cloth to change how either of them is spinning, so the cue ball keeps
    # the roll it arrived with and now finds itself travelling at a different
    # speed — and that difference is the slip that makes it follow through a
    # ball or draw back off it.  An object ball is taken to roll naturally
    # from the instant it is struck, which leaves its path exactly what it
    # was before spin existed.
    # ------------------------------------------------------------------
    if ball_a.is_cue_ball:
        throw_off_side_spin(ball_a, ball_b, n)
    elif ball_b.is_cue_ball:
        throw_off_side_spin(ball_b, ball_a, -n)

    if not ball_a.is_cue_ball:
        ball_a.set_natural_roll()
    if not ball_b.is_cue_ball:
        ball_b.set_natural_roll()

    # Mark balls as rolling (they have non-zero velocity now)
    ball_a.state = BallState.ROLLING
    ball_b.state = BallState.ROLLING

    # ------------------------------------------------------------------
    # Positional correction — separate overlapping balls
    # ------------------------------------------------------------------
    _correct_overlap(ball_a, ball_b, n, dist, min_dist)

    return True


def _correct_overlap(
    ball_a: Ball,
    ball_b: Ball,
    n: Vec2,
    dist: float,
    min_dist: float,
) -> None:
    """Push ball_a and ball_b apart so they no longer overlap.

    Each ball is moved by half the overlap distance plus a tiny extra margin
    to prevent repeated micro-collisions.
    """
    overlap = min_dist - dist
    if overlap <= 0.0:
        return
    # Add 0.5 px extra so the balls are just barely separated
    correction = n * (overlap / 2.0 + 0.5)
    ball_a.pos -= correction
    ball_b.pos += correction
