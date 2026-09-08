# =============================================================================
# game.py — Game class: main loop, event dispatch, state transitions, and
# the glue that connects physics, rules, UI and entities.
#
# Responsibilities
# ----------------
#   • Own and initialise all game objects (balls, table, cue, engines).
#   • Run the pygame event loop.
#   • Call PhysicsEngine.update() every frame while balls are moving.
#   • After balls stop, call RulesEngine.evaluate() and act on the result.
#   • Render the scene by calling draw_frame(), draw_hud(), and overlays.
#   • Handle user input for aiming, power, shooting, and ball-in-hand.
#   • Support R to reset the game.
#
# State machine transitions are validated by state_machine.can_transition().
# =============================================================================

import math
import random
import pygame
from typing import List, Optional

from utils.vector    import Vec2
from utils.constants import (
    WINDOW_W, WINDOW_H, FPS,
    TABLE_OFFSET_X, TABLE_OFFSET_Y, TABLE_W, TABLE_H,
    BALL_RADIUS, RACK_BALL_SPACING, HUD_HEIGHT, POWER_BAR_HEIGHT,
    POWER_SCROLL_STEP, SPIN_NUDGE_STEP, SHOT_AIM_HOLD_SECONDS,
)
from entities.ball        import Ball, BallState, BallGroup
from entities.table       import create_table
from entities.cue         import Cue
from physics.engine       import PhysicsEngine
from physics.spin         import apply_cue_strike
from game.shot_animation  import ShotAnimation
from game.state_machine   import GameState, can_transition
from game.rules           import RulesEngine, FOUL_SCRATCH
from game.turn_manager    import TurnManager
from ai.policy            import AIPlayer, AISearch
from ai.simulation        import GameSnapshot
from ui.renderer          import draw_frame
from ui.hud               import (
    draw_hud, get_power_bar_hit_rect, get_power_bar_track_rect,
    get_spin_dial_rect, spin_from_pointer,
)
from ui.overlay           import (
    draw_foul_overlay, draw_ball_in_hand_overlay,
    draw_win_overlay, draw_loss_overlay, draw_break_prompt,
)


class Game:
    """Top-level game controller.

    Usage::
        game = Game(screen, clock)
        game.run()
    """

    def __init__(
        self,
        screen: pygame.Surface,
        clock: pygame.time.Clock,
        ai_player_index: Optional[int] = None,
        ai_policy_path: Optional[str] = None,
        ai_candidate_count: int = 36,
        ai_delay: float = 0.35,
        ai_time_budget: Optional[float] = 0.9,
        ai_slice: float = 0.006,
        ai_aim_noise: float = 0.0,
    ):
        self.screen = screen
        self.clock  = clock

        # -----------------------------------------------------------------------
        # Build the table geometry (immutable after construction)
        # -----------------------------------------------------------------------
        self.table = create_table()

        # -----------------------------------------------------------------------
        # Engines
        # -----------------------------------------------------------------------
        self.physics = PhysicsEngine(self.table)
        self.rules   = RulesEngine()

        # -----------------------------------------------------------------------
        # Player & turn management
        # -----------------------------------------------------------------------
        if ai_player_index is not None and ai_player_index not in (0, 1):
            raise ValueError("ai_player_index must be 0, 1, or None")

        player_names = ["Player 1", "Player 2"]
        if ai_player_index is not None:
            player_names[ai_player_index] = "AI Player"
        self.turns = TurnManager(player_names[0], player_names[1])
        self.ai_player_index: Optional[int] = ai_player_index
        self.ai_player: Optional[AIPlayer] = None
        if ai_player_index is not None:
            self.ai_player = AIPlayer.load(
                ai_policy_path,
                candidate_count=ai_candidate_count,
                seed=0,
                table=self.table,
                time_budget=ai_time_budget,
            )
        self.ai_delay = max(0.0, ai_delay)
        self._ai_timer = self.ai_delay

        # The AI searches a slice at a time so the loop keeps rendering while
        # it thinks.  ai_slice is how much of each frame it may consume.
        self.ai_slice = max(0.001, ai_slice)
        self._ai_search: Optional[AISearch] = None

        # Standard deviation, in radians, of the error added to the AI's aim
        # when it actually plays the shot.  The search itself stays exact --
        # the AI knows the right shot and simply does not execute it perfectly,
        # which is what makes a weaker setting feel like a weaker player rather
        # than a stupid one.
        self.ai_aim_noise = max(0.0, ai_aim_noise)
        self._ai_hand = random.Random()

        # -----------------------------------------------------------------------
        # Game state
        # -----------------------------------------------------------------------
        self.state            : GameState      = GameState.BREAK_SHOT
        self.balls            : List[Ball]     = []
        self.cue              : Cue            = Cue()
        self.is_break         : bool           = True    # True for the opening shot
        self.winner_name      : str            = ""
        self.loss_reason      : str            = ""
        self.loser_name       : str            = ""
        self.foul_message     : str            = ""      # shown in HUD strip
        self.pending_foul_msg : str            = ""      # stored until overlay dismissed
        self.break_restricted : bool           = False   # ball-in-hand restricted to left half
        self.show_break_prompt: bool           = True    # show the opening instruction

        # -----------------------------------------------------------------------
        # Input helpers
        # -----------------------------------------------------------------------
        self._right_dragging  : bool           = False
        self._power_dragging  : bool           = False
        self._spin_dragging   : bool           = False

        # The wind-up currently being played, if any.  While one is running the
        # shot is already committed: the aim, the power and the tip offset are
        # locked, and no further input is taken until the ball is struck.
        self._shot_anim       : Optional[ShotAnimation] = None
        self._placement_valid : bool           = True
        self._mouse_pos       : tuple          = (0, 0)

        # -----------------------------------------------------------------------
        # Set up the initial rack
        # -----------------------------------------------------------------------
        self._setup_rack()
        self.cue.visible = True
        self._arm_ai_turn()

    # ==========================================================================
    # Main loop
    # ==========================================================================

    def run(self) -> None:
        """Start and run the game loop until the window is closed."""
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0   # seconds

            # --- Events ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self._handle_event(event)

            # --- Update ---
            self._update(dt)

            # --- Render ---
            self._render()

            pygame.display.flip()

    # ==========================================================================
    # Setup / reset
    # ==========================================================================

    def _setup_rack(self) -> None:
        """Place all 16 balls: triangle rack + cue ball at head spot."""
        self.balls = []

        # Cue ball at head spot
        head_x = TABLE_OFFSET_X + TABLE_W * 0.25
        head_y = TABLE_OFFSET_Y + TABLE_H * 0.50
        cue_ball = Ball(number=0, pos=Vec2(head_x, head_y))
        self.balls.append(cue_ball)

        # Rack positions (triangle at foot spot)
        foot_x = TABLE_OFFSET_X + TABLE_W * 0.75
        foot_y = TABLE_OFFSET_Y + TABLE_H * 0.50
        rack_positions = _compute_rack_positions(foot_x, foot_y)

        # The order of balls in the rack (standard 8-ball layout)
        rack_order = _make_rack_order()

        for i, number in enumerate(rack_order):
            pos = rack_positions[i]
            self.balls.append(Ball(number=number, pos=Vec2(pos[0], pos[1])))

    def _full_reset(self) -> None:
        """Reset everything for a new game."""
        self.turns.reset()
        self.is_break          = True
        self.state             = GameState.BREAK_SHOT
        self.winner_name       = ""
        self.loss_reason       = ""
        self.loser_name        = ""
        self.foul_message      = ""
        self.pending_foul_msg  = ""
        self.break_restricted  = False
        self.show_break_prompt = True
        self._right_dragging   = False
        self._power_dragging   = False
        self._spin_dragging    = False
        self._shot_anim        = None
        self.cue.reset()
        self._setup_rack()
        self.cue.visible = True
        self.physics.reset_for_shot()
        self._arm_ai_turn()

    def _re_rack(self) -> None:
        """Re-rack all balls (used when 8-ball is pocketed on the break)."""
        self._shot_anim = None
        self.cue.pullback = 0.0
        self._setup_rack()
        self.physics.reset_for_shot()
        self.is_break    = True
        self.state       = GameState.BREAK_SHOT
        self.foul_message = ""
        self.cue.visible  = True
        self._arm_ai_turn()

    # ==========================================================================
    # Event handling
    # ==========================================================================

    def _handle_event(self, event: pygame.event.Event) -> None:
        """Route a pygame event to the appropriate handler."""

        # --- Keyboard ---
        if event.type == pygame.KEYDOWN:
            self._handle_keydown(event)
            return

        if self._ai_controls_current_state():
            return

        # --- Mouse move ---
        if event.type == pygame.MOUSEMOTION:
            self._mouse_pos = event.pos
            if self._spin_dragging and self._is_aiming_state():
                self.cue.set_tip(*spin_from_pointer(event.pos))
                return
            if self._power_dragging and self._is_aiming_state():
                self._set_power_from_pointer(event.pos)
                return
            if self._is_aiming_state():
                cue_ball = self._get_cue_ball()
                if cue_ball:
                    self.cue.on_mouse_move(event.pos, cue_ball.pos)
            if self._right_dragging:
                cue_ball = self._get_cue_ball()
                if cue_ball:
                    self.cue.update_drag(event.pos, cue_ball.pos)
            return

        # --- Mouse button down ---
        if event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_down(event)
            return

        # --- Mouse button up ---
        if event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self._power_dragging = False
                self._spin_dragging  = False
            if event.button == 3:   # right mouse button
                self._right_dragging = False
                self.cue.end_drag()
            return

        # --- Scroll wheel ---
        if event.type == pygame.MOUSEWHEEL:
            if self._is_aiming_state():
                self.cue.on_scroll(event.y)   # y > 0 = scroll up = more power
            return

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        """Handle keyboard events."""
        if event.key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

        elif event.key == pygame.K_r:
            # R to reset at any time
            self._full_reset()

        elif self._ai_controls_current_state():
            return

        elif event.key == pygame.K_SPACE:
            # SPACE acknowledges foul overlay
            if self.state == GameState.FOUL_PENALTY:
                self._transition(GameState.BALL_IN_HAND)
            # SPACE dismisses the break prompt
            elif self.show_break_prompt and self.state == GameState.BREAK_SHOT:
                self.show_break_prompt = False

        elif self._is_aiming_state():
            if event.key in (pygame.K_UP, pygame.K_RIGHT, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.cue.adjust_power(POWER_SCROLL_STEP)
            elif event.key in (pygame.K_DOWN, pygame.K_LEFT, pygame.K_MINUS, pygame.K_KP_MINUS):
                self.cue.adjust_power(-POWER_SCROLL_STEP)
            # Where the tip strikes the cue ball: W/S for follow and draw,
            # A/D for left and right english, C back to centre ball.
            elif event.key == pygame.K_w:
                self.cue.nudge_tip(0.0, SPIN_NUDGE_STEP)
            elif event.key == pygame.K_s:
                self.cue.nudge_tip(0.0, -SPIN_NUDGE_STEP)
            elif event.key == pygame.K_a:
                self.cue.nudge_tip(-SPIN_NUDGE_STEP, 0.0)
            elif event.key == pygame.K_d:
                self.cue.nudge_tip(SPIN_NUDGE_STEP, 0.0)
            elif event.key == pygame.K_c:
                self.cue.reset_tip()

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        """Handle mouse button press."""
        if event.button == 1:   # left click
            if (
                self._is_aiming_state()
                and not self.show_break_prompt
                and get_spin_dial_rect().collidepoint(event.pos)
            ):
                self._spin_dragging = True
                self.cue.set_tip(*spin_from_pointer(event.pos))
                return
            if (
                self._is_aiming_state()
                and not self.show_break_prompt
                and get_power_bar_hit_rect().collidepoint(event.pos)
            ):
                self._power_dragging = True
                self._set_power_from_pointer(event.pos)
                return
            self._handle_left_click(event.pos)
        elif event.button == 3:  # right click — start power drag
            if self._is_aiming_state():
                self._right_dragging = True
                self.cue.start_drag(event.pos)

    def _handle_left_click(self, pos: tuple) -> None:
        """Left-click: shoot, dismiss overlay, or place cue ball."""

        # Dismiss break prompt
        if self.show_break_prompt and self.state == GameState.BREAK_SHOT:
            self.show_break_prompt = False
            return

        # Acknowledge foul overlay
        if self.state == GameState.FOUL_PENALTY:
            self._transition(GameState.BALL_IN_HAND)
            return

        # Place cue ball (ball-in-hand)
        if self.state == GameState.BALL_IN_HAND:
            self._try_place_cue_ball(pos)
            return

        # Shoot (both aiming states)
        if self._is_aiming_state():
            self._execute_shot()

    # ==========================================================================
    # Shot execution
    # ==========================================================================

    def _execute_shot(self) -> None:
        """Commit to the shot and start the cue's wind-up.

        The ball is not touched here.  The cue holds its line, draws back and
        comes forward, and _strike_ball() fires the moment the tip arrives --
        which is what makes an AI shot something you can watch rather than a
        table that rearranges itself.
        """
        cue_ball = self._get_cue_ball()
        if cue_ball is None:
            return
        if self.cue.power <= 0.0:
            return
        if self._shot_anim is not None:
            return   # already winding up; the shot is committed

        # Your own shots skip the hold: you have been looking down that line
        # the whole time you were aiming.
        hold = SHOT_AIM_HOLD_SECONDS if self._is_ai_turn() else 0.0
        self._shot_anim = ShotAnimation(
            self.cue.power,
            reach=self.cue.rest_gap - BALL_RADIUS,
            aim_hold=hold,
        )
        self.cue.pullback = 0.0

    def _update_shot_animation(self, dt: float) -> None:
        """Advance the wind-up, and strike the ball when the tip arrives."""
        if self._shot_anim is None:
            return
        if self._shot_anim.update(dt):
            self._strike_ball()
        else:
            self.cue.pullback = self._shot_anim.offset

    def _strike_ball(self) -> None:
        """The tip has reached the ball: send it, and let the physics take over."""
        self._shot_anim = None
        self.cue.pullback = 0.0

        cue_ball = self._get_cue_ball()
        if cue_ball is None:
            return

        # Apply impulse, with whatever spin the tip offset asks for
        apply_cue_strike(
            cue_ball,
            self.cue.get_shot_vector(),
            self.cue.tip.x,
            self.cue.tip.y,
        )

        # Spin is deliberate, never inherited: the next shot starts on centre
        # ball unless it is asked for again.
        self.cue.reset_tip()

        # Hide the cue during flight
        self.cue.visible = False

        # Reset physics shot tracking
        self.physics.reset_for_shot()

        # Transition
        self._transition(GameState.BALLS_MOVING)

    # ==========================================================================
    # Ball-in-hand placement
    # ==========================================================================

    def _try_place_cue_ball(self, pos: tuple) -> None:
        """Attempt to place the cue ball at mouse position."""
        target = Vec2(pos[0], pos[1])

        # Validate position
        if not self._is_valid_placement(target):
            return   # Ignore invalid clicks

        # Move cue ball
        cue_ball = self._get_cue_ball()
        if cue_ball is None:
            return
        cue_ball.pos = target
        cue_ball.reset_for_placement()

        # Clear ball-in-hand flag
        self.turns.clear_ball_in_hand()
        self.break_restricted = False
        self.foul_message     = ""
        self.cue.visible      = True

        self._transition(GameState.PLAYER_AIMING)

    def _is_valid_placement(self, pos: Vec2) -> bool:
        """Return True if *pos* is a valid cue ball placement."""
        r = BALL_RADIUS

        # Must be on the felt
        if (pos.x - r < self.table.left  or pos.x + r > self.table.right or
            pos.y - r < self.table.top   or pos.y + r > self.table.bottom):
            return False

        # After break scratch: must be behind head string (left half of table)
        if self.break_restricted:
            if pos.x > self.table.head_string_x:
                return False

        # Must not overlap any other active ball
        for ball in self.balls:
            if ball.is_cue_ball or ball.pocketed:
                continue
            if pos.distance_sq_to(ball.pos) < (r * 2 + 2) ** 2:
                return False

        return True

    # ==========================================================================
    # Update
    # ==========================================================================

    def _update(self, dt: float) -> None:
        """Per-frame game logic."""

        self._update_shot_animation(dt)

        if self.state == GameState.BALLS_MOVING:
            self.physics.update(dt, self.balls)

            if self.physics.all_stationary:
                # All balls stopped — evaluate the shot
                self._on_shot_complete()

        # Update ghost ball validity during ball-in-hand
        if self.state == GameState.BALL_IN_HAND:
            pos = Vec2(self._mouse_pos[0], self._mouse_pos[1])
            self._placement_valid = self._is_valid_placement(pos)

        self._update_ai(dt)

    # ==========================================================================
    # Shot completion and rules evaluation
    # ==========================================================================

    def _on_shot_complete(self) -> None:
        """Called once all balls have stopped after a shot."""

        result = self.rules.evaluate(
            self.physics,
            self.turns,
            self.balls,
            is_break=self.is_break,
        )

        # Mark break as over after the first shot
        self.is_break = False

        # Assign ball groups if needed
        if result.groups_assigned:
            self.turns.assign_groups(result.current_group)

        # Refresh both players' pocketed lists from the table
        self._sync_pocketed_balls()

        # Handle special break case: 8-ball pocketed → re-rack
        if result.is_foul and "re-racking" in result.foul_reason:
            self._re_rack()
            return

        # Game over (win)
        if result.game_won_by_current:
            self.winner_name = self.turns.current_name
            self._transition(GameState.GAME_OVER)
            return

        # Game over (loss — 8 ball too early, or 8+scratch)
        if result.is_loss:
            self.loser_name  = self.turns.current_name
            self.loss_reason = result.foul_reason
            self.winner_name = self.turns.opponent_name
            self._transition(GameState.GAME_OVER)
            return

        # Normal foul → show overlay, give ball-in-hand to opponent
        if result.is_foul:
            self.pending_foul_msg = result.foul_reason
            # Determine if restricted placement (break scratch)
            self.break_restricted = "on break" in result.foul_reason
            self.turns.give_ball_in_hand_to_opponent()
            self._transition(GameState.FOUL_PENALTY)
            return

        # Legal shot — switch turn if needed
        if result.switch_turn:
            self.turns.switch_turn()

        # Clear foul message on a legal shot
        self.foul_message = ""

        # Restore the cue ball if it was pocketed by a foul (already handled above)
        # If we're here, the cue ball is still on the table.

        self.cue.visible = True
        self._transition(GameState.PLAYER_AIMING)

    def _sync_pocketed_balls(self) -> None:
        """Recompute each player's pocketed list from the table.

        Which list a ball lands in is decided by who owns its group, not by
        who struck it: a ball your opponent pockets for you stays down and
        still counts as one of yours. Rebuilding from the table each time
        also picks up balls potted on the break, which go down before either
        group has been assigned.
        """
        for player in self.turns.players:
            if player.group == BallGroup.NONE:
                player.pocketed_balls = []
                continue
            player.pocketed_balls = sorted(
                ball.number for ball in self.balls
                if ball.pocketed and ball.group == player.group
            )

    # ==========================================================================
    # State transitions
    # ==========================================================================

    def _transition(self, new_state: GameState) -> None:
        """Move to *new_state* if the transition is valid."""
        if not can_transition(self.state, new_state):
            # Allow BREAK_SHOT → PLAYER_AIMING (not in table but useful)
            if not (self.state == GameState.BREAK_SHOT and new_state == GameState.PLAYER_AIMING):
                return   # Silently ignore invalid transitions
        self.state = new_state
        self._arm_ai_turn()

    # ==========================================================================
    # Rendering
    # ==========================================================================

    def _render(self) -> None:
        """Draw the full frame."""

        # Determine if ball-in-hand is active
        ball_in_hand = (self.state == GameState.BALL_IN_HAND)

        # Draw table + balls + cue
        draw_frame(
            surface        = self.screen,
            table          = self.table,
            balls          = self.balls,
            cue            = self.cue,
            state_name     = self.state.name,
            ball_in_hand   = ball_in_hand,
            mouse_pos      = self._mouse_pos,
            placement_valid= self._placement_valid,
        )

        # Draw HUD panels (top + bottom strips)
        current = self.turns.current
        opp     = self.turns.opponent
        # Determine foul msg to show
        hud_foul = ""
        if self.state == GameState.FOUL_PENALTY:
            hud_foul = f"FOUL: {self.pending_foul_msg}"
        elif self.foul_message:
            hud_foul = self.foul_message

        draw_hud(
            surface        = self.screen,
            player1_name   = self.turns.players[0].name,
            player2_name   = self.turns.players[1].name,
            player1_group  = self.turns.players[0].group.name,
            player2_group  = self.turns.players[1].group.name,
            p1_pocketed    = self.turns.players[0].pocketed_balls,
            p2_pocketed    = self.turns.players[1].pocketed_balls,
            current_player = self.turns.current_idx,
            power          = self.cue.power,
            spin           = self.cue.tip.to_tuple(),
            foul_message   = hud_foul,
            status_message = "AI is thinking..." if self.ai_is_thinking else "",
        )

        # Overlays (drawn last, on top of everything)
        self._draw_overlays()

    def _draw_overlays(self) -> None:
        """Draw any active overlay panels."""

        if self.state == GameState.GAME_OVER:
            if self.winner_name and not self.loser_name:
                draw_win_overlay(self.screen, self.winner_name)
            else:
                draw_loss_overlay(
                    self.screen,
                    self.loser_name,
                    self.loss_reason,
                    self.winner_name,
                )
            return

        if self.state == GameState.FOUL_PENALTY:
            draw_foul_overlay(
                self.screen,
                self.pending_foul_msg,
                self.turns.current_name,   # opponent is current after give_ball_in_hand
            )
            return

        if self.state == GameState.BALL_IN_HAND:
            draw_ball_in_hand_overlay(
                self.screen,
                self.turns.current_name,
                restricted=self.break_restricted,
            )
            return

        if self.show_break_prompt and self.state == GameState.BREAK_SHOT:
            draw_break_prompt(self.screen, self.turns.current_name)

    # ==========================================================================
    # Helpers
    # ==========================================================================

    def _get_cue_ball(self) -> Optional[Ball]:
        """Return the cue ball, or None if it is pocketed."""
        for ball in self.balls:
            if ball.is_cue_ball and not ball.pocketed:
                return ball
        # Cue ball is pocketed — create a ghost one for placement
        for ball in self.balls:
            if ball.is_cue_ball:
                return ball
        return None

    def _is_aiming_state(self) -> bool:
        """Return True while players may aim and set shot power.

        A wind-up in flight means the shot is already committed, so nothing is
        accepted until the ball has been struck -- which also keeps the AI from
        starting a fresh search over its own shot.
        """
        return (
            self.state in (GameState.PLAYER_AIMING, GameState.BREAK_SHOT)
            and self._shot_anim is None
        )

    def _set_power_from_pointer(self, pos: tuple) -> None:
        """Map a pointer position on the HUD power bar to cue power."""
        track = get_power_bar_track_rect()
        if track.width <= 0:
            return
        self.cue.set_power((pos[0] - track.left) / track.width)

    def _is_ai_turn(self) -> bool:
        return (
            self.ai_player is not None
            and self.ai_player_index is not None
            and self.turns.current_idx == self.ai_player_index
        )

    def _ai_controls_current_state(self) -> bool:
        return self._is_ai_turn() and self.state in (
            GameState.BREAK_SHOT,
            GameState.PLAYER_AIMING,
            GameState.FOUL_PENALTY,
            GameState.BALL_IN_HAND,
        )

    def _arm_ai_turn(self) -> None:
        # Any search still in flight was started for a position that no longer
        # applies, so it is dropped rather than resumed.
        self._ai_search = None
        if self._ai_controls_current_state():
            self._ai_timer = self.ai_delay
        else:
            self._ai_timer = 0.0

    @property
    def ai_is_thinking(self) -> bool:
        """True while a search is in flight, for the thinking indicator."""
        return self._ai_search is not None and not self._ai_search.done

    def _update_ai(self, dt: float) -> None:
        """Let the AI acknowledge, place, and shoot when it owns the turn.

        The search runs a slice per frame instead of blocking, so the table
        keeps animating at full frame rate while the AI decides.
        """
        if self._shot_anim is not None:
            return   # its own shot is on the way; nothing to decide

        if self.ai_player is None or not self._ai_controls_current_state():
            self._ai_search = None
            return

        self._ai_timer = max(0.0, self._ai_timer - dt)
        if self._ai_timer > 0.0:
            return

        if self.state == GameState.FOUL_PENALTY:
            self._transition(GameState.BALL_IN_HAND)
            return

        if self.show_break_prompt and self.state == GameState.BREAK_SHOT:
            self.show_break_prompt = False

        if self._ai_search is None:
            self._ai_search = self.ai_player.start_search(self._make_ai_snapshot())

        if not self._ai_search.advance(self.ai_slice):
            return   # still thinking; render this frame and come back

        decision = self._ai_search.decision()
        self._ai_search = None
        shot = decision.shot

        if self.state == GameState.BALL_IN_HAND:
            if shot.cue_ball_pos is None:
                placement_pos = self._find_ai_fallback_placement()
                if placement_pos is None:
                    self._ai_timer = self.ai_delay
                    return
                self._try_place_cue_ball(placement_pos)
                return

            placement = Vec2(shot.cue_ball_pos[0], shot.cue_ball_pos[1])
            if not self._is_valid_placement(placement):
                placement_pos = self._find_ai_fallback_placement()
                if placement_pos is None:
                    self._ai_timer = self.ai_delay
                    return
                self._try_place_cue_ball(placement_pos)
                return

            self._try_place_cue_ball(shot.cue_ball_pos)
            if not self._is_ai_turn() or not self._is_aiming_state():
                return

        if self._is_aiming_state():
            self.cue.angle = shot.angle + self._ai_aim_error()
            self.cue.set_power(shot.clamped_power)
            self.cue.set_tip(*shot.clamped_spin)
            self._execute_shot()

    def _ai_aim_error(self) -> float:
        """Random aiming error for the current difficulty, in radians."""
        if self.ai_aim_noise <= 0.0:
            return 0.0
        return self._ai_hand.gauss(0.0, self.ai_aim_noise)

    def _make_ai_snapshot(self) -> GameSnapshot:
        return GameSnapshot.from_runtime(
            balls=self.balls,
            turns=self.turns,
            is_break=self.is_break,
            break_restricted=self.break_restricted,
            game_over=self.state == GameState.GAME_OVER,
            winner_name=self.winner_name,
            loser_name=self.loser_name,
            loss_reason=self.loss_reason,
        )

    def _find_ai_fallback_placement(self) -> Optional[tuple[float, float]]:
        candidates = [
            Vec2(self.table.head_x, self.table.center.y),
            Vec2(self.table.left + TABLE_W * 0.20, self.table.top + TABLE_H * 0.35),
            Vec2(self.table.left + TABLE_W * 0.20, self.table.top + TABLE_H * 0.65),
            Vec2(self.table.center.x, self.table.center.y),
            Vec2(self.table.left + TABLE_W * 0.65, self.table.top + TABLE_H * 0.35),
            Vec2(self.table.left + TABLE_W * 0.65, self.table.top + TABLE_H * 0.65),
        ]
        for pos in candidates:
            if self._is_valid_placement(pos):
                return pos.to_tuple()
        return None


# =============================================================================
# Rack helper functions  (module-level, not methods — they don't need 'self')
# =============================================================================

def _compute_rack_positions(foot_x: float, foot_y: float) -> list:
    """Return the 15 rack positions as (x, y) tuples.

    The triangle has its apex closest to the foot spot.
    Row 1 = apex (1 ball), Row 2 = 2 balls, ... Row 5 = 5 balls.
    Balls are spaced RACK_BALL_SPACING apart edge-to-edge.
    """
    import math as _math
    spacing = RACK_BALL_SPACING                  # centre-to-centre distance
    # In a tight triangle the rows step sideways by the 60° triangle height,
    # not by a full ball width -- that is what makes neighbouring rows touch.
    row_dx  = spacing * _math.sin(_math.pi / 3)  # horizontal step between rows
    row_dy  = spacing                            # vertical step within a row

    positions = []
    for row in range(5):          # rows 0..4 (apex = row 0)
        num_in_row = row + 1
        # Each row is centred on the foot line and pushed one step further back
        row_x       = foot_x + row * row_dx
        row_start_y = foot_y - (num_in_row - 1) * row_dy / 2
        for col in range(num_in_row):
            positions.append((row_x, row_start_y + col * row_dy))

    return positions   # 15 positions total


def _make_rack_order() -> list:
    """Return a list of ball numbers 1-15 in the correct rack order.

    Standard 8-ball rack rules:
      • Position 0 (apex): ball 1
      • Position 4 (center of row 3): ball 8
      • Position 10 (bottom-left of row 5): one solid
      • Position 14 (bottom-right of row 5): one stripe
      • All others: random
    """
    solids  = [2, 3, 4, 5, 6, 7]   # 1 is fixed at apex
    stripes = list(range(9, 16))    # 9-15

    random.shuffle(solids)
    random.shuffle(stripes)

    # Build a combined random pool for the remaining 12 positions
    remaining = solids + stripes
    random.shuffle(remaining)

    # 15-position rack:
    # Pos  0: apex  → ball 1
    # Pos  4: center of row 3 → ball 8
    # Pos 10: back-left  → one solid (remaining[0])
    # Pos 14: back-right → one stripe (remaining[1])
    # Others: remaining pool

    rack = [None] * 15
    rack[0]  = 1
    rack[4]  = 8

    # Ensure back corners are solid+stripe
    rack[10] = next(n for n in remaining if 1 <= n <= 7)
    rack[14] = next(n for n in remaining if 9 <= n <= 15)

    used = {rack[10], rack[14]}
    fill_pool = [n for n in remaining if n not in used]
    random.shuffle(fill_pool)

    fill_idx = 0
    for i in range(15):
        if rack[i] is None:
            rack[i] = fill_pool[fill_idx]
            fill_idx += 1

    return rack
