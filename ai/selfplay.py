"""Play the AI against itself and write down what it saw and how it ended.

The point is a dataset for learning what a position is worth.  Nobody has to
label anything: the game already knows who won, so every position a player
faced carries its own answer once the game is over.

One row per shot, recorded *before* the shot is played:

    the position itself   -- every ball still on the table, whose turn it is,
                             which group they are on, whether they have the
                             cue ball in hand
    pv                    -- what today's position_value() thinks the position
                             is worth, so a learned model can be held against
                             the heuristic it would replace
    won                   -- did the player about to shoot go on to win

Positions are stored raw rather than as features, because the games are the
expensive part and features will be reworked several times.

The file is JSON lines.  Every run writes one header line carrying a "meta"
key -- the policy, candidate count and aiming error it played under -- so an
appended file holds several of them.  Anything reading the dataset should skip
lines with that key and keep the rest.

    python -m ai.selfplay --games 200 --workers 12 --out selfplay.jsonl
    python -m ai.selfplay --games 5000 --workers 12 --max-hours 3 --append
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from ai.policy import AIPlayer, PolicyWeights
from ai.simulation import GameSnapshot
from ai.train import DEFAULT_AIM_NOISE


def play_recorded_game(
    weights: PolicyWeights,
    seed: int,
    candidate_count: int,
    max_shots: int,
    aim_noise: float,
) -> dict:
    """Play one self-play game and return its rows plus a note on how it went."""
    seats = [
        AIPlayer(weights=weights, candidate_count=candidate_count, seed=seed),
        AIPlayer(weights=weights, candidate_count=candidate_count, seed=seed + 1),
    ]
    snapshot = GameSnapshot.new_game(seed=seed)

    # The same aiming error training uses.  Without it both sides pot
    # everything and every position looks equally won.
    hand = random.Random(seed * 7919 + 13)

    rows: list[dict] = []
    pots = 0
    fouls = 0

    for ply in range(max_shots):
        player = seats[snapshot.current_idx]

        rows.append({
            "g": seed,
            "t": ply,
            "p": snapshot.current_idx,
            "grp": snapshot.current_player.group,
            "bih": int(snapshot.needs_ball_in_hand()),
            "brk": int(snapshot.is_break),
            "b": [
                [ball.number, round(ball.x, 1), round(ball.y, 1)]
                for ball in snapshot.balls
                if not ball.pocketed
            ],
            "pv": round(player.position_value(snapshot), 5),
        })

        decision = player.choose_decision(snapshot)
        result = decision.result
        if aim_noise > 0.0:
            played = replace(
                decision.shot, angle=decision.shot.angle + hand.gauss(0.0, aim_noise)
            )
            result = player.simulator.simulate(snapshot, played)

        pots += sum(1 for n in result.pocketed_numbers if n not in (0, 8))
        if result.shot_result.is_foul:
            fouls += 1

        snapshot = result.next_state
        if snapshot.game_over:
            break

    finished = snapshot.game_over
    winner_idx = -1
    if finished:
        for idx, player_state in enumerate(snapshot.players):
            if player_state.name == snapshot.winner_name:
                winner_idx = idx

    shots = len(rows)
    for row in rows:
        row["fin"] = int(finished)
        row["left"] = shots - row["t"]
        row["won"] = None if not finished else int(row["p"] == winner_idx)

    return {
        "rows": rows,
        "shots": shots,
        "finished": finished,
        "pots": pots,
        "fouls": fouls,
        "reason": snapshot.loss_reason,
    }


def _game_job(job: tuple) -> dict:
    weights, seed, candidate_count, max_shots, aim_noise = job
    return play_recorded_game(
        weights=weights,
        seed=seed,
        candidate_count=candidate_count,
        max_shots=max_shots,
        aim_noise=aim_noise,
    )


def _load_weights(path: Optional[str]) -> tuple[PolicyWeights, str]:
    if not path:
        return PolicyWeights(), "built-in defaults"
    policy_path = Path(path)
    if not policy_path.exists():
        return PolicyWeights(), "built-in defaults (%s not found)" % path
    with policy_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return PolicyWeights.from_dict(data.get("weights", data)), str(policy_path)


def _fmt_hms(seconds: float) -> str:
    seconds = int(max(0, seconds))
    return "%d:%02d:%02d" % (seconds // 3600, (seconds % 3600) // 60, seconds % 60)


def collect(args: argparse.Namespace) -> dict:
    weights, source = _load_weights(args.policy)
    out_path = Path(args.out)
    mode = "a" if args.append and out_path.exists() else "w"

    jobs = [
        (
            weights,
            args.seed_start + i,
            args.candidates,
            args.max_shots,
            args.aim_noise,
        )
        for i in range(args.games)
    ]

    meta = {
        "meta": {
            "written_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "policy": source,
            "weights": {k: v for k, v in vars(weights).items()},
            "candidates": args.candidates,
            "max_shots": args.max_shots,
            "aim_noise": args.aim_noise,
            "seed_start": args.seed_start,
            "games_requested": args.games,
        }
    }

    started = time.time()
    deadline = started + args.max_hours * 3600 if args.max_hours > 0 else None

    games = rows = pots = fouls = finished = 0
    shots_total = 0
    wins_to_breaker = 0

    handle = out_path.open(mode, encoding="utf-8", newline="\n")
    try:
        handle.write(json.dumps(meta) + "\n")
        handle.flush()

        if args.workers > 1:
            import multiprocessing as mp

            pool = mp.Pool(processes=args.workers)
            stream = pool.imap_unordered(_game_job, jobs, chunksize=1)
        else:
            pool = None
            stream = (_game_job(job) for job in jobs)

        try:
            for game in stream:
                games += 1
                shots_total += game["shots"]
                pots += game["pots"]
                fouls += game["fouls"]
                finished += int(game["finished"])
                for row in game["rows"]:
                    if row["won"] is not None:
                        rows += 1
                        if row["t"] == 0 and row["won"]:
                            wins_to_breaker += 1
                    handle.write(json.dumps(row, separators=(",", ":")) + "\n")

                if games % args.report_every == 0:
                    handle.flush()
                    elapsed = time.time() - started
                    rate = games / max(1e-9, elapsed)
                    print(
                        "%6d games | %8d labelled rows | %.2f games/s | "
                        "%.1f shots/game | %.0f%% finished | breaker wins %.0f%% | "
                        "elapsed %s"
                        % (
                            games,
                            rows,
                            rate,
                            shots_total / max(1, games),
                            100.0 * finished / max(1, games),
                            100.0 * wins_to_breaker / max(1, finished),
                            _fmt_hms(elapsed),
                        ),
                        flush=True,
                    )

                if deadline and time.time() >= deadline:
                    print("stopping: --max-hours reached", flush=True)
                    break
        finally:
            if pool is not None:
                pool.terminate()
                pool.join()
    finally:
        handle.flush()
        handle.close()

    elapsed = time.time() - started
    summary = {
        "games": games,
        "labelled_rows": rows,
        "shots_per_game": shots_total / max(1, games),
        "finished_share": finished / max(1, games),
        "pots_per_shot": pots / max(1, shots_total),
        "fouls_per_shot": fouls / max(1, shots_total),
        "breaker_win_share": wins_to_breaker / max(1, finished),
        "elapsed_s": elapsed,
        "games_per_hour": games / max(1e-9, elapsed / 3600),
        "out": str(out_path),
    }
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=100)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--candidates", type=int, default=48)
    parser.add_argument("--max-shots", type=int, default=80)
    parser.add_argument("--aim-noise", type=float, default=DEFAULT_AIM_NOISE)
    parser.add_argument("--policy", default="ai_policy.json")
    parser.add_argument("--out", default="selfplay.jsonl")
    parser.add_argument("--seed-start", type=int, default=100000)
    parser.add_argument(
        "--append",
        action="store_true",
        help="Add to an existing file instead of overwriting it.",
    )
    parser.add_argument(
        "--max-hours",
        type=float,
        default=0.0,
        help="Stop cleanly after this long, whatever is left of --games.",
    )
    parser.add_argument("--report-every", type=int, default=20)
    return parser


def main() -> None:
    collect(build_parser().parse_args())


if __name__ == "__main__":
    main()
