"""Export one AI decision, in full, as JSON.

The AI does not think in a way you can watch at sixty frames a second.  It
proposes a few dozen shots, plays every one of them out under the real physics
and the real rules, breaks each outcome into thirteen weighted terms, and keeps
the highest total.  All of that happens between two frames and then vanishes,
leaving only the shot it played.

This module keeps the working.  For a given position it records every candidate
in the order the search would reach it: what the shot was *for*, what the
physics did with it, where every ball finished, and which terms added up to its
score.  ai_visualizer.html draws the result.

    python -m ai.inspect --out ai_decisions.json
    python -m ai.inspect --scenario safety --candidates 120 --out one.json

The page carries a copy of that JSON inline, in its <script id="decisions">
block, so it opens straight from disk with no server.  To refresh what it
shows, re-run the export and replace that block with the new file.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import fields
from datetime import datetime, timezone
from typing import Optional

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from ai.geometry import (
    CONTACT_DISTANCE,
    MIN_CUT_COS,
    active_obstacles,
    bank_shots,
    path_is_clear,
    pot_shots,
)
from ai.policy import AIPlayer, _shot_key, load_policy_weights
from ai.simulation import (
    GameSnapshot,
    legal_target_numbers,
)
from entities.ball import Ball, BallGroup
from entities.table import create_table
from game.turn_manager import TurnManager
from utils.constants import BALL_RADIUS
from utils.vector import Vec2


# ---------------------------------------------------------------------------
# Positions worth inspecting
#
# Each one is a different kind of decision: a break where geometry can tell it
# nothing, an open table where several pots compete, a table where nothing pots
# at all and the shot has to be a safety, and the last ball of the game.
# ---------------------------------------------------------------------------

def _cleared_table(group: BallGroup = BallGroup.SOLID):
    """A table with every ball pocketed, ready to have a few put back."""
    table = create_table()
    turns = TurnManager("You", "AI Player")
    turns.assign_groups(group)
    balls = [Ball(number=n, pos=Vec2(0.0, 0.0)) for n in range(16)]
    for ball in balls:
        ball.pocketed = True
    return table, turns, balls


def _place(balls, positions):
    for number, (x, y) in positions.items():
        balls[number].pos = Vec2(float(x), float(y))
        balls[number].pocketed = False


def scenario_break():
    snapshot = GameSnapshot.new_game(seed=7, player1_name="AI Player", player2_name="You")
    return (
        snapshot,
        "The break",
        "Nothing is potted yet and the geometry filter rejects all ninety "
        "ball-and-pocket pairs, so every candidate here is a way of hitting "
        "the rack rather than a pot.",
    )


def scenario_open_table():
    _table, turns, balls = _cleared_table()
    _place(balls, {
        0:  (330.0, 300.0),
        1:  (560.0, 250.0),
        3:  (820.0, 520.0),
        5:  (980.0, 300.0),
        9:  (700.0, 430.0),
        12: (450.0, 560.0),
        8:  (900.0, 620.0),
    })
    snapshot = GameSnapshot.from_runtime(balls=balls, turns=turns, is_break=False)
    return (
        snapshot,
        "Open table",
        "Three solids have a clear run to a pocket. The search gives each one "
        "a plain attempt before it starts varying aim, speed and spin on the "
        "easiest of them.",
    )


def scenario_safety():
    _table, turns, balls = _cleared_table()
    # The three remaining solids sit in a cluster with stripes on every side
    # of it.  Checked against the geometry filter: no solid has a line to any
    # pocket, direct or off a cushion.
    _place(balls, {
        0:  (250.0, 300.0),
        2:  (690.0, 415.0),
        4:  (720.0, 445.0),
        6:  (750.0, 415.0),
        10: (690.0, 380.0),
        11: (750.0, 480.0),
        13: (660.0, 445.0),
        15: (780.0, 445.0),
        8:  (1000.0, 300.0),
    })
    snapshot = GameSnapshot.from_runtime(balls=balls, turns=turns, is_break=False)
    return (
        snapshot,
        "Nothing pots",
        "The last three solids are locked in a cluster with stripes around it. "
        "No solid has a line to any pocket, direct or off a cushion, so the "
        "whole budget goes to the safety pass and the shot is judged on where "
        "it leaves the cue ball rather than on what it pots.",
    )


def scenario_eight_ball():
    _table, turns, balls = _cleared_table()
    _place(balls, {
        0:  (420.0, 250.0),
        8:  (700.0, 380.0),
        10: (900.0, 300.0),
        14: (520.0, 560.0),
    })
    for number in range(1, 8):
        turns.players[0].pocketed_balls.append(number)
    snapshot = GameSnapshot.from_runtime(balls=balls, turns=turns, is_break=False)
    return (
        snapshot,
        "On the 8",
        "The group is cleared, so the 8 is the only legal ball. Potting it wins "
        "the game and scratching on it loses -- the two largest weights in the "
        "table, pulling in opposite directions on the same shot.",
    )


SCENARIOS = {
    "break": scenario_break,
    "open": scenario_open_table,
    "safety": scenario_safety,
    "eight": scenario_eight_ball,
}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _round(value: float, places: int = 2) -> float:
    return round(float(value), places)


def _ball_rows(snapshot: GameSnapshot) -> list[dict]:
    return [
        {
            "n": ball.number,
            "x": _round(ball.x, 1),
            "y": _round(ball.y, 1),
            "group": ball.group,
        }
        for ball in snapshot.balls
        if not ball.pocketed
    ]


def _geometry_section(player: AIPlayer, snapshot: GameSnapshot) -> dict:
    """What the filter saw before a single frame of physics was run."""
    obstacles = active_obstacles(snapshot)
    legal = set(legal_target_numbers(snapshot))
    targets = [ball for ball in obstacles if ball[0] in legal]
    cue = snapshot.active_cue_position()

    pots, banks = [], []
    if cue is not None:
        pots = pot_shots(cue.x, cue.y, targets, player.table, obstacles)
        banks = bank_shots(cue.x, cue.y, targets, player.table, obstacles)

    def row(shot):
        pocket = player.table.pockets[shot.pocket_index]
        return {
            "target": shot.target_number,
            "pocket": [_round(pocket.pos.x, 1), _round(pocket.pos.y, 1)],
            "ghost": [_round(shot.ghost_x, 1), _round(shot.ghost_y, 1)],
            "aim_angle": _round(shot.aim_angle, 5),
            "cut_cos": _round(shot.cut_cos, 3),
            "difficulty": _round(shot.difficulty, 1),
            "is_bank": shot.is_bank,
        }

    return {
        "legal_targets": sorted(legal),
        "pairs_considered": len(targets) * len(player.table.pockets),
        "pots": [row(shot) for shot in pots],
        "banks": [row(shot) for shot in banks[:10]],
    }


def _pair_scan(player: AIPlayer, snapshot: GameSnapshot) -> list[dict]:
    """Every (ball, pocket) pair the geometry filter looks at, and its verdict.

    This walks the same tests as ai.geometry.pot_shots in the same order, and
    records why each pair was thrown out.  On a full rack all ninety of them
    fail here, before a single frame of physics is run -- which is the cheapest
    and least visible thing the AI does, and worth being able to watch.
    """
    table = player.table
    obstacles = active_obstacles(snapshot)
    legal = set(legal_target_numbers(snapshot))
    targets = [ball for ball in obstacles if ball[0] in legal]
    cue = snapshot.active_cue_position()
    if cue is None:
        return []

    rows = []
    for number, tx, ty in targets:
        for pocket_index, pocket in enumerate(table.pockets):
            px, py = pocket.pos.x, pocket.pos.y
            to_x, to_y = px - tx, py - ty
            object_distance = math.hypot(to_x, to_y)
            row = {
                "target": number,
                "pocket": pocket_index,
                "px": _round(px, 1),
                "py": _round(py, 1),
                "tx": _round(tx, 1),
                "ty": _round(ty, 1),
            }
            if object_distance < 1e-6:
                row.update(ok=False, why="on the pocket")
                rows.append(row)
                continue
            to_x /= object_distance
            to_y /= object_distance

            ghost_x = tx - to_x * CONTACT_DISTANCE
            ghost_y = ty - to_y * CONTACT_DISTANCE
            row["gx"] = _round(ghost_x, 1)
            row["gy"] = _round(ghost_y, 1)

            if not (table.left <= ghost_x <= table.right and table.top <= ghost_y <= table.bottom):
                row.update(ok=False, why="no room behind the ball")
                rows.append(row)
                continue

            aim_x, aim_y = ghost_x - cue.x, ghost_y - cue.y
            cue_distance = math.hypot(aim_x, aim_y)
            if cue_distance < 1e-6:
                row.update(ok=False, why="cue ball is on the line")
                rows.append(row)
                continue
            aim_x /= cue_distance
            aim_y /= cue_distance

            if aim_x * to_x + aim_y * to_y < MIN_CUT_COS:
                row.update(ok=False, why="cut too thin")
                rows.append(row)
                continue

            if not path_is_clear(tx, ty, px, py, obstacles, ignore=(number, 0)):
                row.update(ok=False, why="ball blocked from the pocket")
                rows.append(row)
                continue

            if not path_is_clear(cue.x, cue.y, ghost_x, ghost_y, obstacles, ignore=(number, 0)):
                row.update(ok=False, why="cue ball blocked")
                rows.append(row)
                continue

            row.update(ok=True, why="clear")
            rows.append(row)
    return rows


def _trajectory(player: AIPlayer, snapshot: GameSnapshot, shot, stride: int = 5) -> list:
    """Sample where every ball is, every *stride* frames of the shot.

    The search runs this simulation and throws the motion away, keeping only
    the outcome.  Keeping it is what lets the shot be replayed at the speed it
    actually happened.
    """
    run = player.simulator.start(snapshot, shot)
    if not run.balls:
        return []
    frames = []
    step = 0
    while True:
        if step % stride == 0:
            frames.append([
                [ball.number, int(ball.pos.x), int(ball.pos.y)]
                for ball in run.balls
                if not ball.pocketed
            ])
        if run.step(1):
            break
        step += 1
        if step > 3600:
            break
    frames.append([
        [ball.number, int(ball.pos.x), int(ball.pos.y)]
        for ball in run.balls
        if not ball.pocketed
    ])
    return frames


def inspect_snapshot(
    player: AIPlayer,
    snapshot: GameSnapshot,
    name: str,
    description: str,
    scenario_id: str,
    stride: int = 5,
) -> dict:
    """Play out every candidate the search would reach and record all of it."""
    seen: set = set()
    candidates: list[dict] = []
    best_index: Optional[int] = None
    best_score = float("-inf")

    for kind, target, shot in player._generate_labelled_candidates(snapshot):
        if len(candidates) >= player.candidate_count:
            break
        key = _shot_key(shot)
        if key in seen:
            continue
        seen.add(key)

        result = player.simulator.simulate(snapshot, shot)
        trajectory = _trajectory(player, snapshot, shot, stride=stride)
        terms = player.explain_result(snapshot, result)
        score = sum(value for _term, value in terms)
        after = result.next_state
        cue_after = after.active_cue_position()

        index = len(candidates)
        if score > best_score:
            best_score, best_index = score, index

        spin_x, spin_y = shot.clamped_spin
        candidates.append({
            "i": index,
            "kind": kind,
            "target": target,
            "angle": _round(shot.angle, 5),
            "power": _round(shot.clamped_power, 3),
            "spin": [_round(spin_x, 3), _round(spin_y, 3)],
            "score": _round(score, 2),
            "terms": [[term, _round(value, 2)] for term, value in terms],
            "outcome": {
                "legal": bool(result.legal and not result.shot_result.is_foul),
                "foul": result.shot_result.foul_reason or result.error,
                "potted": list(result.pocketed_numbers),
                "first_contact": result.first_contact_number,
                "keeps_turn": not result.shot_result.switch_turn,
                "won": bool(result.shot_result.game_won_by_current),
                "lost": bool(result.shot_result.is_loss),
                "frames": result.frames,
            },
            "roll": trajectory,
            "after": {
                "cue": None if cue_after is None else [_round(cue_after.x, 1), _round(cue_after.y, 1)],
                "balls": [
                    [ball.number, _round(ball.x, 1), _round(ball.y, 1)]
                    for ball in after.balls
                    if not ball.pocketed
                ],
                "position_value": _round(player.position_value(after), 3),
            },
        })

    return {
        "id": scenario_id,
        "name": name,
        "description": description,
        "player_group": snapshot.current_player.group,
        "ball_in_hand": snapshot.needs_ball_in_hand(),
        "is_break": snapshot.is_break,
        "balls": _ball_rows(snapshot),
        "geometry": _geometry_section(player, snapshot),
        "pair_scan": _pair_scan(player, snapshot),
        "candidates": candidates,
        "chosen": best_index,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="ai_decisions.json")
    parser.add_argument("--policy", default=None, help="Policy JSON to inspect.")
    parser.add_argument("--candidates", type=int, default=90)
    parser.add_argument(
        "--stride",
        type=int,
        default=5,
        help="Record a ball position every N physics frames of each shot.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=sorted(SCENARIOS),
        help="Position to inspect; repeatable.  Defaults to all of them.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    table = create_table()
    weights = load_policy_weights(args.policy) if args.policy else None
    player = AIPlayer(weights=weights, candidate_count=args.candidates, seed=0, table=table)

    wanted = args.scenario or list(SCENARIOS)
    scenarios = []
    for scenario_id in wanted:
        snapshot, name, description = SCENARIOS[scenario_id]()
        print(f"inspecting {scenario_id} ...", flush=True)
        scenarios.append(
            inspect_snapshot(
                player, snapshot, name, description, scenario_id, stride=args.stride
            )
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_budget": args.candidates,
        "table": {
            "left": table.left,
            "top": table.top,
            "right": table.right,
            "bottom": table.bottom,
            "ball_radius": BALL_RADIUS,
            "pockets": [
                {
                    "x": _round(pocket.pos.x, 1),
                    "y": _round(pocket.pos.y, 1),
                    "r": _round(pocket.visual_radius, 1),
                    "kind": pocket.kind,
                }
                for pocket in table.pockets
            ],
        },
        "weights": {
            field.name: getattr(player.weights, field.name)
            for field in fields(player.weights)
        },
        "scenarios": scenarios,
    }

    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
    total = sum(len(s["candidates"]) for s in scenarios)
    print(f"wrote {args.out}: {len(scenarios)} positions, {total} candidates")


if __name__ == "__main__":
    main()
