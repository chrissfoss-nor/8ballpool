# physics/

The simulation engine — handles all ball motion, collision detection/response, and pocket detection.

## Files

| File | Purpose |
|------|---------|
| `engine.py` | `PhysicsEngine` — master update loop. Runs `NUM_SUBSTEPS` sub-steps per frame. Tracks shot-level state (`first_contact_ball`, `cushion_contacted`, `pocketed_this_shot`) and signals `all_stationary` when all balls stop. |
| `friction.py` | `apply_friction(ball, dt)` — two-phase friction model: high sliding deceleration right after cue impact, low rolling deceleration at lower speeds. Updates visual spin angle. |
| `ball_collision.py` | `resolve_pair(a, b)` — elastic ball-ball collision with restitution (e=0.96) and positional correction to prevent overlap sinking. |
| `cushion_collision.py` | `resolve_cushions_and_pockets(ball, table)` — axis-aligned wall reflections with cushion restitution (e=0.75); pocket detection runs first and takes priority. |

## Physics parameters (tunable in `utils/constants.py`)

| Constant | Default | Effect |
|----------|---------|--------|
| `NUM_SUBSTEPS` | 4 | Sub-steps per frame — more = more stable but slower |
| `FRICTION_SLIDING` | 0.20 | Deceleration coefficient right after impact |
| `FRICTION_ROLLING` | 0.018 | Deceleration coefficient when rolling slowly |
| `ROLLING_THRESHOLD` | 200 px/s | Speed below which rolling friction kicks in |
| `STOP_THRESHOLD` | 4 px/s | Speed below which a ball is considered stopped |
| `RESTITUTION_BALL` | 0.96 | Energy retained in ball-ball collisions |
| `RESTITUTION_CUSHION` | 0.75 | Energy retained in cushion bounces |

## Sub-step loop

```
for _ in range(NUM_SUBSTEPS):
    apply_friction(each active ball, dt/NUM_SUBSTEPS)
    resolve all ball-ball pairs
    resolve_cushions_and_pockets(each active ball)
```
