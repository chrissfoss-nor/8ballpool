# =============================================================================
# hud.py — Heads-Up Display: player panels, turn indicator and power bar.
#
# The HUD is drawn in two horizontal strips:
#   Top strip  : Player panels (left = P1, right = P2) + turn arrow.
#   Bottom strip: Shot power bar.
#
# The HUD reads game state data passed in as plain values — it has no
# reference to the game or rules engine.
# =============================================================================

import pygame
from typing import List, Optional

from utils.constants import (
    WINDOW_W, WINDOW_H, HUD_HEIGHT, POWER_BAR_HEIGHT,
    POWER_BAR_W, POWER_BAR_BORDER,
    COLOR_HUD_BG, COLOR_HUD_BORDER, COLOR_TEXT, COLOR_TURN_ARROW,
    COLOR_POWER_BAR_BG, COLOR_POWER_BAR_FILL,
    BALL_COLORS, BALL_RADIUS,
)
from ui.assets import draw_text_centered, get_bold_font, get_font


# ---------------------------------------------------------------------------
# Constants for HUD layout
# ---------------------------------------------------------------------------
PANEL_W       = 300    # Width of each player panel
PANEL_MARGIN  = 20     # Margin from window edge
PANEL_H       = HUD_HEIGHT - 10   # Panel height


# ---------------------------------------------------------------------------
# Main HUD draw function
# ---------------------------------------------------------------------------

def draw_hud(
    surface         : pygame.Surface,
    player1_name    : str,
    player2_name    : str,
    player1_group   : str,   # "SOLID", "STRIPE", or "NONE"
    player2_group   : str,
    p1_pocketed     : List[int],   # list of ball numbers pocketed by P1
    p2_pocketed     : List[int],   # list of ball numbers pocketed by P2
    current_player  : int,         # 0 = P1, 1 = P2
    power           : float,       # 0.0 – 1.0
    foul_message    : str = "",    # shown below panel if non-empty
) -> None:
    """Draw the complete HUD onto *surface*."""

    # -----------------------------------------------------------------------
    # Top HUD background strip
    # -----------------------------------------------------------------------
    hud_rect = pygame.Rect(0, 0, WINDOW_W, HUD_HEIGHT)
    pygame.draw.rect(surface, COLOR_HUD_BG, hud_rect)
    pygame.draw.line(surface, COLOR_HUD_BORDER, (0, HUD_HEIGHT - 1), (WINDOW_W, HUD_HEIGHT - 1), 2)

    # -----------------------------------------------------------------------
    # Bottom power bar background strip
    # -----------------------------------------------------------------------
    bottom_y  = WINDOW_H - POWER_BAR_HEIGHT
    bot_rect  = pygame.Rect(0, bottom_y, WINDOW_W, POWER_BAR_HEIGHT)
    pygame.draw.rect(surface, COLOR_HUD_BG, bot_rect)
    pygame.draw.line(surface, COLOR_HUD_BORDER, (0, bottom_y), (WINDOW_W, bottom_y), 2)

    # -----------------------------------------------------------------------
    # Player 1 panel (left side)
    # -----------------------------------------------------------------------
    p1_rect = pygame.Rect(PANEL_MARGIN, 5, PANEL_W, PANEL_H)
    _draw_player_panel(
        surface, p1_rect,
        player1_name, player1_group, p1_pocketed,
        active=(current_player == 0),
        flip=False,
    )

    # -----------------------------------------------------------------------
    # Player 2 panel (right side)
    # -----------------------------------------------------------------------
    p2_x    = WINDOW_W - PANEL_MARGIN - PANEL_W
    p2_rect = pygame.Rect(p2_x, 5, PANEL_W, PANEL_H)
    _draw_player_panel(
        surface, p2_rect,
        player2_name, player2_group, p2_pocketed,
        active=(current_player == 1),
        flip=True,
    )

    # -----------------------------------------------------------------------
    # Turn indicator arrow (center)
    # -----------------------------------------------------------------------
    _draw_turn_arrow(surface, current_player)

    # -----------------------------------------------------------------------
    # Power bar (bottom center)
    # -----------------------------------------------------------------------
    _draw_power_bar(surface, power)

    # -----------------------------------------------------------------------
    # Foul message (below HUD strip if present)
    # -----------------------------------------------------------------------
    if foul_message:
        draw_text_centered(
            surface, foul_message, 16,
            WINDOW_W // 2, HUD_HEIGHT + 14,
            color=(220, 80, 60),
            bold=True,
        )


# ---------------------------------------------------------------------------
# Player panel
# ---------------------------------------------------------------------------

def _draw_player_panel(
    surface    : pygame.Surface,
    rect       : pygame.Rect,
    name       : str,
    group      : str,
    pocketed   : List[int],
    active     : bool,
    flip       : bool,
) -> None:
    """Draw one player's info panel."""
    # Background with highlighted border if this player's turn
    border_color = COLOR_TURN_ARROW if active else COLOR_HUD_BORDER
    pygame.draw.rect(surface, (30, 38, 30), rect, border_radius=4)
    pygame.draw.rect(surface, border_color, rect, 2, border_radius=4)

    # Player name
    name_x = rect.left + rect.width // 2
    draw_text_centered(surface, name, 18, name_x, rect.top + 14, bold=True,
                       color=COLOR_TURN_ARROW if active else COLOR_TEXT)

    # Group label
    group_label = {
        "SOLID" : "Solids (1-7)",
        "STRIPE": "Stripes (9-15)",
        "NONE"  : "Group: TBD",
        "CUE"   : "",
    }.get(group, "")
    if group_label:
        draw_text_centered(surface, group_label, 13, name_x, rect.top + 32,
                           color=(160, 200, 160))

    # Mini ball icons showing pocketed balls
    if pocketed:
        _draw_pocketed_mini_balls(surface, rect, pocketed, flip)


def _draw_pocketed_mini_balls(
    surface  : pygame.Surface,
    panel    : pygame.Rect,
    numbers  : List[int],
    flip     : bool,
) -> None:
    """Draw small colored circles representing pocketed balls."""
    mini_r  = 7
    spacing = mini_r * 2 + 3
    y       = panel.top + 52
    start_x = panel.left + mini_r + 5 if not flip else panel.right - mini_r - 5

    for i, num in enumerate(numbers[:7]):   # at most 7 balls shown
        x = start_x + i * (spacing if not flip else -spacing)
        color = BALL_COLORS.get(num, (150, 150, 150))
        pygame.draw.circle(surface, color, (int(x), int(y)), mini_r)
        pygame.draw.circle(surface, (30, 30, 30), (int(x), int(y)), mini_r, 1)


# ---------------------------------------------------------------------------
# Turn arrow
# ---------------------------------------------------------------------------

def _draw_turn_arrow(surface: pygame.Surface, current_player: int) -> None:
    """Draw an arrow pointing to the active player's side."""
    cy  = HUD_HEIGHT // 2
    cx  = WINDOW_W // 2

    draw_text_centered(
        surface,
        "YOUR TURN",
        15,
        cx,
        cy - 5,
        color=COLOR_TURN_ARROW,
        bold=True,
    )

    # Small arrow triangles pointing left (P1) or right (P2)
    if current_player == 0:
        # Arrow pointing left
        pts = [(cx - 10, cy + 12), (cx + 10, cy + 8), (cx + 10, cy + 16)]
    else:
        pts = [(cx + 10, cy + 12), (cx - 10, cy + 8), (cx - 10, cy + 16)]
    pygame.draw.polygon(surface, COLOR_TURN_ARROW, pts)


# ---------------------------------------------------------------------------
# Power bar
# ---------------------------------------------------------------------------

def _draw_power_bar(surface: pygame.Surface, power: float) -> None:
    """Draw the horizontal shot-power bar at the bottom of the screen."""
    bar_y   = WINDOW_H - POWER_BAR_HEIGHT + (POWER_BAR_HEIGHT - 16) // 2
    bar_x   = (WINDOW_W - POWER_BAR_W) // 2
    b       = POWER_BAR_BORDER

    # Background
    bg_rect = pygame.Rect(bar_x - b, bar_y - b, POWER_BAR_W + b * 2, 16 + b * 2)
    pygame.draw.rect(surface, COLOR_POWER_BAR_BG, bg_rect, border_radius=3)

    # Fill
    fill_w = int(POWER_BAR_W * max(0.0, min(1.0, power)))
    if fill_w > 0:
        # Color shifts from green → yellow → red with power
        r = int(min(255, power * 510))
        g = int(min(255, (1.0 - power) * 510))
        fill_color = (r, g, 30)
        fill_rect  = pygame.Rect(bar_x, bar_y, fill_w, 16)
        pygame.draw.rect(surface, fill_color, fill_rect, border_radius=2)

    # Border
    pygame.draw.rect(surface, COLOR_HUD_BORDER, bg_rect, b, border_radius=3)

    # Label
    label_x = bar_x - 60
    draw_text_centered(surface, "POWER", 13, label_x, bar_y + 8, color=COLOR_TEXT)

    # Percentage
    draw_text_centered(surface, f"{int(power * 100)}%", 13,
                       bar_x + POWER_BAR_W + 30, bar_y + 8, color=COLOR_TEXT)
