# =============================================================================
# turn_manager.py — Tracks whose turn it is and each player's scoring state.
#
# TurnManager is a simple data object — it does not enforce rules (that is
# rules.py's job).  The rules engine tells it what to do after evaluating a
# shot, and TurnManager updates its internal state accordingly.
# =============================================================================

from dataclasses import dataclass, field
from typing import List

from entities.ball import BallGroup


# ---------------------------------------------------------------------------
# Player
# ---------------------------------------------------------------------------

@dataclass
class Player:
    """All the information the game needs about one human player.

    Attributes
    ----------
    name : str
        Display name shown in the HUD.
    group : BallGroup
        The group of balls this player is trying to pocket.
        Starts as BallGroup.NONE and is assigned after the first legal pocket.
    pocketed_balls : list[int]
        Ball numbers legally pocketed by this player (in order).
    has_ball_in_hand : bool
        True while the player needs to place the cue ball.
    """

    name            : str
    group           : BallGroup  = BallGroup.NONE
    pocketed_balls  : List[int]  = field(default_factory=list)
    has_ball_in_hand: bool        = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def balls_remaining(self, all_balls) -> int:
        """How many balls of this player's group are still on the table."""
        if self.group not in (BallGroup.SOLID, BallGroup.STRIPE):
            return 0
        return sum(1 for b in all_balls
                   if b.group == self.group and not b.pocketed)

    def has_cleared_group(self, all_balls) -> bool:
        """True once no ball of this player's group is left on the table.

        Read off the table rather than off pocketed_balls. A ball the
        opponent pockets for you stays down and still clears your group;
        counting only your own pots left such a player permanently short of
        seven, so they could never legally play the 8 ball and never win.
        """
        if self.group not in (BallGroup.SOLID, BallGroup.STRIPE):
            return False
        return self.balls_remaining(all_balls) == 0

    def record_pocket(self, ball_number: int) -> None:
        """Record that this player legally pocketed *ball_number*."""
        if ball_number not in self.pocketed_balls:
            self.pocketed_balls.append(ball_number)

    def reset(self) -> None:
        """Reset this player for a new game."""
        self.group            = BallGroup.NONE
        self.pocketed_balls   = []
        self.has_ball_in_hand = False


# ---------------------------------------------------------------------------
# TurnManager
# ---------------------------------------------------------------------------

class TurnManager:
    """Manages which player is active and switches turns when required.

    Attributes
    ----------
    players : list[Player]
        Exactly two players: index 0 = Player 1, index 1 = Player 2.
    current_idx : int
        Index of the currently active player (0 or 1).
    """

    def __init__(self, player1_name: str = "Player 1", player2_name: str = "Player 2"):
        self.players     : List[Player] = [
            Player(name=player1_name),
            Player(name=player2_name),
        ]
        self.current_idx : int = 0   # Player 1 always goes first (breaks)

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    @property
    def current(self) -> Player:
        """The player whose turn it is right now."""
        return self.players[self.current_idx]

    @property
    def opponent(self) -> Player:
        """The player who is NOT currently shooting."""
        return self.players[1 - self.current_idx]

    @property
    def current_name(self) -> str:
        return self.current.name

    @property
    def opponent_name(self) -> str:
        return self.opponent.name

    # ------------------------------------------------------------------
    # Turn switching
    # ------------------------------------------------------------------

    def switch_turn(self) -> None:
        """Give the turn to the other player."""
        self.current_idx = 1 - self.current_idx

    def give_ball_in_hand_to_opponent(self) -> None:
        """Switch turn and mark the new current player as having ball-in-hand."""
        self.switch_turn()
        self.current.has_ball_in_hand = True

    def clear_ball_in_hand(self) -> None:
        """Clear the ball-in-hand flag for the current player."""
        self.current.has_ball_in_hand = False

    # ------------------------------------------------------------------
    # Group assignment
    # ------------------------------------------------------------------

    def assign_groups(self, current_gets: BallGroup) -> None:
        """Assign ball groups to both players.

        Parameters
        ----------
        current_gets : BallGroup
            The group the current player claims (SOLID or STRIPE).
        """
        opponent_gets = (
            BallGroup.STRIPE if current_gets == BallGroup.SOLID else BallGroup.SOLID
        )
        self.current.group  = current_gets
        self.opponent.group = opponent_gets

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset both players and start from Player 1's turn."""
        for p in self.players:
            p.reset()
        self.current_idx = 0
