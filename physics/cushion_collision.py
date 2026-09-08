# =============================================================================
# cushion_collision.py - Ball-cushion reflection and pocket detection.
#
# The cushion walls are axis-aligned, but they are not continuous: realistic
# pocket mouths leave gaps in the rail.  A ball that enters a gap can drop into
# the pocket, while a ball that catches a jaw reflects off that cushion point.
# =============================================================================

from entities.ball import Ball, BallState
from entities.table import Table
from utils.constants import BALL_RADIUS, RESTITUTION_CUSHION
from physics.spin import bounce_spin_off_cushion
from utils.vector import Vec2


# Inward normals of the four cushions, pointing away from the rail.
_NORMAL_LEFT   = Vec2( 1.0,  0.0)
_NORMAL_RIGHT  = Vec2(-1.0,  0.0)
_NORMAL_TOP    = Vec2( 0.0,  1.0)
_NORMAL_BOTTOM = Vec2( 0.0, -1.0)


def resolve_cushions_and_pockets(
    ball: Ball,
    table: Table,
    cushion_contact_callback=None,
    pocket_callback=None,
) -> None:
    """Check *ball* against cushions and pockets and respond accordingly."""
    if ball.pocketed:
        return

    if _try_pocket(ball, table, pocket_callback):
        return

    hit = _resolve_pocket_jaws(ball, table)

    if _try_pocket(ball, table, pocket_callback):
        return

    if _has_entered_open_mouth(ball, table):
        ball.pocket()
        if pocket_callback:
            pocket_callback(ball)
        return

    hit = _resolve_felt_walls(ball, table) or hit

    if hit:
        ball.state = BallState.ROLLING
        if cushion_contact_callback:
            cushion_contact_callback(ball)


def _try_pocket(ball: Ball, table: Table, pocket_callback=None) -> bool:
    """Pocket *ball* if its centre is inside any pocket capture radius."""
    pos = ball.pos
    for pocket in table.pockets:
        px = pos.x - pocket.pos.x
        py = pos.y - pocket.pos.y
        radius = pocket.collision_radius
        if px * px + py * py <= radius * radius:
            ball.pocket()
            if pocket_callback:
                pocket_callback(ball)
            return True
    return False


def _resolve_felt_walls(ball: Ball, table: Table) -> bool:
    """Reflect against cushion walls, except where a pocket mouth is open."""
    hit = False

    left = table.left + ball.radius
    right = table.right - ball.radius
    top = table.top + ball.radius
    bottom = table.bottom - ball.radius

    spinning = ball.is_cue_ball

    if ball.pos.x < left and not _vertical_wall_has_pocket_gap(table, ball.pos.y):
        ball.pos.x = left
        ball.vel.x = abs(ball.vel.x) * RESTITUTION_CUSHION
        if spinning:
            bounce_spin_off_cushion(ball, _NORMAL_LEFT)
        hit = True

    if ball.pos.x > right and not _vertical_wall_has_pocket_gap(table, ball.pos.y):
        ball.pos.x = right
        ball.vel.x = -abs(ball.vel.x) * RESTITUTION_CUSHION
        if spinning:
            bounce_spin_off_cushion(ball, _NORMAL_RIGHT)
        hit = True

    if ball.pos.y < top and not _horizontal_wall_has_pocket_gap(table, ball.pos.x):
        ball.pos.y = top
        ball.vel.y = abs(ball.vel.y) * RESTITUTION_CUSHION
        if spinning:
            bounce_spin_off_cushion(ball, _NORMAL_TOP)
        hit = True

    if ball.pos.y > bottom and not _horizontal_wall_has_pocket_gap(table, ball.pos.x):
        ball.pos.y = bottom
        ball.vel.y = -abs(ball.vel.y) * RESTITUTION_CUSHION
        if spinning:
            bounce_spin_off_cushion(ball, _NORMAL_BOTTOM)
        hit = True

    return hit


def _resolve_pocket_jaws(ball: Ball, table: Table) -> bool:
    """Reflect the ball if it catches one of the pocket jaw points."""
    hit = False
    min_dist = ball.radius

    for jaw in _pocket_jaw_points(table):
        # Raw-float reject first — twelve jaws are tested per ball per
        # sub-step and almost none of them are ever in range.  ball.pos is
        # re-read every iteration because a jaw hit rebinds it.
        pos = ball.pos
        dx = pos.x - jaw.x
        dy = pos.y - jaw.y
        dist_sq = dx * dx + dy * dy
        if dist_sq >= min_dist * min_dist:
            continue

        delta = Vec2(dx, dy)
        dist = dist_sq ** 0.5

        if dist < 1e-6:
            normal = (-ball.vel).normalize()
            if normal.length_sq() < 1e-9:
                normal = Vec2(1.0, 0.0)
        else:
            normal = delta / dist

        if ball.vel.dot(normal) < 0.0:
            ball.vel = ball.vel.reflect(normal) * RESTITUTION_CUSHION
            if ball.is_cue_ball:
                bounce_spin_off_cushion(ball, normal)

        ball.pos = jaw + normal * (min_dist + 0.25)
        hit = True

    return hit


def _has_entered_open_mouth(ball: Ball, table: Table) -> bool:
    """Return True once the ball centre crosses through an open pocket mouth."""
    x = ball.pos.x
    y = ball.pos.y

    if x < table.left and _vertical_wall_has_pocket_gap(table, y):
        return True
    if x > table.right and _vertical_wall_has_pocket_gap(table, y):
        return True
    if y < table.top and _horizontal_wall_has_pocket_gap(table, x):
        return True
    if y > table.bottom and _horizontal_wall_has_pocket_gap(table, x):
        return True
    return False


def _vertical_wall_has_pocket_gap(table: Table, y: float) -> bool:
    """Return True when the left/right wall is open for a corner pocket."""
    half = _corner_mouth_half_width(table)
    return y <= table.top + half or y >= table.bottom - half


def _horizontal_wall_has_pocket_gap(table: Table, x: float) -> bool:
    """Return True when the top/bottom wall is open for a corner or side pocket."""
    corner_half = _corner_mouth_half_width(table)
    side_half = _side_mouth_half_width(table)
    side_x = table.center.x

    return (
        x <= table.left + corner_half
        or x >= table.right - corner_half
        or abs(x - side_x) <= side_half
    )


# ---------------------------------------------------------------------------
# Geometry cache
#
# The mouth widths and the twelve jaw points are pure functions of the table,
# which never changes after create_table().  Recomputing them per ball per
# sub-step was allocating hundreds of thousands of throwaway Vec2 objects on
# an ordinary shot, so they are memoised on the Table instance itself.
# ---------------------------------------------------------------------------

def _mouth_half_widths(table: Table) -> tuple[float, float]:
    """Return (corner_half_width, side_half_width), cached on the table."""
    cached = getattr(table, "_mouth_half_widths_cache", None)
    if cached is None:
        corner = BALL_RADIUS * 2.0
        side = BALL_RADIUS * 2.22
        for pocket in table.pockets:
            if pocket.kind == "corner":
                corner = pocket.mouth_half_width
                break
        for pocket in table.pockets:
            if pocket.kind == "side":
                side = pocket.mouth_half_width
                break
        cached = (corner, side)
        table._mouth_half_widths_cache = cached
    return cached


def _corner_mouth_half_width(table: Table) -> float:
    return _mouth_half_widths(table)[0]


def _side_mouth_half_width(table: Table) -> float:
    return _mouth_half_widths(table)[1]


def _pocket_jaw_points(table: Table) -> list[Vec2]:
    """Return the cushion-tip points around every pocket mouth (cached)."""
    cached = getattr(table, "_jaw_points_cache", None)
    if cached is not None:
        return cached
    cached = _compute_pocket_jaw_points(table)
    table._jaw_points_cache = cached
    return cached


def _compute_pocket_jaw_points(table: Table) -> list[Vec2]:
    """Build the cushion-tip points around every pocket mouth."""
    left = table.left
    right = table.right
    top = table.top
    bottom = table.bottom
    center_x = table.center.x
    corner_half = _corner_mouth_half_width(table)
    side_half = _side_mouth_half_width(table)

    return [
        Vec2(left + corner_half, top),
        Vec2(left, top + corner_half),
        Vec2(right - corner_half, top),
        Vec2(right, top + corner_half),
        Vec2(left + corner_half, bottom),
        Vec2(left, bottom - corner_half),
        Vec2(right - corner_half, bottom),
        Vec2(right, bottom - corner_half),
        Vec2(center_x - side_half, top),
        Vec2(center_x + side_half, top),
        Vec2(center_x - side_half, bottom),
        Vec2(center_x + side_half, bottom),
    ]
