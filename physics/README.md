# physics/

The simulation engine — handles all ball motion, collision detection/response, and pocket detection.

## Files

| File | Purpose |
|------|---------|
| `engine.py` | `PhysicsEngine` — master update loop. Runs `NUM_SUBSTEPS` sub-steps per frame. Tracks shot-level state (`first_contact_ball`, `cushion_contacted`, `pocketed_this_shot`) and signals `all_stationary` when all balls stop. |
| `friction.py` | `apply_friction(ball, dt)` — two-phase friction model: high sliding deceleration right after cue impact, low rolling deceleration at lower speeds. Runs the spin step first, and skips the drag for a ball that is still sliding, which has already paid the cloth through its slip. Updates visual spin angle. |
| `spin.py` | Cue-ball spin. `apply_cue_strike()` turns a tip offset into roll and side spin, `advance_slip()` lets the cloth work on the slip each sub-step, `throw_off_side_spin()` and `bounce_spin_off_cushion()` handle what spin does at a ball and at a rail. Only the cue ball carries spin. |
| `ball_collision.py` | `resolve_pair(a, b)` — elastic ball-ball collision with restitution (e=0.96) and positional correction to prevent overlap sinking. The cue ball keeps the roll it arrived with, which is what makes it follow or draw; an object ball starts rolling naturally. |
| `cushion_collision.py` | `resolve_cushions_and_pockets(ball, table)` — axis-aligned wall reflections with cushion restitution (e=0.75), standard-sized pocket mouth gaps, jaw collisions, and pocket detection. |

## Physics parameters (tunable in `utils/constants.py`)

| Constant | Default | Effect |
|----------|---------|--------|
| `NUM_SUBSTEPS` | 4 | Sub-steps per frame — more = more stable but slower |
| `FRICTION_SLIDING` | 0.20 | Deceleration coefficient right after impact |
| `FRICTION_ROLLING` | 0.018 | Deceleration coefficient when rolling slowly |
| `SPIN_MAX_TIP_OFFSET` | 0.5 | How far off centre the tip may strike, in ball radii |
| `SPIN_DRAW_GAIN` / `SPIN_FOLLOW_GAIN` | 4.5 / 0.5 | Roll a full bottom or top hit puts on the ball |
| `SPIN_SIDE_GAIN` | 1.4 | Side spin a full side hit puts on the ball |
| `CUSHION_SPIN_GAIN` | 0.30 | How much side spin pushes the ball along a rail it leaves |
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
