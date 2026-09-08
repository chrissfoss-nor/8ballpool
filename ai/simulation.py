"""Headless game-state simulation for AI search and training.

This module intentionally uses the real PhysicsEngine and RulesEngine while
staying independent of pygame rendering and input.  It gives the AI a cheap way
to clone a table position, try a shot, and inspect the ruled outcome.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Iterable, Optional

from entities.ball import Ball, BallGroup, BallState
from entities.table import Table, create_table
from game.rules import RulesEngine, ShotResult
from game.turn_manager import Player, TurnManager
from physics.engine import PhysicsEngine
from physics.spin import apply_cue_strike, clamp_tip_offset
from utils.constants import (
    BALL_RADIUS,
    MAX_SHOT_IMPULSE,
    MIN_SHOT_IMPULSE,
    RACK_BALL_SPACING,
    TABLE_H,
    TABLE_W,
)
from utils.vector import Vec2


SIM_DT = 1.0 / 60.0
SIM_MAX_FRAMES = 3600


@dataclass(frozen=True)
class Shot:
    """A cue action chosen by an AI policy.

    cue_ball_pos is only legal when the current player has ball-in-hand.
    spin_x and spin_y are the tip offset in ball radii: +x is right-hand
    english, +y is top spin.  (0, 0) is a centre-ball hit.
    """

    angle: float
    power: float
    cue_ball_pos: Optional[tuple[float, float]] = None
    spin_x: float = 0.0
    spin_y: float = 0.0

    @property
    def clamped_power(self) -> float:
        return max(0.0, min(1.0, self.power))

    @property
    def clamped_spin(self) -> tuple[float, float]:
        return clamp_tip_offset(self.spin_x, self.spin_y)

    def velocity(self) -> Vec2:
        speed = MIN_SHOT_IMPULSE + self.clamped_power * (
            MAX_SHOT_IMPULSE - MIN_SHOT_IMPULSE
        )
        return Vec2.from_angle(self.angle, speed)


@dataclass(frozen=True)
class BallSnapshot:
    number: int
    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    spin: float = 0.0
    roll_x: float = 0.0
    roll_y: float = 0.0
    side_spin: float = 0.0
    state: str = "STATIONARY"
    group: str = "NONE"
    pocketed: bool = False

    @classmethod
    def from_ball(cls, ball: Ball) -> "BallSnapshot":
        return cls(
            number=ball.number,
            x=ball.pos.x,
            y=ball.pos.y,
            vx=ball.vel.x,
            vy=ball.vel.y,
            spin=ball.spin,
            roll_x=ball.roll.x,
            roll_y=ball.roll.y,
            side_spin=ball.side_spin,
            state=ball.state.name,
            group=ball.group.name,
            pocketed=ball.pocketed,
        )

    def to_ball(self) -> Ball:
        return Ball(
            number=self.number,
            pos=Vec2(self.x, self.y),
            vel=Vec2(self.vx, self.vy),
            spin=self.spin,
            roll=Vec2(self.roll_x, self.roll_y),
            side_spin=self.side_spin,
            state=BallState[self.state],
            group=BallGroup[self.group],
            pocketed=self.pocketed,
        )


@dataclass(frozen=True)
class PlayerSnapshot:
    name: str
    group: str = "NONE"
    pocketed_balls: tuple[int, ...] = field(default_factory=tuple)
    has_ball_in_hand: bool = False

    @classmethod
    def from_player(cls, player: Player) -> "PlayerSnapshot":
        return cls(
            name=player.name,
            group=player.group.name,
            pocketed_balls=tuple(player.pocketed_balls),
            has_ball_in_hand=player.has_ball_in_hand,
        )

    def to_player(self) -> Player:
        return Player(
            name=self.name,
            group=BallGroup[self.group],
            pocketed_balls=list(self.pocketed_balls),
            has_ball_in_hand=self.has_ball_in_hand,
        )


@dataclass(frozen=True)
class GameSnapshot:
    """Serializable game state used by AI search and self-play."""

    balls: tuple[BallSnapshot, ...]
    players: tuple[PlayerSnapshot, PlayerSnapshot]
    current_idx: int = 0
    is_break: bool = True
    break_restricted: bool = False
    game_over: bool = False
    winner_name: str = ""
    loser_name: str = ""
    loss_reason: str = ""

    @classmethod
    def from_runtime(
        cls,
        balls: Iterable[Ball],
        turns: TurnManager,
        is_break: bool,
        break_restricted: bool = False,
        game_over: bool = False,
        winner_name: str = "",
        loser_name: str = "",
        loss_reason: str = "",
    ) -> "GameSnapshot":
        return cls(
            balls=tuple(BallSnapshot.from_ball(ball) for ball in balls),
            players=(
                PlayerSnapshot.from_player(turns.players[0]),
                PlayerSnapshot.from_player(turns.players[1]),
            ),
            current_idx=turns.current_idx,
            is_break=is_break,
            break_restricted=break_restricted,
            game_over=game_over,
            winner_name=winner_name,
            loser_name=loser_name,
            loss_reason=loss_reason,
        )

    @classmethod
    def new_game(
        cls,
        seed: Optional[int] = None,
        player1_name: str = "Player 1",
        player2_name: str = "Player 2",
    ) -> "GameSnapshot":
        table = create_table()
        rng = random.Random(seed)
        turns = TurnManager(player1_name, player2_name)
        return cls.from_runtime(
            balls=_make_initial_balls(table, rng),
            turns=turns,
            is_break=True,
        )

    @property
    def current_player(self) -> PlayerSnapshot:
        return self.players[self.current_idx]

    @property
    def opponent_player(self) -> PlayerSnapshot:
        return self.players[1 - self.current_idx]

    def clone_balls(self) -> list[Ball]:
        return [ball.to_ball() for ball in self.balls]

    def clone_turns(self) -> TurnManager:
        turns = TurnManager(self.players[0].name, self.players[1].name)
        turns.players = [self.players[0].to_player(), self.players[1].to_player()]
        turns.current_idx = self.current_idx
        return turns

    def cue_ball(self) -> Optional[BallSnapshot]:
        for ball in self.balls:
            if ball.number == 0:
                return ball
        return None

    def active_cue_position(self) -> Optional[Vec2]:
        cue = self.cue_ball()
        if cue is None or cue.pocketed:
            return None
        return Vec2(cue.x, cue.y)

    def needs_ball_in_hand(self) -> bool:
        cue = self.cue_ball()
        return self.current_player.has_ball_in_hand or cue is None or cue.pocketed


@dataclass(frozen=True)
class SimulationResult:
    shot: Shot
    next_state: GameSnapshot
    shot_result: ShotResult
    frames: int
    legal: bool
    terminal: bool
    winner_name: str = ""
    error: str = ""
    first_contact_number: Optional[int] = None
    pocketed_numbers: tuple[int, ...] = field(default_factory=tuple)


class HeadlessSimulator:
    """Clone a GameSnapshot, play one shot, and apply the real 8-ball rules."""

    def __init__(
        self,
        table: Optional[Table] = None,
        dt: float = SIM_DT,
        max_frames: int = SIM_MAX_FRAMES,
    ):
        self.table = table or create_table()
        self.dt = dt
        self.max_frames = max_frames
        self.rules = RulesEngine()

    def simulate(self, snapshot: GameSnapshot, shot: Shot) -> SimulationResult:
        """Play one shot through to the end and return its ruled outcome."""
        run = self.start(snapshot, shot)
        while not run.step(self.max_frames):
            pass
        return run.result()

    def start(self, snapshot: GameSnapshot, shot: Shot) -> "ShotRun":
        """Begin a shot that the caller can advance a chunk of frames at a time."""
        return ShotRun(self, snapshot, shot)

    def _apply_rules(
        self,
        snapshot: GameSnapshot,
        balls: list[Ball],
        turns: TurnManager,
        result: ShotResult,
    ) -> GameSnapshot:
        if result.groups_assigned:
            turns.assign_groups(result.current_group)

        _sync_pocketed_balls(turns, balls)

        if result.is_foul and "re-racking" in result.foul_reason:
            reracked = _make_initial_balls(self.table, random.Random(0))
            return GameSnapshot.from_runtime(
                balls=reracked,
                turns=turns,
                is_break=True,
                break_restricted=False,
            )

        if result.game_won_by_current:
            return GameSnapshot.from_runtime(
                balls=balls,
                turns=turns,
                is_break=False,
                game_over=True,
                winner_name=turns.current_name,
            )

        if result.is_loss:
            return GameSnapshot.from_runtime(
                balls=balls,
                turns=turns,
                is_break=False,
                game_over=True,
                winner_name=turns.opponent_name,
                loser_name=turns.current_name,
                loss_reason=result.foul_reason,
            )

        if result.is_foul:
            break_restricted = "on break" in result.foul_reason
            turns.give_ball_in_hand_to_opponent()
            return GameSnapshot.from_runtime(
                balls=balls,
                turns=turns,
                is_break=False,
                break_restricted=break_restricted,
            )

        if result.switch_turn:
            turns.switch_turn()

        return GameSnapshot.from_runtime(
            balls=balls,
            turns=turns,
            is_break=False,
            break_restricted=False,
        )

    def _invalid(self, snapshot: GameSnapshot, shot: Shot, reason: str) -> SimulationResult:
        result = ShotResult(is_foul=True, foul_reason=reason, switch_turn=True)
        return SimulationResult(
            shot=shot,
            next_state=snapshot,
            shot_result=result,
            frames=0,
            legal=False,
            terminal=snapshot.game_over,
            winner_name=snapshot.winner_name,
            error=reason,
        )


class ShotRun:
    """One shot in progress, advanced in bounded chunks of physics frames.

    A single shot can take a few hundred frames to settle, which is more work
    than a 60 fps frame can absorb.  Splitting it lets the game loop drive an
    AI search without ever blocking for longer than one chunk.  Chunking
    changes nothing about the physics: the frames run in the same order with
    the same time step, so a chunked run and a straight-through run finish in
    exactly the same position.
    """

    def __init__(self, simulator: "HeadlessSimulator", snapshot: GameSnapshot, shot: Shot):
        self._sim = simulator
        self._snapshot = snapshot
        self._shot = shot
        self._frames = 0
        self._settled = False
        self._finished = False
        self._result: Optional[SimulationResult] = None
        self._engine: Optional[PhysicsEngine] = None
        self._balls: list[Ball] = []
        self._turns: Optional[TurnManager] = None

        self._setup()

    # ------------------------------------------------------------------
    # Setup and validation (all of it cheap)
    # ------------------------------------------------------------------

    def _setup(self) -> None:
        snapshot = self._snapshot
        shot = self._shot

        if snapshot.game_over:
            return self._fail("Game is already over.")

        balls = snapshot.clone_balls()
        turns = snapshot.clone_turns()
        cue_ball = _find_cue_ball(balls)
        if cue_ball is None:
            return self._fail("Cue ball is missing.")

        if snapshot.needs_ball_in_hand():
            if shot.cue_ball_pos is None:
                return self._fail("Ball-in-hand needs a cue placement.")
            placement = Vec2(shot.cue_ball_pos[0], shot.cue_ball_pos[1])
            if not is_valid_cue_ball_placement(
                placement,
                balls,
                self._sim.table,
                break_restricted=snapshot.break_restricted,
            ):
                return self._fail("Cue placement is not legal.")
            cue_ball.pos = placement
            cue_ball.reset_for_placement()
            turns.clear_ball_in_hand()
        elif shot.cue_ball_pos is not None:
            return self._fail("Cue placement is only legal for ball-in-hand.")

        if cue_ball.pocketed:
            return self._fail("Cue ball is not playable.")
        if shot.clamped_power <= 0.0:
            return self._fail("Shot power must be greater than zero.")

        engine = PhysicsEngine(self._sim.table)
        engine.reset_for_shot()
        spin_x, spin_y = shot.clamped_spin
        apply_cue_strike(cue_ball, shot.velocity(), spin_x, spin_y)

        self._engine = engine
        self._balls = balls
        self._turns = turns

    def _fail(self, reason: str) -> None:
        self._result = self._sim._invalid(self._snapshot, self._shot, reason)
        self._finished = True

    # ------------------------------------------------------------------
    # Advancing
    # ------------------------------------------------------------------

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def balls(self) -> list[Ball]:
        """The live balls of the shot in flight, for anything watching it."""
        return self._balls

    @property
    def frames(self) -> int:
        """Physics frames simulated so far."""
        return self._frames

    def step(self, max_frames: int) -> bool:
        """Advance at most *max_frames* physics frames.  True when finished."""
        if self._finished:
            return True

        engine = self._engine
        balls = self._balls
        dt = self._sim.dt
        budget = min(max_frames, self._sim.max_frames - self._frames)

        for _ in range(budget):
            self._frames += 1
            engine.update(dt, balls)
            if engine.all_stationary:
                self._settled = True
                break

        if self._settled:
            self._conclude()
        elif self._frames >= self._sim.max_frames:
            self._fail("Simulation did not settle.")

        return self._finished

    def result(self) -> SimulationResult:
        """The finished outcome; advances to completion if not there yet."""
        while not self.step(self._sim.max_frames):
            pass
        return self._result

    # ------------------------------------------------------------------
    # Outcome
    # ------------------------------------------------------------------

    def _conclude(self) -> None:
        engine = self._engine
        snapshot = self._snapshot

        shot_result = self._sim.rules.evaluate(
            engine,
            self._turns,
            self._balls,
            is_break=snapshot.is_break,
        )
        next_state = self._sim._apply_rules(
            snapshot, self._balls, self._turns, shot_result
        )
        first_contact = (
            engine.first_contact_ball.number
            if engine.first_contact_ball is not None
            else None
        )
        legal = not shot_result.is_foul and not shot_result.is_loss

        self._result = SimulationResult(
            shot=self._shot,
            next_state=next_state,
            shot_result=shot_result,
            frames=self._frames,
            legal=legal,
            terminal=next_state.game_over,
            winner_name=next_state.winner_name,
            first_contact_number=first_contact,
            pocketed_numbers=tuple(ball.number for ball in engine.pocketed_this_shot),
        )
        self._finished = True


def is_valid_cue_ball_placement(
    pos: Vec2,
    balls: Iterable[Ball],
    table: Table,
    break_restricted: bool = False,
) -> bool:
    r = BALL_RADIUS

    if (
        pos.x - r < table.left
        or pos.x + r > table.right
        or pos.y - r < table.top
        or pos.y + r > table.bottom
    ):
        return False

    if break_restricted and pos.x > table.head_string_x:
        return False

    for ball in balls:
        if ball.is_cue_ball or ball.pocketed:
            continue
        if pos.distance_sq_to(ball.pos) < (r * 2 + 2) ** 2:
            return False

    return True


def legal_target_numbers(snapshot: GameSnapshot) -> tuple[int, ...]:
    if snapshot.is_break:
        return tuple(
            ball.number
            for ball in snapshot.balls
            if ball.number != 0 and not ball.pocketed
        )

    group = BallGroup[snapshot.current_player.group]

    if group == BallGroup.NONE:
        return tuple(
            ball.number
            for ball in snapshot.balls
            if ball.number not in (0, 8) and not ball.pocketed
        )

    if _player_has_cleared_group(snapshot, snapshot.current_idx):
        return tuple(
            ball.number
            for ball in snapshot.balls
            if ball.number == 8 and not ball.pocketed
        )

    return tuple(
        ball.number
        for ball in snapshot.balls
        if BallGroup[ball.group] == group and not ball.pocketed
    )


def target_balls_remaining(snapshot: GameSnapshot, player_idx: int) -> int:
    group = BallGroup[snapshot.players[player_idx].group]
    if group not in (BallGroup.SOLID, BallGroup.STRIPE):
        return 0
    return sum(
        1
        for ball in snapshot.balls
        if BallGroup[ball.group] == group and not ball.pocketed
    )


def _player_has_cleared_group(snapshot: GameSnapshot, player_idx: int) -> bool:
    group = BallGroup[snapshot.players[player_idx].group]
    return group in (BallGroup.SOLID, BallGroup.STRIPE) and target_balls_remaining(
        snapshot, player_idx
    ) == 0


def _sync_pocketed_balls(turns: TurnManager, balls: list[Ball]) -> None:
    for player in turns.players:
        if player.group == BallGroup.NONE:
            player.pocketed_balls = []
            continue
        player.pocketed_balls = sorted(
            ball.number
            for ball in balls
            if ball.pocketed and ball.group == player.group
        )


def _find_cue_ball(balls: list[Ball]) -> Optional[Ball]:
    for ball in balls:
        if ball.is_cue_ball:
            return ball
    return None


def _make_initial_balls(table: Table, rng: random.Random) -> list[Ball]:
    balls = [Ball(number=0, pos=Vec2(table.head_x, table.top + TABLE_H * 0.50))]
    rack_positions = _compute_rack_positions(table.foot_x, table.top + TABLE_H * 0.50)
    for i, number in enumerate(_make_rack_order(rng)):
        x, y = rack_positions[i]
        balls.append(Ball(number=number, pos=Vec2(x, y)))
    return balls


def _compute_rack_positions(foot_x: float, foot_y: float) -> list[tuple[float, float]]:
    import math

    spacing = RACK_BALL_SPACING
    row_dx = spacing * math.sin(math.pi / 3)
    row_dy = spacing

    positions = []
    for row in range(5):
        num_in_row = row + 1
        row_x = foot_x + row * row_dx
        row_start_y = foot_y - (num_in_row - 1) * row_dy / 2
        for col in range(num_in_row):
            positions.append((row_x, row_start_y + col * row_dy))
    return positions


def _make_rack_order(rng: random.Random) -> list[int]:
    solids = [2, 3, 4, 5, 6, 7]
    stripes = list(range(9, 16))
    rng.shuffle(solids)
    rng.shuffle(stripes)

    remaining = solids + stripes
    rng.shuffle(remaining)

    rack: list[Optional[int]] = [None] * 15
    rack[0] = 1
    rack[4] = 8
    rack[10] = next(n for n in remaining if 1 <= n <= 7)
    rack[14] = next(n for n in remaining if 9 <= n <= 15)

    used = {rack[10], rack[14]}
    fill_pool = [n for n in remaining if n not in used]
    rng.shuffle(fill_pool)

    fill_idx = 0
    for i in range(15):
        if rack[i] is None:
            rack[i] = fill_pool[fill_idx]
            fill_idx += 1

    return [int(n) for n in rack]
