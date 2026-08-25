# 8-Ball Pool

A local two-player 8-ball pool game written in Python with Pygame.

## Features

- **Realistic physics** — elastic ball-ball collisions, cushion reflections with energy loss, two-phase rolling/sliding friction
- **Full 8-ball rules** — break rules, solid/stripe group assignment, all foul types, win/loss conditions
- **Mouse-driven controls** — aim with the mouse, set power with scroll wheel or right-click drag, left-click to shoot
- **Visual aiming aid** — dashed guide line + ghost ball showing where the target ball will travel
- **2-player local multiplayer** — pass the keyboard/mouse between friends

---

## Setup

### Requirements
- Python 3.10+
- [Pygame](https://www.pygame.org/) 2.0+

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the game

```bash
python main.py
```

---

## Controls

| Action | Control |
|--------|---------|
| Aim | Move the mouse |
| Set shot power | Scroll wheel (up = more power) |
| Set shot power (alternate) | Hold right-click and drag away from ball |
| Shoot | Left-click |
| Place cue ball (ball-in-hand) | Left-click on the table |
| Dismiss foul overlay | Left-click or SPACE |
| Reset game | R |
| Quit | ESC |

---

## Rules Summary

| Rule | Description |
|------|-------------|
| Break | Player 1 breaks. Cue ball must be placed behind the head string. |
| Group assignment | Whoever pockets the first non-8 ball gets that group (solid/stripe). |
| Legal shot | First contact must be own-group ball (or 8-ball when going for the win). After contact, at least one ball must reach a cushion OR a ball must be pocketed. |
| Scratch | Cue ball pocketed → ball-in-hand for opponent. |
| Winning | Clear all 7 group balls, then pocket the 8-ball with cue ball contacting the 8-ball first. |
| Losing | 8-ball pocketed before clearing your group, or 8-ball + scratch on same shot. |

---

## Project Structure

```
8ballpool/
├── main.py              # Entry point
├── requirements.txt     # Python dependencies
├── game/                # State machine, rules, turn management, main loop
├── physics/             # Ball motion, collision resolution, pocket detection
├── entities/            # Ball, Table, Pocket, Cue data objects
├── ui/                  # Renderer, HUD, overlays
└── utils/               # Vec2 math helper, all constants
```

Each folder has its own `README.md` with detailed documentation.

---

## Physics at a Glance

- **Ball-ball collisions**: equal-mass elastic impulse, restitution coefficient e=0.96, positional overlap correction
- **Cushion collisions**: axis-aligned wall reflection, restitution e=0.75
- **Friction**: two-phase — sliding (μ=0.20) for high-speed, rolling (μ=0.018) for low-speed
- **Sub-stepping**: 4 physics sub-steps per frame for numerical stability
