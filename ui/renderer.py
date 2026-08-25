# =============================================================================
# renderer.py — Main rendering module.  Draws everything that appears on the
# pool table: felt, cushions, pockets, balls (with numbers and stripe bands),
# the cue stick, the aiming guide line, and ball shadows.
#
# draw_frame() is called once per game loop tick.  It does NOT draw the HUD
# or overlays — those are handled by hud.py and overlay.py respectively.
#
# Rendering is deliberately kept separate from game logic so the draw code
# has no side effects on game state.
# =============================================================================

import math
import pygame
from typing import List, Optional

from utils.vector   import Vec2
from utils.constants import (
    COLOR_BACKGROUND, COLOR_WOOD, COLOR_CUSHION, COLOR_FELT,
    COLOR_POCKET, COLOR_HEAD_STRING, COLOR_AIM_LINE, COLOR_SHADOW,
    COLOR_INVALID_GHOST,
    AIM_LINE_DASH_LEN, AIM_LINE_GAP_LEN, AIM_LINE_ALPHA, GHOST_BALL_ALPHA,
    BALL_RADIUS, POCKET_VISUAL_RADIUS,
    TABLE_OFFSET_X, TABLE_OFFSET_Y, TABLE_W, TABLE_H, CUSHION_THICKNESS,
    BALL_COLORS,
)
from entities.ball   import Ball, BallGroup
from entities.table  import Table
from entities.cue    import Cue


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def draw_frame(
    surface       : pygame.Surface,
    table         : Table,
    balls         : List[Ball],
    cue           : Cue,
    state_name    : str,
    ball_in_hand  : bool = False,
    mouse_pos     : tuple = (0, 0),
    placement_valid: bool = True,
) -> None:
    """Draw one complete frame onto *surface*.

    Parameters
    ----------
    surface : pygame.Surface
        The main window surface.
    table : Table
        Table geometry.
    balls : list[Ball]
        All balls (active and pocketed; pocketed ones are skipped).
    cue : Cue
        The player's cue stick (drawn only in aiming states).
    state_name : str
        Name of the current GameState (used to decide what to draw).
    ball_in_hand : bool
        If True, draw a ghost cue ball following the mouse cursor.
    mouse_pos : tuple
        Current mouse (x, y) used for ghost ball and aim line.
    placement_valid : bool
        Whether the current ghost ball position is a legal placement.
    """

    # 1. Background
    surface.fill(COLOR_BACKGROUND)

    # 2. Wooden rail border
    pygame.draw.rect(surface, COLOR_WOOD, table.wood_rect, border_radius=8)

    # 3. Cushion band
    cushion_rect = pygame.Rect(
        table.felt_rect.left   - CUSHION_THICKNESS,
        table.felt_rect.top    - CUSHION_THICKNESS,
        table.felt_rect.width  + CUSHION_THICKNESS * 2,
        table.felt_rect.height + CUSHION_THICKNESS * 2,
    )
    pygame.draw.rect(surface, COLOR_CUSHION, cushion_rect, border_radius=4)

    # 4. Felt surface
    pygame.draw.rect(surface, COLOR_FELT, table.felt_rect)

    # 5. Pocket holes
    for pocket in table.pockets:
        pygame.draw.circle(
            surface, COLOR_POCKET,
            pocket.pos.to_int_tuple(),
            pocket.visual_radius,
        )

    # 6. Head string  (dashed vertical line — marks ball-in-hand zone on break)
    _draw_head_string(surface, table)

    # 7. Ball shadows (drawn before balls so shadows sit "under" them)
    for ball in balls:
        if not ball.pocketed:
            _draw_ball_shadow(surface, ball)

    # 8. Balls
    for ball in balls:
        if not ball.pocketed:
            _draw_ball(surface, ball)

    # 9. Aiming line and cue stick (only in aiming state)
    aiming = state_name in ("PLAYER_AIMING", "BREAK_SHOT")
    if aiming and cue.visible:
        # Find the cue ball
        cue_ball = next((b for b in balls if b.is_cue_ball and not b.pocketed), None)
        if cue_ball:
            _draw_aim_line(surface, cue_ball, cue, balls, table)
            cue.draw(surface, cue_ball.pos)

    # 10. Ghost cue ball for ball-in-hand placement
    if ball_in_hand:
        color = (200, 50, 50) if not placement_valid else (240, 240, 240)
        alpha_surf = pygame.Surface((BALL_RADIUS * 2 + 4, BALL_RADIUS * 2 + 4), pygame.SRCALPHA)
        pygame.draw.circle(
            alpha_surf, (*color, 140),
            (BALL_RADIUS + 2, BALL_RADIUS + 2),
            BALL_RADIUS,
        )
        surface.blit(alpha_surf, (mouse_pos[0] - BALL_RADIUS - 2, mouse_pos[1] - BALL_RADIUS - 2))


# ---------------------------------------------------------------------------
# Table decorations
# ---------------------------------------------------------------------------

def _draw_head_string(surface: pygame.Surface, table: Table) -> None:
    """Draw a dashed vertical line at the head string position."""
    x     = int(table.head_x)
    top   = table.felt_rect.top    + 5
    bot   = table.felt_rect.bottom - 5
    y     = top
    dash  = 8
    gap   = 5
    while y < bot:
        end_y = min(y + dash, bot)
        pygame.draw.line(surface, (180, 180, 180, 80), (x, int(y)), (x, int(end_y)), 1)
        y += dash + gap


# ---------------------------------------------------------------------------
# Ball rendering
# ---------------------------------------------------------------------------

def _draw_ball_shadow(surface: pygame.Surface, ball: Ball) -> None:
    """Draw a semi-transparent shadow ellipse slightly below each ball."""
    shadow_surf = pygame.Surface((BALL_RADIUS * 3, BALL_RADIUS * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(
        shadow_surf,
        (0, 0, 0, 70),
        shadow_surf.get_rect(),
    )
    sx = int(ball.pos.x) - BALL_RADIUS + 4
    sy = int(ball.pos.y) - BALL_RADIUS // 2 + 6
    surface.blit(shadow_surf, (sx, sy))


def _draw_ball(surface: pygame.Surface, ball: Ball) -> None:
    """Draw a single ball with number, color and stripe band if applicable."""
    cx = int(ball.pos.x)
    cy = int(ball.pos.y)
    r  = ball.radius

    if ball.is_stripe:
        # --- Stripe ball: white base, colored band, number ---
        # White base circle
        pygame.draw.circle(surface, (245, 245, 245), (cx, cy), int(r))
        # Colored band across the middle third (drawn as a clipped rect)
        band_surf = pygame.Surface((int(r * 2) + 2, int(r * 2) + 2), pygame.SRCALPHA)
        band_rect = pygame.Rect(0, int(r * 0.35), int(r * 2) + 2, int(r * 1.3))
        pygame.draw.rect(band_surf, (*ball.color, 255), band_rect)
        # Clip band to circle shape
        circle_mask = pygame.Surface((int(r * 2) + 2, int(r * 2) + 2), pygame.SRCALPHA)
        pygame.draw.circle(circle_mask, (255, 255, 255, 255), (int(r) + 1, int(r) + 1), int(r))
        band_surf.blit(circle_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surface.blit(band_surf, (cx - int(r) - 1, cy - int(r) - 1))
        # Thin outline
        pygame.draw.circle(surface, (60, 60, 60), (cx, cy), int(r), 1)
    else:
        # --- Solid ball: filled circle ---
        pygame.draw.circle(surface, ball.color, (cx, cy), int(r))
        # Thin outline
        pygame.draw.circle(surface, (30, 30, 30), (cx, cy), int(r), 1)

    # Sheen (small white highlight in the upper-left quadrant)
    if ball.number != 0:   # Skip sheen on cue ball (it has its own below)
        sheen_x = cx - int(r * 0.3)
        sheen_y = cy - int(r * 0.3)
        sheen_r = max(2, int(r * 0.25))
        sheen_surf = pygame.Surface((sheen_r * 2, sheen_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(sheen_surf, (255, 255, 255, 100), (sheen_r, sheen_r), sheen_r)
        surface.blit(sheen_surf, (sheen_x - sheen_r, sheen_y - sheen_r))

    # Number label (all balls except the cue ball get a number)
    if ball.number != 0:
        _draw_ball_number(surface, ball, cx, cy, r)

    # Cue ball: simple white circle with a subtle sheen
    if ball.number == 0:
        sheen_surf = pygame.Surface((int(r), int(r)), pygame.SRCALPHA)
        pygame.draw.circle(sheen_surf, (255, 255, 255, 120),
                           (int(r) // 2, int(r) // 2), int(r) // 2)
        surface.blit(sheen_surf, (cx - int(r) // 2, cy - int(r) // 2))


def _draw_ball_number(
    surface: pygame.Surface,
    ball   : Ball,
    cx     : int,
    cy     : int,
    r      : float,
) -> None:
    """Draw the ball number centered on the ball, rotated with ball.spin."""
    from ui.assets import get_bold_font
    font_size = max(8, int(r * 1.1))
    font      = get_bold_font(font_size)

    # Choose text color: white on dark balls, black on light/stripe balls
    if ball.is_stripe:
        text_color = (20, 20, 20)
    elif sum(ball.color) < 350:
        text_color = (230, 230, 230)   # light text on dark ball
    else:
        text_color = (20, 20, 20)       # dark text on light ball

    label = str(ball.number)
    txt_surf = font.render(label, True, text_color)
    # Rotate the text surface by the current spin angle (visual roll)
    rotated  = pygame.transform.rotate(txt_surf, -math.degrees(ball.spin))
    txt_rect = rotated.get_rect(center=(cx, cy))
    surface.blit(rotated, txt_rect)


# ---------------------------------------------------------------------------
# Aiming line
# ---------------------------------------------------------------------------

def _draw_aim_line(
    surface  : pygame.Surface,
    cue_ball : Ball,
    cue      : Cue,
    balls    : List[Ball],
    table    : Table,
) -> None:
    """Draw a dashed aiming line from the cue ball to the first obstacle.

    If the line would hit another ball, also draw a ghost ball at the impact
    point and a short arrow showing where that ball would travel.
    """
    import math
    dx = math.cos(cue.angle)
    dy = math.sin(cue.angle)

    origin = cue_ball.pos.copy()

    # Find the closest ball or cushion the aim line intersects
    hit_pos, hit_ball = _ray_cast(origin, Vec2(dx, dy), cue_ball, balls, table)

    # Draw dashed line from cue ball to hit position
    _draw_dashed_line(surface, origin, hit_pos, AIM_LINE_ALPHA)

    # If we hit a ball: draw a ghost of it and a deflection arrow
    if hit_ball:
        _draw_ghost_ball(surface, hit_ball, hit_pos)
        # Direction the hit ball would travel (along collision normal)
        n = (hit_pos - hit_ball.pos)
        dist = n.length()
        if dist > 0.01:
            n = n / dist
            end = Vec2(hit_ball.pos.x + n.x * 60, hit_ball.pos.y + n.y * 60)
            pygame.draw.line(
                surface,
                (255, 230, 100, 120),
                hit_ball.pos.to_int_tuple(),
                end.to_int_tuple(),
                1,
            )


def _ray_cast(
    origin   : Vec2,
    direction: Vec2,
    cue_ball : Ball,
    balls    : List[Ball],
    table    : Table,
    max_dist : float = 2000.0,
) -> tuple:
    """Cast a ray from *origin* in *direction* and find the first hit.

    Returns (hit_position: Vec2, hit_ball: Ball | None).
    """
    best_t    = max_dist
    best_ball = None

    # Check against every other active ball
    for ball in balls:
        if ball is cue_ball or ball.pocketed:
            continue
        t = _ray_circle_intersect(origin, direction, ball.pos, ball.radius + BALL_RADIUS)
        if t is not None and 0 < t < best_t:
            best_t    = t
            best_ball = ball

    # Check against cushion walls
    t_wall = _ray_wall_intersect(origin, direction, table)
    if t_wall < best_t:
        best_t    = t_wall
        best_ball = None

    hit_pos = Vec2(origin.x + direction.x * best_t, origin.y + direction.y * best_t)
    return hit_pos, best_ball


def _ray_circle_intersect(
    origin   : Vec2,
    direction: Vec2,
    center   : Vec2,
    radius   : float,
) -> Optional[float]:
    """Return the distance *t* along *direction* where the ray hits the circle,
    or None if there is no intersection."""
    import math
    oc = origin - center
    a  = direction.dot(direction)
    b  = 2.0 * oc.dot(direction)
    c  = oc.dot(oc) - radius * radius
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    t = (-b - math.sqrt(disc)) / (2.0 * a)
    if t > 0:
        return t
    return None


def _ray_wall_intersect(origin: Vec2, direction: Vec2, table: Table) -> float:
    """Return the distance to the nearest cushion wall along *direction*."""
    best_t = 2000.0
    r = BALL_RADIUS

    walls = [
        # (normal_x, normal_y, wall_coord, test_axis)
        # Left wall
        (1, 0, table.left + r),
        # Right wall
        (-1, 0, table.right - r),
        # Top wall
        (0, 1, table.top + r),
        # Bottom wall
        (0, -1, table.bottom - r),
    ]

    for (nx, ny, wall) in walls:
        # Check axis: if nx != 0 use x, else use y
        if nx != 0:
            if abs(direction.x) < 1e-9:
                continue
            t = (wall - origin.x) / direction.x
        else:
            if abs(direction.y) < 1e-9:
                continue
            t = (wall - origin.y) / direction.y
        if t > 0 and t < best_t:
            best_t = t

    return best_t


def _draw_dashed_line(
    surface : pygame.Surface,
    start   : Vec2,
    end     : Vec2,
    alpha   : int = 140,
) -> None:
    """Draw a dashed line from *start* to *end*."""
    dx  = end.x - start.x
    dy  = end.y - start.y
    dist = math.sqrt(dx * dx + dy * dy)
    if dist < 1:
        return
    ux, uy = dx / dist, dy / dist

    step = AIM_LINE_DASH_LEN + AIM_LINE_GAP_LEN
    t    = 0.0
    while t < dist:
        t1 = t
        t2 = min(t + AIM_LINE_DASH_LEN, dist)
        p1 = (int(start.x + ux * t1), int(start.y + uy * t1))
        p2 = (int(start.x + ux * t2), int(start.y + uy * t2))
        pygame.draw.line(surface, (*COLOR_AIM_LINE[:3], alpha) if len(COLOR_AIM_LINE) > 3
                         else COLOR_AIM_LINE, p1, p2, 1)
        t += step


def _draw_ghost_ball(
    surface  : pygame.Surface,
    ball     : Ball,
    impact   : Vec2,
) -> None:
    """Draw a semi-transparent ghost of *ball* at *impact* position."""
    r    = int(ball.radius)
    size = r * 2 + 2
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(surf, (*ball.color, GHOST_BALL_ALPHA), (r + 1, r + 1), r)
    pygame.draw.circle(surf, (255, 255, 255, 40), (r + 1, r + 1), r, 1)
    surface.blit(surf, (int(impact.x) - r - 1, int(impact.y) - r - 1))
