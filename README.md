# 8-Ball Pool

A local two-player 8-ball pool game written in Python with Pygame.

## Features

- **Realistic physics** — elastic ball-ball collisions, cushion reflections with energy loss, two-phase rolling/sliding friction
- **Cue-ball spin** — strike the ball off centre for draw, follow, stun and side; the cue ball keeps its spin through a contact, so where it finishes is yours to choose
- **Full 8-ball rules** — break rules, solid/stripe group assignment, all foul types, win/loss conditions
- **Mouse-driven controls** — aim with the mouse, set power with scroll, keys, right-click drag, or the power bar, left-click to shoot
- **Visual aiming aid** — dashed guide line + ghost ball showing where the target ball will travel
- **A shot you can watch** — the cue holds its line, draws back and strikes; the AI's shots hold longer, so you can read where it is aiming before it plays
- **2-player local multiplayer** — pass the keyboard/mouse between friends

- **AI opponent** - searches real simulated shots (pots, banks and safeties), judges the position each one leaves behind, and thinks without ever freezing the game

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

Play against the AI:

```bash
python main.py --ai-player 2
```

Pick how strong it plays:

```bash
python main.py --ai-player 2 --ai-difficulty easy      # forgiving
python main.py --ai-player 2 --ai-difficulty medium
python main.py --ai-player 2 --ai-difficulty hard      # default
python main.py --ai-player 2 --ai-difficulty perfect   # no mercy
```

A weaker setting does not make the AI choose worse shots on purpose. It aims at
the right shot and executes it imperfectly, the same way a human does — so it
misses pots rather than doing something visibly stupid. Fouls stay under 4% at
every level.

Use a trained policy:

```bash
python main.py --ai-player 2 --ai-policy ai_policy.json
```

---

## Controls

| Action | Control |
|--------|---------|
| Aim | Move the mouse |
| Set shot power | Scroll wheel, arrow keys, + / -, or click-drag the power bar |
| Set spin | Drag on the SPIN dial, or W / S for follow and draw, A / D for side |
| Back to centre ball | C |
| Set shot power (alternate) | Hold right-click and drag away from ball |
| Shoot | Left-click (the cue draws back and strikes; aim and power lock once it starts) |
| Place cue ball (ball-in-hand) | Left-click on the table |
| Dismiss foul overlay | Left-click or SPACE |
| Reset game | R |
| Quit | ESC |

---

## AI Player

The AI lives in `ai/` and is built in four layers.

**`ai.simulation` — the ground truth.** Clones a `GameSnapshot`, applies a
candidate `Shot`, advances the real `PhysicsEngine` and evaluates the real
`RulesEngine`. Whatever the AI believes about a shot, it believes because it
played it out under the same rules you do. A shot can be run in chunks
(`ShotRun`) instead of all at once.

**`ai.geometry` — the filter.** Simulating a shot costs milliseconds; proving
that the cue ball cannot reach the object ball, or the object ball the pocket,
costs microseconds. Before anything is simulated, every (ball, pocket) pair is
checked for a clear path both ways, a playable cut angle, and a ghost-ball
position that is actually on the table. Off a full rack this rejects all ninety
combinations without running any physics. It also builds one-cushion **bank
shots** — aiming at an image of the pocket behind the rail, adjusted for the
fact that this cushion returns only 75% of the speed sent into it, so the
rebound is shallower than a mirror.

**`ai.policy` — the search.** Orders candidates so that a small budget buys
breadth: every plausible pot gets one best-guess shot before any of them gets a
second variation. When nothing pots, it plays safe instead — striking a legal
ball off-centre by a fraction of its apparent width, at a range of speeds, so
the scorer has genuinely different leaves to pick between.

**Scoring is two-ply.** A shot is worth what it pots *and* what it leaves. The
same geometry filter runs on the resulting position to ask how good the table
looks for whoever is at it next — which is a reward when the turn is kept and a
penalty when it passes. That is the difference between potting one ball and
running a rack, and it is where the safety play comes from.

### Watching it shoot

A shot used to happen the instant it was decided: the cue vanished and the ball
was already moving. That reads fine for your own shots, where you chose the line
yourself, but it made the AI's shots impossible to follow — the table simply
rearranged itself.

`game/shot_animation.py` puts three phases between the decision and the ball.
The cue holds still on the line it is going to play, draws back — further the
harder the shot — and comes forward into the ball, and the impulse lands at the
exact moment the tip arrives. The aiming line and ghost ball stay on screen
throughout, so the hold is when you can read what it intends. Your own shots
skip the hold, because you have been looking down that line the whole time.

Once the cue is moving the shot is committed: aim, power and tip offset are
locked, and further clicks are ignored until the ball is struck.

### Thinking without freezing

The search is handed out a few milliseconds per frame rather than run in one
block, and it can be interrupted part-way through a single simulation. Slicing
changes only *when* the work happens: a sliced search evaluates exactly the
same candidates in the same order as an uninterrupted one, which
`tests/test_ai.py` asserts. Across a full game, no frame spent thinking exceeds
the 16.7 ms budget of 60 fps.

`--ai-think-time` caps how long one decision may take and `--ai-candidates`
caps how many shots it may try; either can override the difficulty preset.

### Train and Evaluate

Training tunes the thirteen scoring weights by **playing matches**, not by asking
the policy to grade itself. Scoring a candidate with the same weights being
tuned makes the yardstick move with the thing it measures — a mutation that
merely inflates every reward scores better without playing better. A win rate
against a fixed opponent cannot be gamed that way, and it has a meaningful zero:
the baseline scores 50% against itself.

Evaluate a policy against the built-in baseline:

```bash
python -m ai.evaluate --policy ai_policy.json --games 8 --candidates 16

# after a night of training: is the new policy actually better?
python -m ai.evaluate --policy ai_policy_night.json --opponent ai_policy.json     --games 30 --candidates 48 --workers 12
```

Run a short training pass:

```bash
python -m ai.train --generations 8 --episodes 6 --candidates 16 --output ai_policy.json
```

Continue from a saved policy, against a stronger opponent:

```bash
python -m ai.train --input ai_policy.json --opponent ai_policy.json \
    --output ai_policy.json --generations 30 --episodes 10 --candidates 24
```

### What training costs

Every generation plays `episodes` complete games, and every shot in them is a
full search. That is the real budget: a generation of 6 games at 16 candidates
runs a few minutes, so 30 generations is an evening, not a coffee break. Raising
`--episodes` buys a less noisy signal and raising `--candidates` buys stronger
play in the games themselves; both multiply the wall-clock directly.

Sides alternate within an evaluation so the advantage of breaking cancels out,
and once the champion beats the opponent in at least 75% of a run of six or more
decided games, the opponent is promoted to the champion — a fixed opponent stops
telling good from better once it is thoroughly beaten.

### Spin

A `Shot` is an angle, a power, a tip offset and (with ball-in-hand) a placement.
The tip offset is where the cue strikes the cue ball, measured in ball radii
from its centre, and it is capped at half a radius — past that a real tip
miscues.

Only the cue ball carries spin. It is the only ball a tip ever touches, and an
object ball is taken to pick up natural roll the instant it is struck, so every
object-ball path is exactly what it was before spin existed: the pot geometry
and the shot powers tuned against it still hold.

What the cue ball does with it:

- **Through a ball.** The contact is far too brief for the cloth to change how
  the cue ball is spinning, so it keeps the roll it arrived with and suddenly
  finds itself moving at a different speed. That difference is the slip the
  cloth then works on — forward for follow, backward for draw. A full hit sends
  the cue ball on at 2/7 of the roll it was carrying, which is where both the
  follow and the draw shot come from.
- **Off a rail.** A cushion is rubber and grips: only the deviation from natural
  roll survives, reflected and damped. Side spin survives better and pushes the
  ball along the rail as it leaves, so running english widens the angle and
  reverse english tightens it.
- **At contact.** Side spin rubs against the object ball and throws it a little
  off the aiming line, which is why a cut played with english does not go quite
  where the ghost ball says.

The search treats spin as another way to vary a shot it already likes: after
each pot has had a plain attempt, the same pot is tried with draw, stun,
follow and both sides, and the two-ply score decides between them on what they
leave behind. Safety play gets the same treatment, where it matters most —
nothing pots, so the whole budget goes to that pass.

Spin needs search budget to be found at all: below roughly 30 candidates the
aim and power variations use the budget up first. `--ai-candidates 48` or more
is where cue-ball control starts showing up in the AI's game.

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
├── ai/                  # Shot geometry, search policy, headless simulator, training
├── game/                # State machine, rules, turn management, main loop
├── physics/             # Ball motion, collision resolution, pocket detection
├── entities/            # Ball, Table, Pocket, Cue data objects
├── ui/                  # Renderer, HUD, overlays
├── utils/               # Vec2 math helper, all constants
└── tests/               # Rule and end-to-end regression tests
```

Each folder has its own `README.md` with detailed documentation. The `ai/`
package contains the headless simulator, shot policy, and training/evaluation
commands.

---

## Tests

No test framework is required — each file runs on its own:

```bash
python tests/test_rules.py      # rack layout and group-clearing rules
python tests/test_game_end.py   # winning and losing a game, end to end
python tests/test_ai.py         # simulation, shot geometry, banks, search slicing
python tests/test_spin.py       # draw, follow, side off a cushion, throw
```

---

## Physics at a Glance

- **Ball-ball collisions**: equal-mass elastic impulse, restitution coefficient e=0.96, positional overlap correction
- **Cushion collisions**: axis-aligned wall reflection, restitution e=0.75
- **Friction**: two-phase — sliding (μ=0.20) for high-speed, rolling (μ=0.018) for low-speed
- **Spin**: cue ball only; slip between roll and travel decays at 3.5x the speed it feeds the ball, the textbook figure for a sphere
- **Sub-stepping**: 4 physics sub-steps per frame for numerical stability
