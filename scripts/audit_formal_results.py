#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPERIMENTS = {
    "expat_resume": (
        ROOT / "results" / "expat_resume" / "formal_300s"
    ),
    "libyaml_flow": (
        ROOT / "results" / "libyaml_flow" / "formal_300s"
    ),
}

MODES = (
    "afl",
    "aflsmart-mixed",
    "aflsmart-nonstack",
)

EXPECTED_REPS = range(1, 6)
EXPECTED_DURATION = 300
EXPECTED_SEEDS = 16

failed = False
runs_checked = 0


def error(message: str) -> None:
    global failed
    failed = True
    print(f"ERROR   {message}")


def ok(message: str) -> None:
    print(f"OK      {message}")


def require_file(path: Path, description: str) -> bool:
    if path.is_file():
        ok(description)
        return True

    error(f"{description} missing: {path}")
    return False


def require_dir(path: Path, description: str) -> bool:
    if path.is_dir():
        ok(description)
        return True

    error(f"{description} missing: {path}")
    return False


def count_regular_files(path: Path) -> int:
    if not path.is_dir():
        return 0

    return sum(
        1
        for item in path.iterdir()
        if item.is_file()
    )


def load_jsonl(path: Path) -> list[dict]:
    records = []

    with path.open(
        encoding="utf-8"
    ) as handle:

        for line_number, line in enumerate(
            handle,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                records.append(
                    json.loads(line)
                )
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"{path}:{line_number}: "
                    f"invalid JSON: {exc}"
                ) from exc

    return records


def parse_afl_stats(path: Path) -> dict[str, str]:
    stats = {}

    for line in path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1,
        )

        stats[key.strip()] = value.strip()

    return stats


def parse_stability(stats: dict[str, str]):
    raw = stats.get("stability")

    if raw is None:
        return None

    match = re.search(
        r"([0-9]+(?:\.[0-9]+)?)",
        raw,
    )

    if not match:
        return None

    return float(
        match.group(1)
    )


for subject, root in EXPERIMENTS.items():

    print()
    print("=" * 78)
    print(subject)
    print("=" * 78)

    if not require_dir(
        root,
        "formal experiment root",
    ):
        continue

    for rep in EXPECTED_REPS:

        repdir = root / f"rep{rep:02d}"

        if not require_dir(
            repdir,
            f"rep{rep:02d} directory",
        ):
            continue

        for mode in MODES:

            runs_checked += 1

            print()
            print(
                f"{subject} "
                f"rep{rep:02d} "
                f"{mode}"
            )

            rundir = repdir / mode

            metadata_path = (
                rundir / "metadata.json"
            )

            coverage_path = (
                rundir
                / "generated_eval"
                / "coverage"
                / "coverage.jsonl"
            )

            pass_dir = (
                rundir
                / "generated_eval"
                / "pass"
            )

            fail_dir = (
                rundir
                / "generated_eval"
                / "fail"
            )

            queue_dir = (
                rundir
                / "raw"
                / "queue"
            )

            stats_path = (
                rundir
                / "raw"
                / "fuzzer_stats"
            )

            required_ok = True

            required_ok &= require_file(
                metadata_path,
                "metadata.json",
            )

            required_ok &= require_file(
                coverage_path,
                "coverage.jsonl",
            )

            required_ok &= require_dir(
                pass_dir,
                "generated PASS directory",
            )

            required_ok &= require_dir(
                fail_dir,
                "generated FAIL directory",
            )

            required_ok &= require_dir(
                queue_dir,
                "AFL queue directory",
            )

            required_ok &= require_file(
                stats_path,
                "fuzzer_stats",
            )

            if not required_ok:
                continue

            metadata = json.loads(
                metadata_path.read_text(
                    encoding="utf-8"
                )
            )

            classification = metadata.get(
                "classification",
                {},
            )

            duration = metadata.get(
                "duration_seconds"
            )

            if duration == EXPECTED_DURATION:
                ok(
                    f"duration={duration}s"
                )
            else:
                error(
                    f"duration expected "
                    f"{EXPECTED_DURATION}, got {duration}"
                )

            expected_mode = metadata.get(
                "mode"
            )

            if expected_mode == mode:
                ok(f"mode={mode}")
            else:
                error(
                    f"metadata mode={expected_mode!r}, "
                    f"directory mode={mode!r}"
                )

            metadata_rep = metadata.get(
                "rep",
                metadata.get(
                    "repetition"
                ),
            )

            if metadata_rep == rep:
                ok(f"repetition={rep}")
            elif metadata_rep is not None:
                error(
                    f"metadata repetition={metadata_rep}, "
                    f"directory repetition={rep}"
                )

            pass_count = int(
                classification.get(
                    "PASS",
                    -1,
                )
            )

            fail_count = int(
                classification.get(
                    "FAIL",
                    -1,
                )
            )

            unresolved_count = int(
                classification.get(
                    "UNRESOLVED",
                    -1,
                )
            )

            usable = int(
                classification.get(
                    "usable",
                    -1,
                )
            )

            unique_evaluated = int(
                classification.get(
                    "unique_generated_evaluated",
                    -1,
                )
            )

            raw_queue_entries = int(
                classification.get(
                    "raw_queue_entries",
                    -1,
                )
            )

            seed_entries = int(
                classification.get(
                    "seed_entries",
                    -1,
                )
            )

            generated_queue_entries = int(
                classification.get(
                    "generated_queue_entries",
                    -1,
                )
            )

            duplicate_generated = int(
                classification.get(
                    "duplicate_generated",
                    0,
                )
            )

            duplicate_baseline = int(
                classification.get(
                    "duplicate_baseline",
                    0,
                )
            )

            #
            # Classification arithmetic.
            #
            if pass_count + fail_count == usable:
                ok(
                    "PASS + FAIL = usable "
                    f"({usable})"
                )
            else:
                error(
                    "PASS + FAIL != usable: "
                    f"{pass_count}+{fail_count}!={usable}"
                )

            if (
                pass_count
                + fail_count
                + unresolved_count
                == unique_evaluated
            ):
                ok(
                    "PASS + FAIL + UNRESOLVED = "
                    f"unique evaluated ({unique_evaluated})"
                )
            else:
                error(
                    "classification total mismatch: "
                    f"{pass_count}+{fail_count}+"
                    f"{unresolved_count} != "
                    f"{unique_evaluated}"
                )

            if seed_entries == EXPECTED_SEEDS:
                ok(
                    f"seed entries={EXPECTED_SEEDS}"
                )
            else:
                error(
                    f"expected {EXPECTED_SEEDS} seeds, "
                    f"got {seed_entries}"
                )

            if (
                unique_evaluated
                + duplicate_generated
                + duplicate_baseline
                == generated_queue_entries
            ):
                ok(
                    "generated queue accounting "
                    "is consistent"
                )
            else:
                error(
                    "generated queue accounting mismatch"
                )

            if (
                seed_entries
                + generated_queue_entries
                == raw_queue_entries
            ):
                ok(
                    "raw queue accounting "
                    "is consistent"
                )
            else:
                error(
                    "raw queue accounting mismatch"
                )

            #
            # Actual generated PASS/FAIL files.
            #
            actual_pass_files = (
                count_regular_files(
                    pass_dir
                )
            )

            actual_fail_files = (
                count_regular_files(
                    fail_dir
                )
            )

            if actual_pass_files == pass_count:
                ok(
                    f"PASS files={actual_pass_files}"
                )
            else:
                error(
                    f"PASS files={actual_pass_files}, "
                    f"metadata PASS={pass_count}"
                )

            if actual_fail_files == fail_count:
                ok(
                    f"FAIL files={actual_fail_files}"
                )
            else:
                error(
                    f"FAIL files={actual_fail_files}, "
                    f"metadata FAIL={fail_count}"
                )

            #
            # Coverage records.
            #
            coverage_records = (
                load_jsonl(
                    coverage_path
                )
            )

            outcome_counts = Counter(
                record.get(
                    "classification"
                )
                for record
                in coverage_records
            )

            if len(coverage_records) == usable:
                ok(
                    "coverage records = usable tests "
                    f"({usable})"
                )
            else:
                error(
                    f"coverage records="
                    f"{len(coverage_records)}, "
                    f"usable={usable}"
                )

            if (
                outcome_counts["PASS"]
                == pass_count
            ):
                ok(
                    "coverage PASS count matches "
                    f"metadata ({pass_count})"
                )
            else:
                error(
                    "coverage PASS mismatch: "
                    f"{outcome_counts['PASS']} "
                    f"vs {pass_count}"
                )

            if (
                outcome_counts["FAIL"]
                == fail_count
            ):
                ok(
                    "coverage FAIL count matches "
                    f"metadata ({fail_count})"
                )
            else:
                error(
                    "coverage FAIL mismatch: "
                    f"{outcome_counts['FAIL']} "
                    f"vs {fail_count}"
                )

            unexpected_outcomes = (
                set(outcome_counts)
                - {"PASS", "FAIL"}
            )

            if unexpected_outcomes:
                error(
                    "unexpected coverage outcomes: "
                    f"{sorted(unexpected_outcomes)}"
                )
            else:
                ok(
                    "coverage contains only PASS/FAIL"
                )

            #
            # Actual AFL queue.
            #
            actual_queue = (
                count_regular_files(
                    queue_dir
                )
            )

            if actual_queue == raw_queue_entries:
                ok(
                    f"raw queue files={actual_queue}"
                )
            else:
                error(
                    f"raw queue files={actual_queue}, "
                    f"metadata={raw_queue_entries}"
                )

            #
            # AFL statistics and stability.
            #
            stats = parse_afl_stats(
                stats_path
            )

            stability = parse_stability(
                stats
            )

            if stability is None:
                error(
                    "could not parse AFL stability"
                )
            elif stability == 100.0:
                ok(
                    "AFL stability=100.00%"
                )
            else:
                error(
                    f"AFL stability={stability}%"
                )

            try:
                execs_done = int(
                    stats.get(
                        "execs_done",
                        "0",
                    )
                )
            except ValueError:
                execs_done = 0

            if execs_done > 0:
                ok(
                    f"execs_done={execs_done}"
                )
            else:
                error(
                    "execs_done missing or zero"
                )

            print(
                "SUMMARY "
                f"PASS={pass_count} "
                f"FAIL={fail_count} "
                f"UNRESOLVED={unresolved_count} "
                f"usable={usable}"
            )


print()
print("=" * 78)
print(f"runs checked: {runs_checked}")

expected_runs = (
    len(EXPERIMENTS)
    * len(tuple(EXPECTED_REPS))
    * len(MODES)
)

if runs_checked != expected_runs:
    error(
        f"expected {expected_runs} runs, "
        f"checked {runs_checked}"
    )

if failed:
    print("FORMAL RESULT AUDIT: FAIL")
    sys.exit(1)

print("FORMAL RESULT AUDIT: PASS")
