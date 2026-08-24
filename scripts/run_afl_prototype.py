from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
import shutil
from typing import Any

from afl_mutate import mutate
from oracle import Outcome, classify


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SEED = (
    PROJECT_ROOT
    / "reports"
    / "invoice_character_ddmin"
    / "minimal_failure.xml"
)

DEFAULT_RESULTS_ROOT = (
    PROJECT_ROOT
    / "results"
    / "afl_prototype_runs"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def append_json_line(
    path: Path,
    record: dict[str, Any],
) -> None:
    with path.open(
        "a",
        encoding="utf-8",
    ) as file:
        file.write(
            json.dumps(
                record,
                sort_keys=True,
            )
        )

        file.write("\n")


def make_run_directory(
    results_root: Path,
) -> Path:
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    run_directory = (
        results_root
        / timestamp
    )

    run_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    return run_directory


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate AFL-style mutations from a DDMIN seed "
            "and classify them using the existing "
            "differential oracle."
        )
    )

    parser.add_argument(
        "--seed",
        type=Path,
        default=DEFAULT_SEED,
        help=(
            "DDMIN failing seed. "
            f"Default: {DEFAULT_SEED}"
        ),
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=500,
        help=(
            "Number of mutation attempts. "
            "Default: 500."
        ),
    )

    parser.add_argument(
        "--random-seed",
        type=int,
        default=1337,
        help=(
            "PRNG seed for reproducibility. "
            "Default: 1337."
        ),
    )

    parser.add_argument(
        "--results-root",
        type=Path,
        default=DEFAULT_RESULTS_ROOT,
        help=(
            "Directory containing prototype runs. "
            f"Default: {DEFAULT_RESULTS_ROOT}"
        ),
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    if arguments.iterations <= 0:
        raise SystemExit(
            "--iterations must be greater than zero."
        )

    seed_path = arguments.seed.resolve()

    if not seed_path.is_file():
        raise SystemExit(
            f"Seed not found: {seed_path}"
        )

    # Validate the DDMIN output before doing any mutation.
    seed_outcome = classify(seed_path)

    if seed_outcome != "FAIL":
        raise SystemExit(
            "Seed must classify as FAIL before mutation; "
            f"got {seed_outcome}: {seed_path}"
        )

    run_directory = make_run_directory(
        arguments.results_root.resolve()
    )

    outcome_directories = {
        "PASS": run_directory / "passing",
        "FAIL": run_directory / "failing",
        "UNRESOLVED": run_directory / "unresolved",
    }

    for directory in outcome_directories.values():
        directory.mkdir(
            parents=True
        )

    # Keep an exact copy of the seed used for the run.
    seed_copy = (
        run_directory
        / "seed.xml"
    )

    shutil.copy2(
        seed_path,
        seed_copy,
    )

    candidate_path = (
        run_directory
        / "_candidate.xml"
    )

    cases_path = (
        run_directory
        / "cases.jsonl"
    )

    summary_path = (
        run_directory
        / "mutation_summary.json"
    )

    rng = random.Random(
        arguments.random_seed
    )

    seed_data = seed_path.read_bytes()

    seed_hash = sha256_bytes(
        seed_data
    )

    # Do not count the original DDMIN seed as a generated mutation.
    seen_hashes = {
        seed_hash
    }

    outcome_counts: Counter[str] = Counter()

    operator_counts: Counter[str] = Counter()

    outcome_by_operator: dict[
        str,
        Counter[str],
    ] = defaultdict(Counter)

    duplicates = 0

    for attempt in range(
        1,
        arguments.iterations + 1,
    ):
        mutation = mutate(
            seed_data,
            rng,
        )

        candidate_hash = sha256_bytes(
            mutation.data
        )

        operator_counts[
            mutation.operator
        ] += 1

        # Avoid repeatedly executing identical candidates.
        if candidate_hash in seen_hashes:
            duplicates += 1

            append_json_line(
                cases_path,
                {
                    "attempt": attempt,
                    "operator": mutation.operator,
                    "sha256": candidate_hash,
                    "duplicate": True,
                },
            )

            continue

        seen_hashes.add(
            candidate_hash
        )

        candidate_path.write_bytes(
            mutation.data
        )

        # Reuse the exact existing DDMIN/SBFL oracle.
        outcome: Outcome = classify(
            candidate_path
        )

        outcome_counts[
            outcome
        ] += 1

        outcome_by_operator[
            mutation.operator
        ][outcome] += 1

        filename = (
            f"{attempt:05d}_"
            f"{mutation.operator}_"
            f"{candidate_hash[:12]}.xml"
        )

        saved_path = (
            outcome_directories[outcome]
            / filename
        )

        saved_path.write_bytes(
            mutation.data
        )

        append_json_line(
            cases_path,
            {
                "attempt": attempt,
                "operator": mutation.operator,
                "sha256": candidate_hash,
                "duplicate": False,
                "outcome": outcome,
                "size_bytes": len(
                    mutation.data
                ),
                "saved_file": str(
                    saved_path.relative_to(
                        run_directory
                    )
                ),
            },
        )

    if candidate_path.exists():
        candidate_path.unlink()

    summary = {
        "prototype": (
            "AFL-style byte mutation; "
            "not AFL/AFLSmart"
        ),
        "seed_file": str(
            seed_path
        ),
        "seed_sha256": seed_hash,
        "seed_size_bytes": len(
            seed_data
        ),
        "seed_outcome": seed_outcome,
        "iterations_requested": (
            arguments.iterations
        ),
        "random_seed": (
            arguments.random_seed
        ),
        "unique_mutations": sum(
            outcome_counts.values()
        ),
        "duplicate_mutations": duplicates,
        "outcomes": {
            "PASS": outcome_counts[
                "PASS"
            ],
            "FAIL": outcome_counts[
                "FAIL"
            ],
            "UNRESOLVED": outcome_counts[
                "UNRESOLVED"
            ],
        },
        "operators": dict(
            sorted(
                operator_counts.items()
            )
        ),
        "outcomes_by_operator": {
            operator: {
                "PASS": counts[
                    "PASS"
                ],
                "FAIL": counts[
                    "FAIL"
                ],
                "UNRESOLVED": counts[
                    "UNRESOLVED"
                ],
            }
            for operator, counts
            in sorted(
                outcome_by_operator.items()
            )
        },
    }

    summary_path.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Run directory: {run_directory}"
    )

    print(
        f"Seed: {seed_path}"
    )

    print(
        "Mutation attempts: "
        f"{arguments.iterations}"
    )

    print(
        "Unique mutations: "
        f"{summary['unique_mutations']}"
    )

    print(
        f"Duplicates: {duplicates}"
    )

    print(
        f"PASS: {outcome_counts['PASS']}"
    )

    print(
        f"FAIL: {outcome_counts['FAIL']}"
    )

    print(
        "UNRESOLVED: "
        f"{outcome_counts['UNRESOLVED']}"
    )

    print(
        f"Summary: {summary_path}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())