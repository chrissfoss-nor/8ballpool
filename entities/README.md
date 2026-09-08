# entities/

Game object definitions — everything that exists on the pool table.

## Files

| File | Purpose |
|------|---------|
| `ball.py` | `Ball` dataclass with `BallState` and `BallGroup` enums. Every ball on the table is one instance. The physics engine mutates `pos`, `vel`, `spin`, `state`; the rules engine reads `group`, `number`, `pocketed`. `roll` and `side_spin` carry cue-ball spin — the difference `roll - vel` is the slip the cloth works on. |
| `pocket.py` | `Pocket` dataclass: centre position, corner/side mouth width, visual radius, and collision radius. `pocket.contains(ball_pos)` returns `True` when a ball should be pocketed. |
| `table.py` | `Table` dataclass holding the felt rect, cushion rect, wood rect, and the list of six pockets. `create_table()` factory builds the standard geometry from constants. |
| `cue.py` | `Cue` class: manages aim angle, power level, drag input, and draws the cue stick. `get_shot_vector()` returns the impulse `Vec2` to apply to the cue ball on a shot, and `tip` says where on the cue ball that impulse lands, which is what puts spin on it. |

## Ball numbering

| Number | Group | Description |
|--------|-------|-------------|
| 0 | CUE | White cue ball |
| 1–7 | SOLID | Solid-colour balls |
| 8 | EIGHT | The eight ball (money ball) |
| 9–15 | STRIPE | Striped balls |

## Controls (Cue)

| Action | Effect |
|--------|--------|
| Move mouse | Aim direction updates in real time |
| Scroll wheel / arrow keys / + / - / power bar | Increase / decrease shot power |
| Right-click drag | Pull cue back to set power |
| Left-click | Fire the shot |
