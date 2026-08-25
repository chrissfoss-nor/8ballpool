# =============================================================================
# overlay.py — Full-screen overlays: foul notification, win screen, break
# prompt, and ball-in-hand instructions.
#
# Overlays are drawn on top of everything else.  They use a semi-transparent
# dark backing panel so the table is still visible behind them.
# =============================================================================

import pygame

from utils.constants import WINDOW_W, WINDOW_H, COLOR_FOUL_OVERLAY, COLOR_WIN_OVERLAY
from ui.assets import draw_text_centered


# ---------------------------------------------------------------------------
# Shared drawing helper
# ---------------------------------------------------------------------------

def _draw_panel(
    surface     : pygame.Surface,
    color       : tuple,
    title       : str,
    lines       : list,
    title_size  : int = 36,
    line_size   : int = 20,
) -> None:
    """Draw a centered semi-transparent panel with a title and body lines."""
    panel_w = 560
    panel_h = 60 + len(lines) * (line_size + 8) + 20
    panel_x = (WINDOW_W - panel_w) // 2
    panel_y = (WINDOW_H - panel_h) // 2

    # Dark semi-transparent backing
    backing = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    backing.fill((0, 0, 0, 130))
    surface.blit(backing, (0, 0))

    # Colored panel
    panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
    panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    panel_surf.fill((*color[:3], 220))
    surface.blit(panel_surf, (panel_x, panel_y))
    pygame.draw.rect(surface, (255, 255, 255), panel_rect, 2, border_radius=8)

    # Title
    draw_text_centered(
        surface, title, title_size,
        WINDOW_W // 2, panel_y + 30,
        color=(255, 255, 255), bold=True,
    )

    # Body lines
    for i, line in enumerate(lines):
        y = panel_y + 60 + i * (line_size + 8)
        draw_text_centered(surface, line, line_size, WINDOW_W // 2, y, color=(240, 240, 240))


# ---------------------------------------------------------------------------
# Public overlay functions
# ---------------------------------------------------------------------------

def draw_foul_overlay(surface: pygame.Surface, reason: str, next_player: str) -> None:
    """Overlay shown when a foul is committed.

    Prompts the opponent to acknowledge before placing the cue ball.

    Parameters
    ----------
    reason : str
        Human-readable foul description (e.g. "Cue ball scratched").
    next_player : str
        Name of the player who now has ball-in-hand.
    """
    _draw_panel(
        surface,
        color=(140, 30, 30),
        title="FOUL!",
        lines=[
            reason,
            f"{next_player} has ball in hand.",
            "",
            "Press SPACE or click to continue.",
        ],
    )


def draw_ball_in_hand_overlay(surface: pygame.Surface, player_name: str, restricted: bool) -> None:
    """Light instruction bar shown during ball-in-hand placement.

    Does NOT use the dark backing panel — just a small bottom banner so the
    player can see where they're placing the ball.

    Parameters
    ----------
    player_name : str
        Name of the player placing the ball.
    restricted : bool
        If True, placement is restricted to behind the head string (break scratch).
    """
    banner_h   = 40
    banner_rect = pygame.Rect(0, WINDOW_H - banner_h - 30, WINDOW_W, banner_h)
    surf = pygame.Surface((WINDOW_W, banner_h), pygame.SRCALPHA)
    surf.fill((20, 20, 60, 180))
    surface.blit(surf, (0, WINDOW_H - banner_h - 30))

    zone = " behind the head string" if restricted else " anywhere on the table"
    msg  = f"{player_name}: click to place the cue ball{zone}."
    draw_text_centered(surface, msg, 18, WINDOW_W // 2, WINDOW_H - banner_h - 10,
                       color=(220, 220, 255), bold=False)


def draw_win_overlay(surface: pygame.Surface, winner_name: str) -> None:
    """Overlay shown when a player wins the game.

    Parameters
    ----------
    winner_name : str
        Name of the winning player.
    """
    _draw_panel(
        surface,
        color=(30, 120, 60),
        title=f"{winner_name} Wins!",
        lines=[
            "Congratulations!",
            "",
            "Press R to play again.",
            "Press ESC to quit.",
        ],
        title_size=42,
    )


def draw_loss_overlay(surface: pygame.Surface, loser_name: str, reason: str, other_name: str) -> None:
    """Overlay shown when a player loses (e.g. potted the 8-ball early).

    Parameters
    ----------
    loser_name : str
        Name of the player who lost.
    reason : str
        Why they lost.
    other_name : str
        Name of the opposing player (the winner).
    """
    _draw_panel(
        surface,
        color=(120, 30, 30),
        title=f"{loser_name} Loses!",
        lines=[
            reason,
            f"{other_name} wins the game!",
            "",
            "Press R to play again.",
            "Press ESC to quit.",
        ],
        title_size=38,
    )


def draw_break_prompt(surface: pygame.Surface, player_name: str) -> None:
    """Small overlay shown before the break shot.

    Parameters
    ----------
    player_name : str
        Name of the player who is breaking.
    """
    _draw_panel(
        surface,
        color=(20, 60, 100),
        title="8-Ball Pool",
        lines=[
            f"{player_name} breaks first.",
            "Aim and left-click to shoot.",
            "Scroll wheel / right-drag to set power.",
        ],
        title_size=32,
        line_size=18,
    )
