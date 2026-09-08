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

        # The active set only shrinks within a frame (balls can be pocketed
        # but never un-pocketed), and every routine below re-checks .pocketed
        # itself, so it is safe to build this list once per frame instead of
        # once per sub-step.
        active = [b for b in balls if not b.pocketed]

        for _ in range(NUM_SUBSTEPS):
            self._substep(dt_sub, active)

        # After all sub-steps, check if every active ball has stopped
        self.all_stationary = all(
            b.state in (BallState.STATIONARY, BallState.POCKETED)
            for b in balls
        )

    # ------------------------------------------------------------------
    # Single sub-step
    # ------------------------------------------------------------------

    def _substep(self, dt: float, active: List[Ball]) -> None:
        """One physics sub-step: friction → ball-ball → cushion/pocket.

        Only *moving* balls are integrated, collided and reflected.  A ball at
        rest cannot start moving on its own, so the only pairs worth testing
        are those with at least one roller, and a resting ball cannot cross a
        cushion or drop into a pocket.  On a typical shot one or two of the
        sixteen balls are in motion, so this turns 120 pair tests per sub-step
        into a handful.
        """
        rolling = BallState.ROLLING

        # 1. Apply friction to the balls that are actually moving.
        #    (apply_friction is a no-op for stationary and pocketed balls.)
        moving = [b for b in active if b.state is rolling]
        if not moving:
            return

        for ball in moving:
            apply_friction(ball, dt)

        # 2. Integrate positions.  Friction above may have brought a ball to
        #    rest, so the state is re-checked rather than trusting `moving`.
        for ball in moving:
            if ball.state is rolling:
                pos = ball.pos
                vel = ball.vel
                pos.x += vel.x * dt
                pos.y += vel.y * dt

        # 3. Resolve ball-ball collisions for every pair containing a roller.
        #    The pairs are still visited in the original index order: when
        #    several balls collide in the same sub-step the resolution order
        #    changes the outcome, so skipping work must not reorder it.
        on_contact = self._on_ball_ball_contact
        count = len(active)
        for i in range(count):
            ball_a = active[i]
            a_rolling = ball_a.state is rolling
            for j in range(i + 1, count):
                ball_b = active[j]
                if a_rolling or ball_b.state is rolling:
                    resolve_pair(ball_a, ball_b, first_contact_callback=on_contact)

        # 4. Cushion reflection and pocket detection.  A collision above can
        #    set a previously resting ball rolling, so the set is rebuilt.
        for ball in active:
            if ball.state is rolling and not ball.pocketed:
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
