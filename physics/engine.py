# =============================================================================
# engine.py — PhysicsEngine: master update loop for all ball motion.
#
# Each call to update() advances the simulation by *dt* seconds using
# NUM_SUBSTEPS sub-steps for stability.  Within each sub-step:
#   1. Friction is applied to every active ball.
#   2. All ball-ball pairs are checked and resolved.
#   3. Cushion/pocket collisions are resolved.
#
# The engine tracks shot-level state that the rules engine needs:
#   • first_contact_ball  — which ball the cue ball hit first
#   • cushion_contacted   — did ANY ball touch a cushion during this shot?
#   • pocketed_this_shot  — list of balls pocketed during this shot
#   • all_stationary      — True once every active ball has stopped
#
# Usage
# -----
#   engine = PhysicsEngine(table)
#   engine.reset_for_shot()                  # call before applying cue impulse
#   cue_ball.vel = cue.get_shot_vector()
#   cue_ball.state = BallState.ROLLING
#   # inside the game loop:
#   engine.update(dt, balls)
#   if engine.all_stationary:
#       result = rules_engine.evaluate(engine)
# =============================================================================

from typing import List, Optional

from utils.constants import NUM_SUBSTEPS
from entities.ball   import Ball, BallState
from entities.table  import Table
from physics.friction          import apply_friction
from physics.ball_collision    import resolve_pair
from physics.cushion_collision import resolve_cushions_and_pockets


class PhysicsEngine:
    """Drives all ball motion for one game of pool.

    Attributes
    ----------
    table : Table
        Immutable table geometry used for boundary checks.
    first_contact_ball : Ball | None
        The first non-cue ball the cue ball touched during the current shot.
        None until the first collision; set once and not changed again until
        reset_for_shot() is called.
    cushion_contacted : bool
        True if at least one ball (including the cue ball) touched a cushion
        during the current shot.
    pocketed_this_shot : list[Ball]
        All balls pocketed since the last reset_for_shot() call.
    all_stationary : bool
        Becomes True once every active (non-pocketed) ball is stationary.
        The game loop uses this as the signal to evaluate the shot result.
    _first_contact_recorded : bool
        Internal flag so we only fire the first-contact callback once.
    """

    def __init__(self, table: Table):
        self.table = table

        # Shot-level state (reset each shot)
        self.first_contact_ball      : Optional[Ball] = None
        self.cushion_contacted       : bool           = False
        self.pocketed_this_shot      : List[Ball]     = []
        self.all_stationary          : bool           = True
        self._first_contact_recorded : bool           = False

    # ------------------------------------------------------------------
    # Per-shot reset
    # ------------------------------------------------------------------

    def reset_for_shot(self) -> None:
        """Call this immediately before the cue ball is given its impulse.

        Clears all shot-level tracking so the rules engine sees only events
        from the current shot.
        """
        self.first_contact_ball      = None
        self.cushion_contacted       = False
        self.pocketed_this_shot      = []
        self.all_stationary          = False
        self._first_contact_recorded = False

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    def update(self, dt: float, balls: List[Ball]) -> None:
        """Advance the simulation by *dt* seconds.

        Parameters
        ----------
        dt : float
            Frame delta-time in seconds (capped to avoid large jumps).
        balls : list[Ball]
            All balls in the game (active and pocketed; pocketed ones are
            skipped automatically).
        """
        # Cap dt to avoid explosive physics if the frame rate drops badly
        dt = min(dt, 1.0 / 20.0)

        # Divide dt into sub-steps for numerical stability
        dt_sub = dt / NUM_SUBSTEPS

        for _ in range(NUM_SUBSTEPS):
            self._substep(dt_sub, balls)

        # After all sub-steps, check if every active ball has stopped
        self.all_stationary = all(
            b.state in (BallState.STATIONARY, BallState.POCKETED)
            for b in balls
        )

    # ------------------------------------------------------------------
    # Single sub-step
    # ------------------------------------------------------------------

    def _substep(self, dt: float, balls: List[Ball]) -> None:
        """One physics sub-step: friction → ball-ball → cushion/pocket."""

        active = [b for b in balls if not b.pocketed]

        # 1. Apply friction to every active ball
        for ball in active:
            apply_friction(ball, dt)

        # 2. Integrate positions (move balls according to their velocity)
        for ball in active:
            if ball.state == BallState.ROLLING:
                ball.pos += ball.vel * dt

        # 3. Resolve all ball-ball collision pairs
        for i in range(len(active)):
            for j in range(i + 1, len(active)):
                resolve_pair(
                    active[i],
                    active[j],
                    first_contact_callback=self._on_ball_ball_contact,
                )

        # 4. Cushion reflection and pocket detection
        for ball in active:
            resolve_cushions_and_pockets(
                ball,
                self.table,
                cushion_contact_callback=self._on_cushion_contact,
                pocket_callback=self._on_ball_pocketed,
            )

    # ------------------------------------------------------------------
    # Callbacks (invoked during sub-step)
    # ------------------------------------------------------------------

    def _on_ball_ball_contact(self, ball_a: Ball, ball_b: Ball) -> None:
        """Record the first cue-ball contact during this shot."""
        if self._first_contact_recorded:
            return   # Already recorded — only care about the first hit

        # Determine which is the cue ball and which is the object ball
        if ball_a.is_cue_ball:
            self.first_contact_ball = ball_b
            self._first_contact_recorded = True
        elif ball_b.is_cue_ball:
            self.first_contact_ball = ball_a
            self._first_contact_recorded = True

    def _on_cushion_contact(self, ball: Ball) -> None:
        """Note that at least one ball touched a cushion during this shot."""
        self.cushion_contacted = True

    def _on_ball_pocketed(self, ball: Ball) -> None:
        """Add ball to the pocketed list for this shot."""
        if ball not in self.pocketed_this_shot:
            self.pocketed_this_shot.append(ball)
