"""Multi-seed benchmark runner for the baseline and green-wave algorithms.

Usage:
    uv run python -u -m sumotraci.scripts.eval_multi_seed \
        --algorithm baseline greenwave_legacy greenwave
    GW_EV_PREEMPTION=false uv run python -u -m sumotraci.scripts.eval_multi_seed \
        --algorithm greenwave --label greenwave_rigoroso
    uv run python -u -m sumotraci.scripts.eval_multi_seed \
        --algorithm greenwave --seeds 428956419

Runs each algorithm headless over the 10 evaluation `Settings.SEEDS` (or the
--seeds given), one run after the other, then merges the per-seed
tripinfo/lanedata CSVs into one file per label under data/, with a LABEL column
so variants of the same algorithm stay apart. The `greenwave` composition comes
from the GW_* settings (.env or environment variables), as in a single run.
See docs/BENCHMARK.md.

Every run rewrites data/road.net.xml, data/route.rou.xml and
data/config.sumocfg, so never start two benchmarks in the same directory at the
same time.
"""

import argparse
import os
import sys
import time

import pandas as pd

from ..core.config import Settings
from ..core.simulation import SimulationEngine

_ALGORITHMS = ("baseline", "greenwave_legacy", "greenwave")
_KINDS = ("tripinfo", "lanedata")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run algorithms over the evaluation seeds and merge the results."
    )
    parser.add_argument("--algorithm", nargs="+", required=True, choices=_ALGORITHMS)
    parser.add_argument(
        "--label",
        help="Name for the output files instead of the algorithm (one --algorithm "
        "only); use it to keep greenwave variants apart.",
    )
    parser.add_argument(
        "--seeds", nargs="+", type=int, help="Seeds to run (default: Settings.SEEDS)."
    )
    args = parser.parse_args()
    if args.label and len(args.algorithm) > 1:
        parser.error("--label takes exactly one --algorithm")
    return args


def _csv(kind: str, label: str, seed: int) -> str:
    return f"data/{kind}_{label}_{seed}.csv"


def _run(algorithm: str, label: str, seed: int) -> tuple[int, int] | None:
    """Run one simulation; return (saveds, unsaveds), or None if it wrote no CSVs."""
    # A CSV left by an earlier benchmark must not pass for this run's output.
    for kind in _KINDS:
        if os.path.exists(_csv(kind, label, seed)):
            os.remove(_csv(kind, label, seed))

    settings = Settings()
    settings.ALGORITHM = algorithm
    settings.SEED = seed
    settings.HIGHLIGHT_ALLOCATIONS = False  # visual only; headless runs skip it
    engine = SimulationEngine(
        settings=settings,
        nogui=True,
        tripinfo_filepath=f"tripinfo_{label}_{seed}.xml",
        lanedata_filepath=f"lanedata_{label}_{seed}.xml",
    )
    engine.run()

    if not all(os.path.exists(_csv(kind, label, seed)) for kind in _KINDS):
        return None
    saveds = engine.emergency_manager.count_saveds
    return saveds, engine.accident_manager.count_accidents - saveds


def _merge(kind: str, label: str, seeds: list[int]) -> str:
    frames = [pd.read_csv(_csv(kind, label, seed)).assign(LABEL=label) for seed in seeds]
    merged = f"data/{kind}_{label}_merged.csv"
    pd.concat(frames).to_csv(merged, index=False)
    return merged


def main() -> None:
    args = _parse_args()
    seeds = args.seeds or Settings().SEEDS
    failed: list[str] = []

    for algorithm in args.algorithm:
        label = args.label or algorithm
        done: list[int] = []
        for seed in seeds:
            start = time.monotonic()
            result = _run(algorithm, label, seed)
            elapsed = time.monotonic() - start
            if result is None:
                failed.append(f"{label}/{seed}")
                print(f"[benchmark] {label} seed={seed} FAILED ({elapsed:.0f} s)")
                continue
            done.append(seed)
            print(
                f"[benchmark] {label} seed={seed} saveds={result[0]} "
                f"unsaveds={result[1]} ({elapsed:.0f} s)"
            )
        if done:
            for kind in _KINDS:
                print(f"[benchmark] {label}: {_merge(kind, label, done)}")

    if failed:
        sys.exit(f"[benchmark] failed runs: {', '.join(failed)}")


if __name__ == "__main__":
    main()
