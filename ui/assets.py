# =============================================================================
# assets.py — Font and color helpers.
#
# All colors come from utils/constants.py.  This module adds pygame Font
# objects (loaded lazily on first access) and helper functions that the
# renderer and HUD modules use to draw text cleanly.
# =============================================================================

import pygame
from utils.constants import COLOR_TEXT


# ---------------------------------------------------------------------------
# Lazy font cache — fonts cannot be created before pygame.init() is called.
# The first time a font size is requested it is created and cached here.
# ---------------------------------------------------------------------------
_font_cache: dict[int, pygame.font.Font] = {}
_bold_font_cache: dict[int, pygame.font.Font] = {}


def get_font(size: int) -> pygame.font.Font:
    """Return a regular SysFont of *size* pt, creating it on first call."""
    if size not in _font_cache:
        _font_cache[size] = pygame.font.SysFont("Arial", size)
    return _font_cache[size]


def get_bold_font(size: int) -> pygame.font.Font:
    """Return a bold SysFont of *size* pt, creating it on first call."""
    if size not in _bold_font_cache:
        _bold_font_cache[size] = pygame.font.SysFont("Arial", size, bold=True)
    return _bold_font_cache[size]


def render_text(
    text: str,
    size: int,
    color: tuple = COLOR_TEXT,
    bold: bool = False,
) -> pygame.Surface:
    """Render *text* into a Surface with anti-aliasing."""
    font = get_bold_font(size) if bold else get_font(size)
    return font.render(text, True, color)


def draw_text_centered(
    surface: pygame.Surface,
    text: str,
    size: int,
    center_x: float,
    center_y: float,
    color: tuple = COLOR_TEXT,
    bold: bool = False,
) -> None:
    """Render *text* and blit it centred at (*center_x*, *center_y*)."""
    img = render_text(text, size, color, bold)
    rect = img.get_rect(center=(int(center_x), int(center_y)))
    surface.blit(img, rect)
