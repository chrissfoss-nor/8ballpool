# game/

Game logic, state machine, rules enforcement, and the main game loop.

## Files

| File | Purpose |
|------|---------|
| `game.py` | `Game` class — owns the main loop (`run()`), all game objects, event dispatch, state transitions, rendering calls, and the connect between physics and rules. |
| `shot_animation.py` | `ShotAnimation` — the wind-up between choosing a shot and striking it: hold the aim, draw back, strike. Owns nothing but time; the game applies the impulse when the tip arrives. |
| `state_machine.py` | `GameState` enum + `VALID_TRANSITIONS` dict. `can_transition(from, to)` guards all state changes. |
| `turn_manager.py` | `TurnManager` + `Player` dataclass. Tracks whose turn it is, each player's group/pocketed balls, and ball-in-hand status. |
| `rules.py` | `RulesEngine.evaluate()` — pure function that reads `PhysicsEngine` shot data, applies 8-ball pool rules, and returns a `ShotResult`. |

## State machine

```
MENU → BREAK_SHOT → BALLS_MOVING
                  ↕
            PLAYER_AIMING ←──── BALL_IN_HAND
                                     ↑
                               FOUL_PENALTY
                                     ↑
                              BALLS_MOVING → GAME_OVER
```

## Foul types

| Foul | Effect |
|------|--------|
| Scratch (cue ball pocketed) | Ball-in-hand for opponent |
| No hit (cue misses everything) | Ball-in-hand for opponent |
| Wrong ball first contact | Ball-in-hand for opponent |
| No rail (nothing touched a cushion, nothing pocketed) | Ball-in-hand for opponent |
| 8-ball pocketed early | **Instant loss** |
| 8-ball + scratch together | **Instant loss** |

## Ball groups

Groups (solid 1–7 vs stripe 9–15) are NOT assigned at the start.  They are assigned to whoever first legally pockets a non-8 ball after the break.  The opponent automatically gets the other group.

## Winning

Clear all 7 of your group's balls, then pocket the 8-ball with the cue ball making first contact with the 8-ball.  No scratch.
