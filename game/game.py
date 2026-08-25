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
)
from entities.ball        import Ball, BallState, BallGroup
from entities.table       import create_table
from entities.cue         import Cue
from physics.engine       import PhysicsEngine
from game.state_machine   import GameState, can_transition
from game.rules           import RulesEngine, FOUL_SCRATCH
from game.turn_manager    import TurnManager
from ui.renderer          import draw_frame
from ui.hud               import draw_hud
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

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
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
        self.turns = TurnManager("Player 1", "Player 2")

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
        self._placement_valid : bool           = True
        self._mouse_pos       : tuple          = (0, 0)

        # -----------------------------------------------------------------------
        # Set up the initial rack
        # -----------------------------------------------------------------------
        self._setup_rack()
        self.cue.visible = True

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
        self.cue.reset()
        self._setup_rack()
        self.cue.visible = True
        self.physics.reset_for_shot()

    def _re_rack(self) -> None:
        """Re-rack all balls (used when 8-ball is pocketed on the break)."""
        self._setup_rack()
        self.physics.reset_for_shot()
        self.is_break    = True
        self.state       = GameState.BREAK_SHOT
        self.foul_message = ""
        self.cue.visible  = True

    # ==========================================================================
    # Event handling
    # ==========================================================================

    def _handle_event(self, event: pygame.event.Event) -> None:
        """Route a pygame event to the appropriate handler."""

        # --- Keyboard ---
        if event.type == pygame.KEYDOWN:
            self._handle_keydown(event)
            return

        # --- Mouse move ---
        if event.type == pygame.MOUSEMOTION:
            self._mouse_pos = event.pos
            if self.state in (GameState.PLAYER_AIMING, GameState.BREAK_SHOT):
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
            if event.button == 3:   # right mouse button
                self._right_dragging = False
                self.cue.end_drag()
            return

        # --- Scroll wheel ---
        if event.type == pygame.MOUSEWHEEL:
            if self.state in (GameState.PLAYER_AIMING, GameState.BREAK_SHOT):
                self.cue.on_scroll(event.y)   # y > 0 = scroll up = more power
            return

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        """Handle keyboard events."""
        if event.key == pygame.K_ESCAPE:
            pygame.event.post(pygame.event.Event(pygame.QUIT))

        elif event.key == pygame.K_r:
            # R to reset at any time
            self._full_reset()

        elif event.key == pygame.K_SPACE:
            # SPACE acknowledges foul overlay
            if self.state == GameState.FOUL_PENALTY:
                self._transition(GameState.BALL_IN_HAND)
            # SPACE dismisses the break prompt
            elif self.show_break_prompt and self.state == GameState.BREAK_SHOT:
                self.show_break_prompt = False

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        """Handle mouse button press."""
        if event.button == 1:   # left click
            self._handle_left_click(event.pos)
        elif event.button == 3:  # right click — start power drag
            if self.state in (GameState.PLAYER_AIMING, GameState.BREAK_SHOT):
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
        if self.state in (GameState.PLAYER_AIMING, GameState.BREAK_SHOT):
            self._execute_shot()

    # ==========================================================================
    # Shot execution
    # ==========================================================================

    def _execute_shot(self) -> None:
        """Apply the cue impulse to the cue ball and transition to BALLS_MOVING."""
        cue_ball = self._get_cue_ball()
        if cue_ball is None:
            return

        # Apply impulse
        cue_ball.vel   = self.cue.get_shot_vector()
        cue_ball.state = BallState.ROLLING

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

        if self.state == GameState.BALLS_MOVING:
            self.physics.update(dt, self.balls)

            if self.physics.all_stationary:
                # All balls stopped — evaluate the shot
                self._on_shot_complete()

        # Update ghost ball validity during ball-in-hand
        if self.state == GameState.BALL_IN_HAND:
            pos = Vec2(self._mouse_pos[0], self._mouse_pos[1])
            self._placement_valid = self._is_valid_placement(pos)

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
            # Record legally pocketed balls for current player
        # Record pocketed balls for the appropriate player
        self._record_pocketed_balls(result)

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

    def _record_pocketed_balls(self, result) -> None:
        """Credit legally pocketed balls to the correct player."""
        current  = self.turns.current
        opponent = self.turns.opponent

        for ball in result.pocketed_this_shot:
            if ball.is_cue_ball or ball.number == 8:
                continue
            # After group assignment, credit own-group balls to current player
            if current.group != BallGroup.NONE and ball.group == current.group:
                current.record_pocket(ball.number)
            elif opponent.group != BallGroup.NONE and ball.group == opponent.group:
                # Opponent's ball pocketed by current player — still counts for opponent
                # (only "own" pockets count; we don't award opponent credit here —
                #  the ball is just removed from the table and the foul check handles it)
                pass
            elif current.group == BallGroup.NONE and result.groups_assigned:
                # Groups just assigned on this shot
                if ball.group == result.current_group:
                    current.record_pocket(ball.number)

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
            foul_message   = hud_foul,
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
