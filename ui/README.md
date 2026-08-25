# ui/

All rendering code — table, balls, cue stick, HUD panels, and overlays.

## Files

| File | Purpose |
|------|---------|
| `renderer.py` | `draw_frame()` — draws one complete frame: background, wood, cushions, felt, pockets, head string, ball shadows, balls (with numbers/stripes), aiming line, cue stick, and ghost ball for ball-in-hand. |
| `hud.py` | `draw_hud()` — top strip (player names, group labels, pocketed mini-balls, turn arrow) and bottom strip (shot power bar). |
| `overlay.py` | Semi-transparent pop-up panels for foul notifications, win/loss screens, break prompts, and ball-in-hand instructions. |
| `assets.py` | Font cache (`get_font`, `get_bold_font`) and `draw_text_centered` helper. No image files — everything is drawn procedurally. |

## Rendering layers (draw order)

1. Background fill
2. Wooden border
3. Cushion band
4. Felt surface
5. Pocket holes (black circles)
6. Head string (dashed vertical line)
7. Ball shadows (semi-transparent ellipses)
8. Balls — filled circles with number text; stripe balls get a colored band
9. Aiming guide line + ghost ball (only during PLAYER_AIMING / BREAK_SHOT)
10. Cue stick (only during PLAYER_AIMING / BREAK_SHOT)
11. HUD panels (top + bottom strips)
12. Overlays (topmost — drawn by game.py after draw_frame)

## Aiming aid

The aiming line is a dashed ray cast from the cue ball in the shot direction.  It stops at the first ball or cushion it would hit.  If it hits a ball, a semi-transparent ghost of that ball is drawn at the impact point, plus a short arrow showing where the target ball would travel.
