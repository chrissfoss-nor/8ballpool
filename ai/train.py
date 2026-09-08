"""Train the 8-ball AI policy by playing candidate weights against an opponent.

The objective here is a *match result*, not the policy's own opinion of its
shots.  Scoring a candidate with the same weights that are being tuned makes
the yardstick move with the thing it measures: a mutation that simply inflates
every reward scores higher without playing any better.  Beating a fixed
opponent cannot be gamed that way.

A generation plays every mutation *and the champion* over the same games, on
the same seeds, and keeps whoever came out ahead.  Measuring the champion
again each generation costs one extra evaluation and buys the only comparison
worth making: a mutation that wins because it drew easier tables has not
learned anything, and over a night of small accepted steps that noise is what
a hill climber accumulates instead of skill.

A challenger that comes out on top is then replayed against the champion on
games neither has seen, and only takes the crown if it wins that too.  Picking
the best of several noisy samples flatters whichever one the noise favoured;
the confirmation round is what makes an accepted step mean something.

Matches are independent, so a generation is handed to a process pool and the
wall clock divides by the number of cores.  That is what makes an overnight
run worth starting: the number of games played is the whole budget.
"""

from __future__ import annotations

import os

# Every worker process would otherwise start a BLAS thread pool sized for the
# whole machine, and fifteen of those at once run the box out of threads before
# the first game is played.  The work here is one game per core, single
# threaded, so each process is told to keep to itself.  This has to happen
# before anything pulls in numpy, which is why it sits above the imports.
for _thread_var in (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ.setdefault(_thread_var, "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, replace
from datetime import datetime, timezone
import random
import time

from ai.policy import AIPlayer, PolicyWeights, load_policy_weights, save_policy_weights
from ai.simulation import GameSnapshot


#: Aiming error applied to every shot in a training match, in radians.
#:
#: Without it a match says nothing.  An AI that plays its chosen shot perfectly
#: breaks and runs the entire rack, so the opponent never reaches the table and
#: every policy wins exactly the games it breaks in -- a win rate of 50% for
#: everything, whatever it knows about pool.  Making both sides miss the way a
#: player misses is what turns a match back into a measurement of judgement.
#:
#: Measured over six games of the current policy against itself:
#:
#:     noise     shots/game   breaker won   one side never shot
#:     0.0006       7.5          6 of 6          3 of 6
#:     0.0025      16.7          3 of 6          0 of 6
#:     0.0060      17.0          3 of 6          0 of 6
#:
#: 0.0006 is the 'hard' preset and it is not enough to stop a run-out. 0.0025 is
#: 'medium', and it is the point where both players get to the table in every
#: game -- so that is what a policy is judged on, whatever difficulty it is
#: later played at.
DEFAULT_AIM_NOISE = 0.0025


#: A promotion decided on fewer games than this is noise, not progress.
MIN_GAMES_FOR_PROMOTION = 6


def play_match(
    challenger: PolicyWeights,
    opponent: PolicyWeights,
    seed: int,
    candidate_count: int,
    max_shots: int,
    challenger_breaks: bool,
    aim_noise: float = DEFAULT_AIM_NOISE,
) -> dict:
    """Play one full game between two weight sets and report how it went."""
    challenger_ai = AIPlayer(
        weights=challenger, candidate_count=candidate_count, seed=seed
    )
    opponent_ai = AIPlayer(
        weights=opponent, candidate_count=candidate_count, seed=seed
    )

    snapshot = GameSnapshot.new_game(seed=seed)
    challenger_idx = 0 if challenger_breaks else 1
    seats = [None, None]
    seats[challenger_idx] = challenger_ai
    seats[1 - challenger_idx] = opponent_ai

    shots = 0
    challenger_shots = 0
    challenger_legal = 0
    challenger_pots = 0

    # Both sides miss by the same amount, from one stream tied to the seed, so
    # a match stays reproducible.
    hand = random.Random(seed * 7919 + 13)

    for _ in range(max_shots):
        acting_idx = snapshot.current_idx
        player = seats[acting_idx]
        decision = player.choose_decision(snapshot)
        result = decision.result

        if aim_noise > 0.0:
            # The search stays exact -- the policy knows the shot it wants and
            # simply does not execute it perfectly, which is what separates a
            # good choice from a lucky one.
            played = replace(
                decision.shot, angle=decision.shot.angle + hand.gauss(0.0, aim_noise)
            )
            result = player.simulator.simulate(snapshot, played)

        shots += 1

        if acting_idx == challenger_idx:
            challenger_shots += 1
            if result.legal:
                challenger_legal += 1
                challenger_pots += sum(
                    1 for n in result.pocketed_numbers if n not in (0, 8)
                )

        snapshot = result.next_state
        if snapshot.game_over:
            break

    challenger_name = snapshot.players[challenger_idx].name
    if not snapshot.game_over:
        outcome = "unfinished"
    elif snapshot.winner_name == challenger_name:
        outcome = "win"
    else:
        outcome = "loss"

    return {
        "outcome": outcome,
        "shots": shots,
        "legal_rate": challenger_legal / max(1, challenger_shots),
        "balls_per_shot": challenger_pots / max(1, challenger_shots),
    }


def _play_match_job(job: tuple) -> dict:
    """Run one match from a plain tuple, so a process pool can carry it."""
    challenger, opponent, seed, candidate_count, max_shots, breaks, aim_noise = job
    return play_match(
        challenger=challenger,
        opponent=opponent,
        seed=seed,
        candidate_count=candidate_count,
        max_shots=max_shots,
        challenger_breaks=breaks,
        aim_noise=aim_noise,
    )


def evaluate_many(
    contenders: list[PolicyWeights],
    opponent: PolicyWeights,
    episodes: int,
    candidate_count: int,
    max_shots: int,
    seed: int,
    executor: ProcessPoolExecutor | None = None,
    aim_noise: float = DEFAULT_AIM_NOISE,
) -> list[dict]:
    """Play every contender over the same *episodes* games and report each.

    Every contender meets the same seeds and breaks in the same games, so the
    records can be compared directly instead of through the luck of the draw.
    """
    jobs = [
        (
            contender,
            opponent,
            seed + episode,
            candidate_count,
            max_shots,
            episode % 2 == 0,
            aim_noise,
        )
        for contender in contenders
        for episode in range(episodes)
    ]

    if executor is None:
        played = [_play_match_job(job) for job in jobs]
    else:
        played = list(executor.map(_play_match_job, jobs, chunksize=1))

    return [
        _summarise(played[index * episodes : (index + 1) * episodes], episodes)
        for index in range(len(contenders))
    ]


def evaluate_weights(
    weights: PolicyWeights,
    episodes: int,
    candidate_count: int,
    max_shots: int,
    seed: int,
    opponent: PolicyWeights | None = None,
    executor: ProcessPoolExecutor | None = None,
    aim_noise: float = DEFAULT_AIM_NOISE,
) -> dict:
    """Play *episodes* games against *opponent* and report the match record.

    Sides alternate so the advantage of breaking cancels out.
    """
    if opponent is None:
        opponent = PolicyWeights()

    return evaluate_many(
        [weights],
        opponent=opponent,
        episodes=episodes,
        candidate_count=candidate_count,
        max_shots=max_shots,
        seed=seed,
        executor=executor,
        aim_noise=aim_noise,
    )[0]


def _summarise(results: list[dict], episodes: int) -> dict:
    """Turn a set of played matches into the record used to rank them."""
    wins = sum(1 for r in results if r["outcome"] == "win")
    losses = sum(1 for r in results if r["outcome"] == "loss")
    decided = wins + losses

    return {
        "win_rate": wins / max(1, decided),
        "wins": wins,
        "losses": losses,
        "unfinished": sum(1 for r in results if r["outcome"] == "unfinished"),
        "legal_rate": sum(r["legal_rate"] for r in results) / max(1, len(results)),
        "balls_per_shot": sum(r["balls_per_shot"] for r in results) / max(1, len(results)),
        "avg_shots": sum(r["shots"] for r in results) / max(1, len(results)),
        "episodes": episodes,
    }


def fitness(metrics: dict) -> tuple:
    """Rank by match record, then by how briskly the games were won."""
    return (
        round(metrics["win_rate"], 4),
        round(metrics["balls_per_shot"], 4),
        -metrics["avg_shots"],
    )


def _metadata(args: argparse.Namespace, generations_run: int, metrics: dict) -> dict:
    return {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "generations": generations_run,
        "population": args.population,
        "episodes_per_generation": args.episodes,
        "candidate_count": args.candidates,
        "max_shots": args.max_shots,
        "seed": args.seed,
        "metrics": metrics,
    }


def train(args: argparse.Namespace) -> tuple[PolicyWeights, dict]:
    rng = random.Random(args.seed)
    best = load_policy_weights(args.input)

    # The yardstick.  Held fixed so a win rate means the same thing in the
    # last generation as in the first.
    opponent = PolicyWeights() if args.opponent is None else load_policy_weights(args.opponent)

    deadline = None if not args.max_hours else time.perf_counter() + args.max_hours * 3600.0
    executor = ProcessPoolExecutor(max_workers=args.workers) if args.workers > 1 else None

    games_per_generation = (args.population + 1) * args.episodes
    print(
        f"population={args.population} episodes={args.episodes} "
        f"candidates={args.candidates} workers={args.workers} "
        f"({games_per_generation} games per generation)"
    )

    best_metrics: dict = {}
    generations_run = 0
    started = time.perf_counter()

    try:
        for generation in range(1, args.generations + 1):
            # The champion is re-played alongside its own mutations, on the
            # same games, so the comparison is between the policies and not
            # between the tables they happened to draw.
            contenders = [best] + [
                best.mutated(rng, scale=args.mutation_scale)
                for _ in range(args.population)
            ]
            records = evaluate_many(
                contenders,
                opponent=opponent,
                episodes=args.episodes,
                candidate_count=args.candidates,
                max_shots=args.max_shots,
                seed=args.seed + generation * 1000,
                executor=executor,
                aim_noise=args.aim_noise,
            )

            winner = max(range(len(contenders)), key=lambda i: fitness(records[i]))
            best_metrics = records[0]
            generations_run = generation
            improved = False

            if winner != 0:
                # Confirm on games neither has seen before.  The best of six
                # noisy samples is flattered by the noise it was picked on, so
                # a champion replaced on that alone drifts sideways all night
                # instead of climbing.  Re-playing just the two of them costs a
                # fifth of a generation and is the difference between selection
                # and a random walk.
                confirm = evaluate_many(
                    [best, contenders[winner]],
                    opponent=opponent,
                    episodes=args.episodes,
                    candidate_count=args.candidates,
                    max_shots=args.max_shots,
                    seed=args.seed + generation * 1000 + 500_000,
                    executor=executor,
                    aim_noise=args.aim_noise,
                )
                if fitness(confirm[1]) > fitness(confirm[0]):
                    best = contenders[winner]
                    best_metrics = confirm[1]
                    improved = True
                    save_policy_weights(
                        args.output, best, _metadata(args, generation, best_metrics)
                    )
                else:
                    best_metrics = confirm[0]

            elapsed = (time.perf_counter() - started) / 60.0
            print(
                f"{generation:03d} {'kept' if improved else 'hold'} "
                f"win={best_metrics['win_rate']:.0%} "
                f"({best_metrics['wins']}-{best_metrics['losses']}) "
                f"balls/shot={best_metrics['balls_per_shot']:.2f} "
                f"legal={best_metrics['legal_rate']:.0%} "
                f"[{elapsed:.0f} min]",
                flush=True,
            )

            # Once the champion is clearly ahead, a fixed opponent stops telling
            # the two apart.  Promoting it keeps the comparison informative --
            # but a win rate over a handful of games is mostly noise, so a
            # promotion needs a real sample behind it.  The next generation
            # measures everyone against the new opponent, so nothing needs to
            # be re-played here.
            decided = best_metrics["wins"] + best_metrics["losses"]
            if (
                args.promote
                and decided >= MIN_GAMES_FOR_PROMOTION
                and best_metrics["win_rate"] >= args.promote
            ):
                opponent = best
                print("    opponent promoted to the current champion", flush=True)

            if deadline is not None and time.perf_counter() >= deadline:
                print(f"    stopping: {args.max_hours} h budget spent", flush=True)
                break
    except KeyboardInterrupt:
        print("interrupted; keeping the best policy found so far", flush=True)
    finally:
        if executor is not None:
            executor.shutdown()

    return best, _metadata(args, generations_run, best_metrics)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="ai_policy.json", help="Policy JSON to write.")
    parser.add_argument("--input", default=None, help="Optional existing policy JSON to continue.")
    parser.add_argument(
        "--opponent",
        default=None,
        help="Policy JSON to train against.  Defaults to the built-in baseline.",
    )
    parser.add_argument("--generations", type=int, default=8)
    parser.add_argument(
        "--population",
        type=int,
        default=1,
        help="Mutations tried per generation.  Each one costs --episodes games.",
    )
    parser.add_argument("--episodes", type=int, default=6, help="Games per evaluation.")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Processes playing matches in parallel.  Matches are independent, "
             "so this divides the wall clock almost exactly.",
    )
    parser.add_argument(
        "--max-hours",
        type=float,
        default=0.0,
        help="Stop after this many hours, whatever generation it is on.  0 runs "
             "all --generations.",
    )
    parser.add_argument("--candidates", type=int, default=16)
    parser.add_argument("--max-shots", type=int, default=80)
    parser.add_argument("--mutation-scale", type=float, default=0.12)
    parser.add_argument(
        "--aim-noise",
        type=float,
        default=DEFAULT_AIM_NOISE,
        help="Aiming error applied to every shot played, in radians.  0 makes "
             "both sides perfect, which makes the match record meaningless.",
    )
    parser.add_argument(
        "--promote",
        type=float,
        default=0.75,
        help="Promote the champion to opponent once it wins this share of games. 0 disables.",
    )
    parser.add_argument("--seed", type=int, default=1)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    weights, metadata = train(args)
    save_policy_weights(args.output, weights, metadata)
    print(f"saved {args.output}")
    print(asdict(weights))


if __name__ == "__main__":
    main()
