"""Evaluate an 8-ball AI policy by its match record against a fixed opponent."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor

from ai.policy import PolicyWeights, load_policy_weights
from ai.train import evaluate_weights


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", default="ai_policy.json", help="Policy JSON to evaluate.")
    parser.add_argument(
        "--opponent",
        default=None,
        help="Policy JSON to play against.  Defaults to the built-in baseline.",
    )
    parser.add_argument("--games", type=int, default=6)
    parser.add_argument("--candidates", type=int, default=16)
    parser.add_argument("--max-shots", type=int, default=80)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Processes playing matches in parallel.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    weights = load_policy_weights(args.policy)
    opponent = (
        PolicyWeights() if args.opponent is None else load_policy_weights(args.opponent)
    )

    executor = (
        ProcessPoolExecutor(max_workers=args.workers) if args.workers > 1 else None
    )
    try:
        metrics = evaluate_weights(
            weights=weights,
            episodes=args.games,
            candidate_count=args.candidates,
            max_shots=args.max_shots,
            seed=args.seed,
            opponent=opponent,
            executor=executor,
        )
    finally:
        if executor is not None:
            executor.shutdown()
    print(
        f"win={metrics['win_rate']:.0%} "
        f"({metrics['wins']}-{metrics['losses']}, "
        f"{metrics['unfinished']} unfinished) "
        f"balls/shot={metrics['balls_per_shot']:.2f} "
        f"legal={metrics['legal_rate']:.0%} "
        f"avg_shots={metrics['avg_shots']:.1f}"
    )


if __name__ == "__main__":
    main()
