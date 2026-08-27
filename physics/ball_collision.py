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
    # ------------------------------------------------------------------
    delta = ball_b.pos - ball_a.pos          # vector from a → b
    dist_sq = delta.length_sq()
    min_dist = ball_a.radius + ball_b.radius

    if dist_sq >= min_dist * min_dist:
        return False   # No contact

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
