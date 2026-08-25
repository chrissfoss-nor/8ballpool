# =============================================================================
# state_machine.py — GameState enum and transition validation.
#
# The game moves through a well-defined set of states.  Each state determines:
#   • What input is accepted (aiming vs. watching vs. placing the cue ball)
#   • What is rendered on screen (cue / overlays)
#   • What logic runs after balls stop moving
#
# State diagram
# -------------
#
#   ┌──────────────────────────────────────────────────────────┐
#   │                         MENU                            │
#   └──────────────────────────┬──────────────────────────────┘
#                              │ start game
#   ┌──────────────────────────▼──────────────────────────────┐
#   │                      BREAK_SHOT                         │
#   │  (P1 aims and shoots the break; cue ball behind         │
#   │   the head string)                                      │
#   └──────────────────────────┬──────────────────────────────┘
#                              │ left-click (shoot)
#   ┌──────────────────────────▼──────────────────────────────┐
#   │                    BALLS_MOVING                         │
#   │  (physics running; no input accepted)                   │
#   └──┬──────────────┬────────────────┬──────────────────────┘
#      │ all stopped  │ foul           │ win / loss
#      │ continue     │                │
#   ┌──▼──────────┐  ┌▼────────────┐  ┌▼──────────────────────┐
#   │PLAYER_AIMING│  │FOUL_PENALTY │  │     GAME_OVER         │
#   │(same or     │  │(overlay;    │  │ (win/loss overlay)    │
#   │ next player)│  │ press SPACE)│  └───────────────────────┘
#   └──────────┬──┘  └──────┬──────┘
#              │ shoot       │ acknowledged
#              │             ▼
#              │         BALL_IN_HAND
#              │         (opponent places cue ball)
#              │             │ click (valid pos)
#              └─────────────┘
#                (→ PLAYER_AIMING for opponent)
# =============================================================================

from enum import Enum, auto


class GameState(Enum):
    """All possible states of the game controller."""

    MENU          = auto()   # Main/start screen (currently skipped — game auto-starts)
    BREAK_SHOT    = auto()   # First shot of the game (P1 breaks)
    PLAYER_AIMING = auto()   # Current player is aiming and setting power
    BALLS_MOVING  = auto()   # Physics simulation running — no player input
    FOUL_PENALTY  = auto()   # A foul occurred; overlay displayed, awaiting acknowledgment
    BALL_IN_HAND  = auto()   # Player is placing the cue ball (after foul)
    GAME_OVER     = auto()   # Someone won or lost; reset prompt shown


# ---------------------------------------------------------------------------
# Valid transitions
# The game.py controller checks this to guard against invalid state changes.
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[GameState, list[GameState]] = {
    GameState.MENU          : [GameState.BREAK_SHOT],
    GameState.BREAK_SHOT    : [GameState.BALLS_MOVING],
    GameState.PLAYER_AIMING : [GameState.BALLS_MOVING],
    GameState.BALLS_MOVING  : [
        GameState.PLAYER_AIMING,
        GameState.FOUL_PENALTY,
        GameState.BALL_IN_HAND,    # immediate ball-in-hand without overlay (future use)
        GameState.GAME_OVER,
    ],
    GameState.FOUL_PENALTY  : [GameState.BALL_IN_HAND],
    GameState.BALL_IN_HAND  : [GameState.PLAYER_AIMING],
    GameState.GAME_OVER     : [GameState.BREAK_SHOT],   # reset → new game
}


def can_transition(from_state: GameState, to_state: GameState) -> bool:
    """Return True if the transition from *from_state* to *to_state* is allowed."""
    return to_state in VALID_TRANSITIONS.get(from_state, [])
