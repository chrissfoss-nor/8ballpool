# =============================================================================
# cushion_collision.py — Ball-cushion reflection and pocket detection.
#
# The four cushion walls are treated as axis-aligned boundaries defined by
# the felt rect in Table.  When a ball's edge crosses a boundary:
#   1. The perpendicular velocity component is reversed (reflection).
#   2. Energy is removed via RESTITUTION_CUSHION.
#   3. The ball is pushed back inside the boundary.
#   4. The cushion-contact flag in the engine is set (used for foul checking).
#
# Pocket detection runs before cushion reflection: if a ball is inside a
# pocket's collision radius it is pocketed immediately rather than bouncing.
# =============================================================================

from entities.ball import Ball, BallState
from entities.table import Table
from utils.constants import RESTITUTION_CUSHION


def resolve_cushions_and_pockets(
    ball: Ball,
    table: Table,
    cushion_contact_callback=None,
    pocket_callback=None,
) -> None:
    """Check *ball* against cushions and pockets and respond accordingly.

    Parameters
    ----------
    ball : Ball
        The ball to test.  Must be active (not pocketed).
    table : Table
        Provides felt boundary coords and pocket list.
    cushion_contact_callback : callable | None
        Called with (ball,) when the ball touches a cushion.
        The engine uses this to satisfy the "ball must contact a rail" rule.
    pocket_callback : callable | None
        Called with (ball,) when the ball is pocketed.
    """
    if ball.pocketed:
        return

    # ------------------------------------------------------------------
    # Pocket detection first  (takes priority over cushion reflection)
    # ------------------------------------------------------------------
    for pocket in table.pockets:
        if pocket.contains(ball.pos):
            ball.pocket()
            if pocket_callback:
                pocket_callback(ball)
            return   # Ball is gone — no cushion check needed

    # ------------------------------------------------------------------
    # Cushion reflection — check all four walls
    # The ball must stay inside the *felt* rectangle.  We treat the felt
    # edges as the reflection boundary (the cushion gives them the correct
    # restitution).
    # ------------------------------------------------------------------
    hit = False

    left   = table.left   + ball.radius
    right  = table.right  - ball.radius
    top    = table.top    + ball.radius
    bottom = table.bottom - ball.radius

    # Left wall
    if ball.pos.x < left:
        ball.pos.x  = left
        ball.vel.x  = abs(ball.vel.x) * RESTITUTION_CUSHION
        hit = True

    # Right wall
    if ball.pos.x > right:
        ball.pos.x  = right
        ball.vel.x  = -abs(ball.vel.x) * RESTITUTION_CUSHION
        hit = True

    # Top wall
    if ball.pos.y < top:
        ball.pos.y  = top
        ball.vel.y  = abs(ball.vel.y) * RESTITUTION_CUSHION
        hit = True

    # Bottom wall
    if ball.pos.y > bottom:
        ball.pos.y  = bottom
        ball.vel.y  = -abs(ball.vel.y) * RESTITUTION_CUSHION
        hit = True

    if hit:
        # Keep ball rolling state after cushion hit
        ball.state = BallState.ROLLING
        if cushion_contact_callback:
            cushion_contact_callback(ball)
