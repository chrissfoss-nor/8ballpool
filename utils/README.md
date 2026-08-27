# utils/

Shared utility modules used by every other package in the game.

## Files

| File | Purpose |
|------|---------|
| `constants.py` | **Single source of truth for all tunable values** — window size, table dimensions, physics coefficients, colors, ball colors. Tweak physics feel here without touching any other file. |
| `vector.py` | `Vec2` — a lightweight 2-D vector class. Supports `+`, `-`, `*`, `/`, negation, dot product, normalize, rotate, reflect, and distance helpers. Used everywhere instead of bare tuples so the math stays readable. |
| `__init__.py` | Re-exports everything from `constants` and `Vec2` from `vector` for convenient `from utils import *` usage. |

## Usage

```python
from utils.vector import Vec2
from utils.constants import BALL_RADIUS, FRICTION_ROLLING

# Create a velocity vector pointing right at 500 px/s
vel = Vec2(500, 0)

# Reflect off a vertical wall (normal pointing left)
normal = Vec2(-1, 0)
new_vel = vel.reflect(normal)
```
