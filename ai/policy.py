"""AI shot policy built on top of headless simulation."""

from __future__ import annotations

import json
import math
import random
import time
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Iterable, Optional

from ai.geometry import (
    PotShot,
    active_obstacles,
    bank_shots,
    path_is_clear,
    pot_difficulty,
    pot_shots,
)
from ai.simulation import (
    GameSnapshot,
    HeadlessSimulator,
    Shot,
    SimulationResult,
    is_valid_cue_ball_placement,
    legal_target_numbers,
    target_balls_remaining,
)
from entities.ball import BallGroup
from entities.table import Table, create_table
from game.rules import ShotResult
from utils.constants import BALL_RADIUS, TABLE_H, TABLE_W
from utils.vector import Vec2


#: Difficulty at which a leave is worth half of a perfect one.  A dead-straight
#: short pot scores about 90 on the pot_difficulty scale; a long thin cut runs
#: past 1500.
POSITION_DIFFICULTY_SCALE = 400.0

#: Below this many direct pots, the search also looks for banks, and takes at
#: most this many of them.  Searching banks on an open table is wasted budget.
BANK_SEARCH_THRESHOLD = 6
BANK_SEARCH_LIMIT = 10

#: How many of the nearest legal balls to build safety options against.
SAFETY_TARGETS = 4

#: Tip offsets tried on top of a shot that already pots, in ball radii
#: (+x is right-hand english, +y is top spin).  Where the cue ball stops is
#: what decides the next shot, and the tip is the only control over it:
#: bottom holds it back, top sends it on, side changes the angle it leaves a
#: cushion at.  They are searched after every pot has had a plain attempt, so
#: they buy position rather than costing the pot.
POSITION_SPINS = (
    (0.0, -0.50),   # draw
    (0.0, -0.25),   # stun
    (0.0,  0.50),   # follow
    (-0.40, 0.0),   # left
    (0.40, 0.0),    # right
)

#: Fewer offsets for safety play, where the shot is longer and the point is
#: only to leave the cue ball somewhere awkward.
SAFETY_SPINS = ((0.0, -0.50), (0.0, 0.50))


@dataclass(frozen=True)
class PolicyWeights:
    legal_reward: float = 30.0
    own_pocket_reward: float = 95.0
    opponent_pocket_penalty: float = -35.0
    group_assignment_reward: float = 35.0
    keep_turn_reward: float = 20.0
    win_reward: float = 800.0
    foul_penalty: float = -160.0
    loss_penalty: float = -900.0
    progress_reward: float = 8.0
    cue_center_reward: float = 4.0
    power_cost: float = 3.0
    # How much the position left behind is worth.  When the turn is kept this
    # rewards leaving yourself a shot; when it passes, the same measurement
    # becomes a penalty for leaving the opponent one.
    position_reward: float = 45.0
    opponent_position_penalty: float = -30.0

    @classmethod
    def from_dict(cls, data: dict) -> "PolicyWeights":
        allowed = {field.name for field in fields(cls)}
        return cls(**{key: float(value) for key, value in data.items() if key in allowed})

    def mutated(self, rng: random.Random, scale: float = 0.12) -> "PolicyWeights":
        negative_fields = {
            "foul_penalty",
            "loss_penalty",
            "opponent_pocket_penalty",
            "opponent_position_penalty",
        }
        values = {}
        for field in fields(self):
            value = float(getattr(self, field.name))
            spread = max(1.0, abs(value) * scale)
            mutated = value + rng.gauss(0.0, spread)
            if field.name in negative_fields:
                values[field.name] = -max(1.0, abs(mutated))
            else:
                values[field.name] = max(0.0, mutated)
        return PolicyWeights(**values)


@dataclass(frozen=True)
class AIDecision:
    shot: Shot
    score: float
    result: SimulationResult
    candidates_evaluated: int


class AIPlayer:
    """Choose shots by simulating candidates and scoring their ruled outcomes."""

    def __init__(
        self,
        weights: Optional[PolicyWeights] = None,
        candidate_count: int = 36,
        seed: int = 0,
        simulator: Optional[HeadlessSimulator] = None,
        table: Optional[Table] = None,
        time_budget: Optional[float] = None,
        use_spin: bool = True,
    ):
        self.weights = weights or PolicyWeights()
        self.candidate_count = max(1, candidate_count)
        self.rng = random.Random(seed)
        self.table = table or create_table()
        self.simulator = simulator or HeadlessSimulator(self.table)
        # None keeps the search purely candidate-bounded, and therefore
        # deterministic.  The game sets a budget so a decision cannot run long
        # on a crowded table; tests and training leave it unset.
        self.time_budget = time_budget

        # Turning spin off leaves a player that aims and hits exactly as well
        # but has no control over where the cue ball finishes -- which is the
        # measurement that says what the spin search is worth.
        self.position_spins = POSITION_SPINS if use_spin else ()
        self.safety_spins = SAFETY_SPINS if use_spin else ()

    @classmethod
    def load(
        cls,
        path: Optional[str | Path],
        candidate_count: int = 36,
        seed: int = 0,
        table: Optional[Table] = None,
        time_budget: Optional[float] = None,
    ) -> "AIPlayer":
        kwargs = dict(
            candidate_count=candidate_count,
            seed=seed,
            table=table,
            time_budget=time_budget,
        )
        if not path:
            return cls(**kwargs)

        policy_path = Path(path)
        if not policy_path.exists():
            return cls(**kwargs)

        with policy_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        weights = PolicyWeights.from_dict(data.get("weights", data))
        return cls(weights=weights, **kwargs)

    def choose_shot(self, snapshot: GameSnapshot) -> Shot:
        return self.choose_decision(snapshot).shot

    def start_search(self, snapshot: GameSnapshot) -> "AISearch":
        """Begin a search that the caller can advance a slice at a time."""
        return AISearch(self, snapshot)

    def choose_decision(self, snapshot: GameSnapshot) -> AIDecision:
        """Run a search to completion and return the best decision."""
        return self.start_search(snapshot).run()

    def score_result(self, snapshot: GameSnapshot, result: SimulationResult) -> float:
        """What this shot is worth, all in.

        The sum of the terms explain_result() lists, added in that order, so
        the two can never disagree about what a shot scored.
        """
        score = 0.0
        for _term, value in self.explain_result(snapshot, result):
            score += value
        return score

    def explain_result(
        self,
        snapshot: GameSnapshot,
        result: SimulationResult,
    ) -> list[tuple[str, float]]:
        """Break a shot's score into the terms that produced it.

        Returns (weight name, contribution) in the order they are summed.  A
        term is listed only when it applies, so what comes back is the actual
        reasoning behind one shot rather than a row of zeroes -- which is what
        ai/inspect.py exports and the shot inspector draws.
        """
        weights = self.weights
        shot_result = result.shot_result

        if result.error:
            return [("invalid_shot", weights.foul_penalty * 2.0)]
        if shot_result.is_loss:
            return [("loss_penalty", weights.loss_penalty)]
        if shot_result.is_foul:
            return [("foul_penalty", weights.foul_penalty)]

        terms: list[tuple[str, float]] = [("legal_reward", weights.legal_reward)]

        if shot_result.game_won_by_current:
            terms.append(("win_reward", weights.win_reward))

        if shot_result.groups_assigned:
            terms.append(("group_assignment_reward", weights.group_assignment_reward))

        if not shot_result.switch_turn:
            terms.append(("keep_turn_reward", weights.keep_turn_reward))

        own_pocketed, opponent_pocketed = _count_pocketed_for_current(
            snapshot,
            shot_result,
            result.pocketed_numbers,
        )
        terms.append(("own_pocket_reward", own_pocketed * weights.own_pocket_reward))
        terms.append(
            ("opponent_pocket_penalty", opponent_pocketed * weights.opponent_pocket_penalty)
        )

        before = target_balls_remaining(snapshot, snapshot.current_idx)
        after = target_balls_remaining(result.next_state, snapshot.current_idx)
        terms.append(
            ("progress_reward", max(0, before - after) * weights.progress_reward)
        )

        cue_pos = result.next_state.active_cue_position()
        if cue_pos is not None:
            max_dist = math.hypot(TABLE_W, TABLE_H) / 2.0
            center_score = 1.0 - min(1.0, cue_pos.distance_to(self.table.center) / max_dist)
            terms.append(("cue_center_reward", center_score * weights.cue_center_reward))

        # Second ply: what does this shot leave behind?  The same geometry
        # filter that finds candidate shots also answers how good the table
        # looks for whoever is at it next, which is what separates potting one
        # ball from running a rack.
        next_state = result.next_state
        if not next_state.game_over:
            leave = self.position_value(next_state)
            if shot_result.switch_turn:
                terms.append(
                    ("opponent_position_penalty", leave * weights.opponent_position_penalty)
                )
            else:
                terms.append(("position_reward", leave * weights.position_reward))

        terms.append(("power_cost", -(result.shot.clamped_power * weights.power_cost)))
        return terms

    def position_value(self, snapshot: GameSnapshot) -> float:
        """How promising the table is for whoever shoots next, from 0 to 1.

        Only the geometry is consulted, never the physics, so this is cheap
        enough to run once per candidate shot.
        """
        if snapshot.game_over:
            return 0.0

        # Ball-in-hand is close to the best position there is: the cue ball can
        # be put wherever the easiest shot happens to be.
        if snapshot.needs_ball_in_hand():
            return 0.95

        cue_pos = snapshot.active_cue_position()
        if cue_pos is None:
            return 0.95

        obstacles = active_obstacles(snapshot)
        legal_numbers = set(legal_target_numbers(snapshot))
        targets = [ball for ball in obstacles if ball[0] in legal_numbers]
        if not targets:
            return 0.0

        pots = pot_shots(cue_pos.x, cue_pos.y, targets, self.table, obstacles)
        if not pots:
            return 0.0

        best = 1.0 / (1.0 + pots[0].difficulty / POSITION_DIFFICULTY_SCALE)
        # Several ways to continue are worth more than a single forced one.
        spare = min(len(pots) - 1, 4) * 0.04
        return min(1.0, best + spare)

    def _generate_candidates(self, snapshot: GameSnapshot) -> Iterable[Shot]:
        """Yield candidate shots, most promising first."""
        for _kind, _target, shot in self._generate_labelled_candidates(snapshot):
            yield shot

    def _generate_labelled_candidates(
        self,
        snapshot: GameSnapshot,
    ) -> Iterable[tuple[str, Optional[int], Shot]]:
        """Yield (kind, target ball, shot), most promising first.

        Candidates are ordered so a small simulation budget buys breadth
        rather than depth: every geometrically plausible pot gets one
        best-guess shot before any of them gets a second variation.

        The kind and target are what the shot was *for* -- a direct pot at the
        4, the same pot played with draw, a safety off the nearest legal ball.
        The search itself ignores them and scores what the physics returns;
        they exist so ai/inspect.py can say why each candidate was tried.
        """
        obstacles = active_obstacles(snapshot)
        placements = self._candidate_placements(snapshot, obstacles)

        if snapshot.is_break:
            for placement in placements:
                cue_pos = _cue_position_for(snapshot, placement)
                if cue_pos is None:
                    continue
                rack_target = _frontmost_object_ball(snapshot)
                if rack_target is None:
                    continue
                base_angle = (rack_target - cue_pos).angle()
                for offset in (0.0, -0.035, 0.035, -0.07, 0.07):
                    for power in (0.95, 1.0, 0.85):
                        yield "break", None, Shot(base_angle + offset, power, placement)

        legal_numbers = set(legal_target_numbers(snapshot))
        targets = [ball for ball in obstacles if ball[0] in legal_numbers]

        plans: list[tuple[Optional[tuple[float, float]], PotShot]] = []
        for placement in placements:
            cue_pos = _cue_position_for(snapshot, placement)
            if cue_pos is None:
                continue
            for pot in pot_shots(cue_pos.x, cue_pos.y, targets, self.table, obstacles):
                plans.append((placement, pot))
        plans.sort(key=lambda plan: plan[1].difficulty)

        # Banks are only worth searching when the direct pots are thin on the
        # ground, and they sort behind every direct shot in any case.
        if len(plans) < BANK_SEARCH_THRESHOLD:
            banks: list[tuple[Optional[tuple[float, float]], PotShot]] = []
            for placement in placements:
                cue_pos = _cue_position_for(snapshot, placement)
                if cue_pos is None:
                    continue
                for bank in bank_shots(
                    cue_pos.x, cue_pos.y, targets, self.table, obstacles
                ):
                    banks.append((placement, bank))
            banks.sort(key=lambda plan: plan[1].difficulty)
            plans.extend(banks[:BANK_SEARCH_LIMIT])

        # Pass 1 - one shot at every plausible pot, easiest first.
        for placement, pot in plans:
            kind = "bank" if pot.is_bank else "pot"
            yield kind, pot.target_number, Shot(pot.aim_angle, _pot_power(pot), placement)

        # Pass 2 - refine aim, speed and spin around those same pots, easiest
        # pot first.  Spin sits in the same block as the aim and power
        # variations rather than behind all of them: a pot is worth more when
        # the cue ball finishes on the next ball, and on a modest budget that
        # is worth more than a fourth aiming tweak on the fifth-easiest pot.
        for placement, pot in plans:
            base_power = _pot_power(pot)
            target = pot.target_number
            for angle_offset in (-0.012, 0.012, -0.030, 0.030):
                yield "aim", target, Shot(
                    pot.aim_angle + angle_offset, base_power, placement
                )
            for power_scale in (0.80, 1.25, 1.60):
                yield "speed", target, Shot(
                    pot.aim_angle,
                    max(0.15, min(1.0, base_power * power_scale)),
                    placement,
                )
            for spin_x, spin_y in self.position_spins:
                yield "spin", target, Shot(
                    pot.aim_angle, base_power, placement, spin_x, spin_y
                )

        # Pass 3 - safety.  When nothing pots, the shot still has to be legal,
        # and where it leaves the cue ball decides the next visit.  Striking a
        # legal ball off-centre by a fraction of its apparent width, at a range
        # of speeds, gives the scorer genuinely different leaves to choose
        # between rather than one fixed contact.
        for placement in placements:
            cue_pos = _cue_position_for(snapshot, placement)
            if cue_pos is None:
                continue
            for _number, tx, ty in _by_distance(targets, cue_pos)[:SAFETY_TARGETS]:
                safety_target = _number
                aim = Vec2(tx, ty) - cue_pos
                distance = aim.length()
                if distance < 1e-9:
                    continue
                angle = aim.angle()
                # Half the angular width of the target ball seen from here: an
                # offset of the full amount is a miss, so fractions of it span
                # everything from dead full to the thinnest playable clip.
                spread = math.asin(
                    min(1.0, (BALL_RADIUS * 2.0) / max(distance, BALL_RADIUS * 2.0))
                )
                for fraction in (0.0, -0.55, 0.55, -0.85, 0.85):
                    for power in (0.28, 0.45, 0.75, 1.00):
                        yield "safety", safety_target, Shot(
                            angle + spread * fraction, power, placement
                        )
                # Nothing pots here, so the whole budget is on this pass and
                # the tip is worth spending some of it on: a safety lives or
                # dies on where the cue ball stops.
                for fraction in (0.0, -0.55, 0.55, -0.85, 0.85):
                    for power in (0.28, 0.45, 0.75, 1.00):
                        for spin_x, spin_y in self.safety_spins:
                            yield "safety-spin", safety_target, Shot(
                                angle + spread * fraction,
                                power,
                                placement,
                                spin_x,
                                spin_y,
                            )

        # Pass 4 - last resort, random probing.
        while True:
            placement = self.rng.choice(placements)
            yield "probe", None, Shot(
                self.rng.uniform(-math.pi, math.pi),
                self.rng.uniform(0.20, 1.0),
                placement,
            )

    def _candidate_placements(
        self,
        snapshot: GameSnapshot,
        obstacles: Optional[list[tuple[int, float, float]]] = None,
    ) -> list[Optional[tuple[float, float]]]:
        """Ball-in-hand positions, best first.

        A placement is only worth having if it creates a shot, so the cue ball
        is offered along the aiming line of every unobstructed pot, ordered by
        how easy the resulting pot would be.
        """
        if not snapshot.needs_ball_in_hand():
            return [None]

        if obstacles is None:
            obstacles = active_obstacles(snapshot)

        balls = snapshot.clone_balls()
        legal_numbers = set(legal_target_numbers(snapshot))
        targets = [ball for ball in obstacles if ball[0] in legal_numbers]

        scored: list[tuple[float, tuple[float, float]]] = []
        seen: set[tuple[float, float]] = set()

        def offer(pos: Vec2, score: float) -> None:
            if not is_valid_cue_ball_placement(
                pos,
                balls,
                self.table,
                break_restricted=snapshot.break_restricted,
            ):
                return
            key = (round(pos.x, 1), round(pos.y, 1))
            if key in seen:
                return
            seen.add(key)
            scored.append((score, pos.to_tuple()))

        for number, tx, ty in targets:
            target_pos = Vec2(tx, ty)
            for pocket in self.table.pockets:
                to_pocket = (pocket.pos - target_pos).normalize()
                if to_pocket.length_sq() < 1e-9:
                    continue
                if not path_is_clear(
                    tx, ty, pocket.pos.x, pocket.pos.y, obstacles, ignore=(number, 0)
                ):
                    continue
                object_distance = target_pos.distance_to(pocket.pos)
                for distance in (BALL_RADIUS * 5, BALL_RADIUS * 9, BALL_RADIUS * 14):
                    pos = target_pos - to_pocket * distance
                    if not path_is_clear(
                        pos.x, pos.y, tx, ty, obstacles, ignore=(number, 0)
                    ):
                        continue
                    # Placing straight behind the ball gives a dead-square cut,
                    # so the cut cosine is 1.0 by construction.
                    offer(pos, pot_difficulty(distance, object_distance, 1.0))

        for pos in self._fallback_placements():
            offer(pos, 1e6)

        scored.sort(key=lambda item: item[0])
        return [pos for _score, pos in scored[:12]] or [None]

    def _fallback_placements(self) -> list[Vec2]:
        """Generic spots used when no pot-derived placement is legal."""
        return [
            Vec2(self.table.head_x, self.table.center.y),
            Vec2(self.table.left + TABLE_W * 0.20, self.table.top + TABLE_H * 0.35),
            Vec2(self.table.left + TABLE_W * 0.20, self.table.top + TABLE_H * 0.65),
            Vec2(self.table.center.x, self.table.center.y),
            Vec2(self.table.left + TABLE_W * 0.65, self.table.top + TABLE_H * 0.35),
            Vec2(self.table.left + TABLE_W * 0.65, self.table.top + TABLE_H * 0.65),
        ]

    def _sorted_legal_targets(self, snapshot: GameSnapshot):
        legal_numbers = set(legal_target_numbers(snapshot))
        cue_pos = snapshot.active_cue_position() or self.table.center
        return sorted(
            (
                ball
                for ball in snapshot.balls
                if ball.number in legal_numbers and not ball.pocketed
            ),
            key=lambda ball: (Vec2(ball.x, ball.y).distance_sq_to(cue_pos), ball.number),
        )

    def _fallback_shot(self, snapshot: GameSnapshot) -> Shot:
        placement = self._candidate_placements(snapshot)[0]
        cue_pos = _cue_position_for(snapshot, placement) or self.table.center
        target = _frontmost_object_ball(snapshot)
        if target is None:
            return Shot(0.0, 0.5, placement)
        return Shot((target - cue_pos).angle(), 0.65, placement)


class AISearch:
    """A shot search that can be advanced in small slices.

    The game loop runs at 60 fps and cannot afford to block for the length of
    a whole search, so the work is handed out a few milliseconds at a time and
    the frame keeps rendering in between.  Slicing changes only *when* work
    happens, never which candidates are evaluated, so a search advanced in
    slices returns exactly what an uninterrupted one would.
    """

    #: How long one chunk of physics should take.  A frame with sixteen balls
    #: in motion costs roughly twenty times one with a single ball rolling, so
    #: the chunk is sized from a measured cost per frame rather than fixed.
    CHUNK_TARGET_SECONDS = 0.0025
    MIN_CHUNK_FRAMES = 3
    MAX_CHUNK_FRAMES = 240

    def __init__(self, player: AIPlayer, snapshot: GameSnapshot):
        self._player = player
        self._snapshot = snapshot
        self._candidates = player._generate_candidates(snapshot)
        self._seen: set = set()
        self._best: Optional[AIDecision] = None
        self._evaluated = 0
        self._spent = 0.0
        self._done = False
        self._run = None            # ShotRun currently being played out
        self._run_shot: Optional[Shot] = None
        self._seconds_per_frame = 0.0005

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    @property
    def done(self) -> bool:
        return self._done

    @property
    def evaluated(self) -> int:
        return self._evaluated

    @property
    def progress(self) -> float:
        """Rough 0..1 completion, for a thinking indicator."""
        by_count = self._evaluated / max(1, self._player.candidate_count)
        budget = self._player.time_budget
        by_time = self._spent / budget if budget else 0.0
        return min(1.0, max(by_count, by_time))

    # ------------------------------------------------------------------
    # Driving the search
    # ------------------------------------------------------------------

    def advance(self, slice_seconds: float) -> bool:
        """Work on the search for up to *slice_seconds*.  True when finished.

        One iteration either picks up the next candidate or advances the shot
        already in flight by a chunk of frames, so the slice can end part-way
        through a simulation instead of overrunning by a whole one.
        """
        if self._done:
            return True

        deadline = time.perf_counter() + slice_seconds
        player = self._player
        budget = player.time_budget

        while True:
            started = time.perf_counter()

            if self._run is None:
                if self._evaluated >= player.candidate_count:
                    return self._finish()
                if budget is not None and self._spent >= budget:
                    return self._finish()

                try:
                    shot = next(self._candidates)
                except StopIteration:
                    self._spent += time.perf_counter() - started
                    return self._finish()

                key = _shot_key(shot)
                if key not in self._seen:
                    self._seen.add(key)
                    self._run = player.simulator.start(self._snapshot, shot)
                    self._run_shot = shot
            else:
                before = self._run.frames
                if self._run.step(self._chunk_frames()):
                    result = self._run.result()
                    score = player.score_result(self._snapshot, result)
                    self._evaluated += 1

                    decision = AIDecision(
                        shot=self._run_shot,
                        score=score,
                        result=result,
                        candidates_evaluated=self._evaluated,
                    )
                    if self._best is None or _is_better(decision, self._best):
                        self._best = decision

                    self._run = None
                    self._run_shot = None

                elapsed = time.perf_counter() - started
                advanced = self._run.frames - before if self._run else 0
                if advanced > 0:
                    self._observe_frame_cost(elapsed / advanced)

            self._spent += time.perf_counter() - started
            if time.perf_counter() >= deadline:
                return False

    def _chunk_frames(self) -> int:
        """Frames to simulate before checking the clock again."""
        frames = int(self.CHUNK_TARGET_SECONDS / max(self._seconds_per_frame, 1e-6))
        return max(self.MIN_CHUNK_FRAMES, min(self.MAX_CHUNK_FRAMES, frames))

    def _observe_frame_cost(self, seconds: float) -> None:
        """Blend a fresh cost-per-frame sample into the running estimate."""
        self._seconds_per_frame = 0.7 * self._seconds_per_frame + 0.3 * seconds

    def run(self) -> AIDecision:
        """Advance without interruption until the search finishes."""
        while not self.advance(float("inf")):
            pass
        return self.decision()

    def decision(self) -> AIDecision:
        """The best decision found, falling back to a safe shot if none was."""
        if self._best is not None:
            return self._best

        player = self._player
        fallback = player._fallback_shot(self._snapshot)
        result = player.simulator.simulate(self._snapshot, fallback)
        return AIDecision(
            shot=fallback,
            score=player.score_result(self._snapshot, result),
            result=result,
            candidates_evaluated=1,
        )

    def _finish(self) -> bool:
        self._done = True
        return True


def load_policy_weights(path: Optional[str | Path]) -> PolicyWeights:
    if not path:
        return PolicyWeights()
    policy_path = Path(path)
    if not policy_path.exists():
        return PolicyWeights()
    with policy_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return PolicyWeights.from_dict(data.get("weights", data))


def save_policy_weights(
    path: str | Path,
    weights: PolicyWeights,
    metadata: Optional[dict] = None,
) -> None:
    policy_path = Path(path)
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "weights": asdict(weights),
        "metadata": metadata or {},
    }
    with policy_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _count_pocketed_for_current(
    snapshot: GameSnapshot,
    shot_result: ShotResult,
    pocketed_numbers: tuple[int, ...],
) -> tuple[int, int]:
    current_group = BallGroup[snapshot.current_player.group]
    if current_group == BallGroup.NONE and shot_result.groups_assigned:
        current_group = shot_result.current_group

    own = 0
    opponent = 0
    for number in pocketed_numbers:
        if number in (0, 8):
            continue
        group = _group_for_number(number)
        if current_group == BallGroup.NONE:
            continue
        if group == current_group:
            own += 1
        else:
            opponent += 1
    return own, opponent


def _group_for_number(number: int) -> BallGroup:
    if 1 <= number <= 7:
        return BallGroup.SOLID
    if 9 <= number <= 15:
        return BallGroup.STRIPE
    if number == 8:
        return BallGroup.EIGHT
    return BallGroup.CUE


def _estimate_power(distance: float) -> float:
    return max(0.22, min(1.0, 0.22 + distance / 1700.0))


def _pot_power(pot: PotShot) -> float:
    """Enough speed to carry the object ball to the pocket, plus margin.

    The cue ball sheds speed over its own run, and a thin cut passes on only
    part of what is left, so both legs are weighted.
    """
    effective = pot.cue_distance + pot.object_distance / max(pot.cut_cos, 0.25)
    if pot.is_bank:
        # A cushion returns only three quarters of the speed it is given.
        effective /= 0.75
    return max(0.22, min(1.0, 0.26 + effective / 1900.0))


def _by_distance(
    targets: list[tuple[int, float, float]],
    cue_pos: Vec2,
) -> list[tuple[int, float, float]]:
    """Targets ordered nearest-first from the cue ball."""
    return sorted(
        targets,
        key=lambda ball: (cue_pos.x - ball[1]) ** 2 + (cue_pos.y - ball[2]) ** 2,
    )


def _cue_position_for(
    snapshot: GameSnapshot,
    placement: Optional[tuple[float, float]],
) -> Optional[Vec2]:
    if placement is not None:
        return Vec2(placement[0], placement[1])
    return snapshot.active_cue_position()


def _frontmost_object_ball(snapshot: GameSnapshot) -> Optional[Vec2]:
    candidates = [
        Vec2(ball.x, ball.y)
        for ball in snapshot.balls
        if ball.number != 0 and not ball.pocketed
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda pos: pos.x)


def _shot_key(shot: Shot) -> tuple:
    placement = None
    if shot.cue_ball_pos is not None:
        placement = (round(shot.cue_ball_pos[0], 2), round(shot.cue_ball_pos[1], 2))
    spin_x, spin_y = shot.clamped_spin
    return (
        round(shot.angle, 5),
        round(shot.power, 3),
        placement,
        round(spin_x, 3),
        round(spin_y, 3),
    )


def _is_better(candidate: AIDecision, incumbent: AIDecision) -> bool:
    if candidate.score > incumbent.score + 1e-9:
        return True
    if abs(candidate.score - incumbent.score) > 1e-9:
        return False
    return _shot_key(candidate.shot) < _shot_key(incumbent.shot)
