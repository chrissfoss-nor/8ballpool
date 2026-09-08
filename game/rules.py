# =============================================================================
# rules.py — RulesEngine: all 8-ball pool rule enforcement.
#
# The rules engine is called ONCE per shot, after all balls have stopped
# moving.  It reads shot-tracking data from the PhysicsEngine and the
# current TurnManager state, then returns a ShotResult describing what
# happened and what should occur next.
#
# Supported foul conditions
# -------------------------
#   SCRATCH           cue ball pocketed
#   NO_HIT            cue ball never contacted any ball
#   WRONG_BALL        first contact was opponent's ball, or 8-ball before
#                     the shooter's group is cleared
#   NO_RAIL           after contact, nothing reached a cushion and nothing
#                     was pocketed
#   8_BALL_EARLY      8-ball pocketed before own group is cleared (loss)
#   8_BALL_SCRATCH    8-ball AND cue ball both pocketed on the same shot (loss)
#
# Break special rules
# -------------------
#   • 8-ball pocketed on break → re-rack immediately (handled in game.py)
#   • Scratch on break         → ball-in-hand behind head string for opponent
#   • Legal break requirement  : at least 4 balls hit a cushion OR any ball
#                                is pocketed.  (Simplified: we require at
#                                least one ball pocketed OR cushion contacted
#                                to be generous.)
# =============================================================================

from dataclasses import dataclass, field
from typing import List, Optional

from entities.ball     import Ball, BallGroup
from game.turn_manager import TurnManager
from physics.engine    import PhysicsEngine


# ---------------------------------------------------------------------------
# Foul reason strings (used in UI overlays)
# ---------------------------------------------------------------------------
FOUL_SCRATCH        = "Cue ball scratched (pocketed)."
FOUL_NO_HIT         = "Cue ball did not contact any ball."
FOUL_WRONG_BALL     = "Cue ball hit the wrong ball first."
FOUL_NO_RAIL        = "No ball reached a cushion after contact."
FOUL_8_BALL_EARLY   = "8-ball pocketed before clearing your group!"
FOUL_8_BALL_SCRATCH = "8-ball and cue ball both pocketed!"


# ---------------------------------------------------------------------------
# ShotResult
# ---------------------------------------------------------------------------

@dataclass
class ShotResult:
    """The outcome of one shot, returned by RulesEngine.evaluate().

    Attributes
    ----------
    is_foul : bool
        True if any rule was violated.
    foul_reason : str
        Human-readable description of the foul (empty string if no foul).
    is_loss : bool
        True if the fouling player loses the game immediately
        (e.g. pocketed the 8-ball too early).
    pocketed_this_shot : list[Ball]
        All balls pocketed during this shot (may include the cue ball).
    switch_turn : bool
        True if the turn should pass to the other player.
    game_won_by_current : bool
        True if the current player has legally won the game.
    groups_assigned : bool
        True if group assignment just happened on this shot.
    current_group : BallGroup
        The group assigned to the current player (if groups_assigned is True).
    """

    is_foul              : bool      = False
    foul_reason          : str       = ""
    is_loss              : bool      = False
    pocketed_this_shot   : List[Ball]= field(default_factory=list)
    switch_turn          : bool      = False
    game_won_by_current  : bool      = False
    groups_assigned      : bool      = False
    current_group        : BallGroup = BallGroup.NONE


# ---------------------------------------------------------------------------
# RulesEngine
# ---------------------------------------------------------------------------

class RulesEngine:
    """Stateless rule evaluator.

    RulesEngine.evaluate() is pure: it only reads from the objects passed to
    it and returns a ShotResult.  The game controller applies that result to
    the TurnManager and ball list.
    """

    def evaluate(
        self,
        engine      : PhysicsEngine,
        turn_manager: TurnManager,
        all_balls   : List[Ball],
        is_break    : bool = False,
    ) -> ShotResult:
        """Evaluate the result of the shot just completed.

        Parameters
        ----------
        engine : PhysicsEngine
            Contains first_contact_ball, cushion_contacted, pocketed_this_shot.
        turn_manager : TurnManager
            Current player, opponent, groups.
        all_balls : list[Ball]
            All balls (pocketed and active).
        is_break : bool
            True if this is the opening break shot (relaxed rules apply).

        Returns
        -------
        ShotResult
        """
        result    = ShotResult()
        current   = turn_manager.current
        opponent  = turn_manager.opponent
        pocketed  = engine.pocketed_this_shot    # balls pocketed this shot

        result.pocketed_this_shot = list(pocketed)

        # ------------------------------------------------------------------
        # Identify relevant balls in this shot
        # ------------------------------------------------------------------
        scratch        = any(b.is_cue_ball  for b in pocketed)
        eight_pocketed = any(b.number == 8  for b in pocketed)

        # Own-group balls pocketed (non-cue, non-8)
        own_pocketed   = [
            b for b in pocketed
            if not b.is_cue_ball
            and b.number != 8
            and (current.group == BallGroup.NONE or b.group == current.group)
        ]
        opp_pocketed   = [
            b for b in pocketed
            if not b.is_cue_ball
            and b.number != 8
            and current.group != BallGroup.NONE
            and b.group == opponent.group
        ]
        current_had_cleared_group = self._had_cleared_group_before_shot(
            current,
            all_balls,
            pocketed,
        )

        # ------------------------------------------------------------------
        # Break-shot special handling
        # ------------------------------------------------------------------
        if is_break:
            return self._evaluate_break(result, scratch, eight_pocketed, pocketed, engine)

        # ------------------------------------------------------------------
        # Check: no hit (cue ball never touched anything)
        # ------------------------------------------------------------------
        if engine.first_contact_ball is None and not scratch:
            result.is_foul    = True
            result.foul_reason = FOUL_NO_HIT
            result.switch_turn = True
            return result

        # ------------------------------------------------------------------
        # Check: scratch (cue ball pocketed)
        # ------------------------------------------------------------------
        if scratch and eight_pocketed:
            # 8-ball AND scratch — instant loss
            result.is_foul    = True
            result.is_loss    = True
            result.foul_reason = FOUL_8_BALL_SCRATCH
            result.switch_turn = True
            return result

        if scratch:
            result.is_foul    = True
            result.foul_reason = FOUL_SCRATCH
            result.switch_turn = True
            return result

        # ------------------------------------------------------------------
        # Check: 8-ball pocketed (must be handled BEFORE wrong_ball check)
        # ------------------------------------------------------------------
        if eight_pocketed:
            return self._evaluate_eight_ball_pocket(
                result, current, engine.first_contact_ball,
                engine.cushion_contacted, all_balls,
            )

        # ------------------------------------------------------------------
        # Group assignment (first legal non-8 pocket after break)
        # ------------------------------------------------------------------
        if current.group == BallGroup.NONE and own_pocketed:
            # The first ball pocketed determines which group the current player gets
            first_ball = own_pocketed[0]
            result.groups_assigned = True
            result.current_group   = first_ball.group

        # ------------------------------------------------------------------
        # Check: wrong first contact
        # ------------------------------------------------------------------
        if engine.first_contact_ball is not None:
            wrong = self._is_wrong_first_contact(
                engine.first_contact_ball, current, current_had_cleared_group,
            )
            if wrong:
                result.is_foul    = True
                result.foul_reason = FOUL_WRONG_BALL
                result.switch_turn = True
                return result

        # ------------------------------------------------------------------
        # Check: no rail contact (and nothing pocketed) after a legal hit
        # ------------------------------------------------------------------
        if not engine.cushion_contacted and not pocketed:
            result.is_foul    = True
            result.foul_reason = FOUL_NO_RAIL
            result.switch_turn = True
            return result

        # ------------------------------------------------------------------
        # All checks passed — legal shot
        # Did the current player pocket any of their own balls?
        # ------------------------------------------------------------------
        if own_pocketed and current.group != BallGroup.NONE:
            # Legal pocket(s) of own balls → same player continues
            result.switch_turn = False
        elif result.groups_assigned and own_pocketed:
            # Groups just assigned AND balls pocketed → continue
            result.switch_turn = False
        else:
            # No own balls pocketed (or only opponent balls) → switch turn
            result.switch_turn = True

        return result

    # ------------------------------------------------------------------
    # Break evaluation
    # ------------------------------------------------------------------

    def _evaluate_break(
        self,
        result         : ShotResult,
        scratch        : bool,
        eight_pocketed : bool,
        pocketed       : List[Ball],
        engine         : PhysicsEngine,
    ) -> ShotResult:
        """Special rules for the opening break shot."""

        if eight_pocketed:
            # 8-ball on break — special case: re-rack, same player breaks again
            # Signal to game.py via a specific foul reason string
            result.is_foul    = True
            result.foul_reason = "8-ball pocketed on break — re-racking."
            result.switch_turn = False   # same player breaks again
            return result

        if scratch:
            # Scratch on break → opponent gets ball-in-hand behind head string
            result.is_foul    = True
            result.foul_reason = FOUL_SCRATCH + " (on break)"
            result.switch_turn = True
            return result

        # Legal break if at least one ball was pocketed OR a cushion was hit
        if not pocketed and not engine.cushion_contacted:
            result.is_foul    = True
            result.foul_reason = FOUL_NO_RAIL
            result.switch_turn = True
            return result

        # Legal break — groups not yet assigned; switch turn unless balls pocketed
        result.switch_turn = len(pocketed) == 0
        return result

    # ------------------------------------------------------------------
    # 8-ball pocket evaluation
    # ------------------------------------------------------------------

    def _evaluate_eight_ball_pocket(
        self,
        result           : ShotResult,
        current_player,
        first_contact    : Optional[Ball],
        cushion_contacted: bool,
        all_balls        : List[Ball],
    ) -> ShotResult:
        """Handle the case where ball 8 was pocketed (and no scratch)."""

        # Check if player has cleared their group
        if not current_player.has_cleared_group(all_balls):
            # Pocketed 8-ball too early → instant loss
            result.is_foul    = True
            result.is_loss    = True
            result.foul_reason = FOUL_8_BALL_EARLY
            result.switch_turn = True
            return result

        # Player HAS cleared their group — check the 8-ball was hit first
        if first_contact is None or first_contact.number != 8:
            # Did not contact the 8-ball first → loss
            result.is_foul    = True
            result.is_loss    = True
            result.foul_reason = "8-ball not contacted first on the winning shot."
            result.switch_turn = True
            return result

        # Winning shot!
        result.game_won_by_current = True
        result.switch_turn         = False
        return result

    # ------------------------------------------------------------------
    # Wrong first contact check
    # ------------------------------------------------------------------

    @staticmethod
    def _had_cleared_group_before_shot(current_player, all_balls, pocketed) -> bool:
        """Return True if the shooter had no group balls up before this shot."""
        if current_player.group not in (BallGroup.SOLID, BallGroup.STRIPE):
            return False

        pocketed_ids = {id(ball) for ball in pocketed}
        for ball in all_balls:
            if ball.group != current_player.group:
                continue
            if not ball.pocketed or id(ball) in pocketed_ids:
                return False
        return True

    @staticmethod
    def _is_wrong_first_contact(
        first_ball: Ball,
        current_player,
        current_had_cleared_group: bool,
    ) -> bool:
        """Return True if the cue ball's first contact was illegal.

        Legal first contacts:
          • Own-group ball   (if groups are assigned)
          • 8-ball           (if player has cleared their group)
          • Any non-8 ball   (if groups not yet assigned — post-break)
        """
        if current_player.group == BallGroup.NONE:
            # Groups not yet assigned — hitting the 8-ball directly is a foul
            if first_ball.number == 8:
                return True
            return False   # Any other first contact is legal

        if current_had_cleared_group:
            # Must hit the 8-ball first when going for the win
            return first_ball.number != 8

        # Normal play: must hit own group first
        return first_ball.group != current_player.group
