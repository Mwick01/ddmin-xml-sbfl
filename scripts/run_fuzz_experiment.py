#!/usr/bin/env python3

from __future__ import annotations

import os
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from oracle import classify


PROJECT_ROOT = Path(__file__).resolve().parents[1]

IMAGE = "ddmin-aflsmart"

SEED_DIRECTORY = PROJECT_ROOT / "aflsmart" / "seeds"
PIT_FILE = PROJECT_ROOT / "aflsmart" / "invoice.xml"

TARGET = PROJECT_ROOT / "build" / "aflsmart" / "invoice_buggy"

RESULTS_ROOT = PROJECT_ROOT / "results" / "fuzz_experiments"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(65536)

            if not block:
                break

            digest.update(block)

    return digest.hexdigest()


def get_git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout.strip()


def build_afl_arguments(
    mode: str,
    output_directory: Path,
) -> list[str]:

    arguments = [
        "/aflsmart/afl-fuzz",
        "-m",
        "200",
        "-d",
        "-i",
        "aflsmart/seeds",
        "-o",
        str(output_directory.relative_to(PROJECT_ROOT)),
    ]

    if mode in {"aflsmart-nonstack", "aflsmart-mixed"}:
        arguments.extend(
            [
                "-w",
                "peach",
                "-g",
                "aflsmart/invoice.xml",
            ]
        )

    if mode == "aflsmart-mixed":
        arguments.append("-h")

    arguments.extend(
        [
            "--",
            "./build/aflsmart/invoice_buggy",
            "@@",
        ]
    )

    return arguments


def run_fuzzer(
    mode: str,
    duration: int,
    raw_directory: Path,
) -> list[str]:

    afl_arguments = build_afl_arguments(mode, raw_directory)

    inner_command = [
        "timeout",
        "-s",
        "INT",
        f"{duration}s",
        *afl_arguments,
    ]

    docker_command = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        "HOME=/tmp",
        "-e",
        "AFL_PATH=/aflsmart",
        "-e",
        "AFL_SKIP_CPUFREQ=1",
        "-e",
        "AFL_NO_AFFINITY=1",
        "-v",
        f"{PROJECT_ROOT}:/work",
        "-w",
        "/work",
        IMAGE,
        "bash",
        "-lc",
        (
            'export PATH="'
            "/aflsmart/peach-3.0.202-source/"
            "output/linux_x86_64_release/bin:"
            '/aflsmart:$PATH"; '
            + " ".join(inner_command)
        ),
    ]

    print()
    print("Starting fuzzing experiment")
    print("=" * 72)
    print(f"Mode     : {mode}")
    print(f"Duration : {duration} seconds")
    print(f"Output   : {raw_directory}")
    print()

    result = subprocess.run(
        docker_command,
        cwd=PROJECT_ROOT,
    )

    # timeout normally returns 124 when it terminates a command.
    if result.returncode not in {0, 124}:
        raise RuntimeError(
            f"Fuzzer exited unexpectedly: {result.returncode}"
        )

    return afl_arguments


def classify_queue(
    raw_directory: Path,
    experiment_directory: Path,
) -> dict:

    queue_directory = raw_directory / "queue"

    outcome_directories = {
        "PASS": experiment_directory / "pass",
        "FAIL": experiment_directory / "fail",
        "UNRESOLVED": experiment_directory / "unresolved",
    }

    for directory in outcome_directories.values():
        directory.mkdir(parents=True, exist_ok=True)

    tests = sorted(
        path
        for path in queue_directory.iterdir()
        if path.is_file() and path.name.startswith("id:")
    )

    counts = Counter()

    seen_hashes: set[str] = set()

    records = []

    for test in tests:
        digest = sha256_file(test)

        duplicate = digest in seen_hashes
        seen_hashes.add(digest)

        outcome = classify(test)

        counts[outcome] += 1

        destination = (
            outcome_directories[outcome]
            / f"{digest[:12]}_{test.name}"
        )

        if not duplicate:
            shutil.copy2(test, destination)

        record = {
            "test_id": test.name,
            "sha256": digest,
            "classification": outcome,
            "duplicate": duplicate,
            "size_bytes": test.stat().st_size,
        }

        records.append(record)

        print(
            f"{outcome:10} "
            f"{test.name} "
            f"{'(duplicate)' if duplicate else ''}"
        )

    classification_file = (
        experiment_directory / "classification.jsonl"
    )

    with classification_file.open("w") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    total = len(records)

    usable = (
        counts["PASS"]
        + counts["FAIL"]
    )

    summary = {
        "total_queue_entries": total,
        "unique_inputs": len(seen_hashes),
        "PASS": counts["PASS"],
        "FAIL": counts["FAIL"],
        "UNRESOLVED": counts["UNRESOLVED"],
        "usable": usable,
        "usable_rate": (
            usable / total
            if total
            else 0.0
        ),
    }

    return summary


def read_fuzzer_stats(raw_directory: Path) -> dict:
    stats_file = raw_directory / "fuzzer_stats"

    if not stats_file.exists():
        return {}

    stats = {}

    for line in stats_file.read_text().splitlines():
        if ":" not in line:
            continue

        key, value = line.split(":", 1)

        stats[key.strip()] = value.strip()

    return stats

def collect_and_analyze_coverage(
    experiment_directory: Path,
) -> dict:

    pass_directory = experiment_directory / "pass"
    fail_directory = experiment_directory / "fail"

    pass_files = [
        path
        for path in pass_directory.iterdir()
        if path.is_file()
    ]

    fail_files = [
        path
        for path in fail_directory.iterdir()
        if path.is_file()
    ]

    # SBFL/coverage comparison requires both classes.
    if not pass_files or not fail_files:
        return {
            "status": "skipped",
            "reason": (
                "Coverage collection requires at least "
                "one PASS and one FAIL test."
            ),
            "pass_tests": len(pass_files),
            "fail_tests": len(fail_files),
        }

    collector = (
        PROJECT_ROOT
        / "scripts"
        / "collect_coverage.py"
    )

    subprocess.run(
        [
            sys.executable,
            str(collector),
            str(experiment_directory),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )

    coverage_file = (
        experiment_directory
        / "coverage"
        / "coverage.jsonl"
    )

    records = [
        json.loads(line)
        for line in coverage_file.read_text().splitlines()
        if line.strip()
    ]

    result = {
        "status": "completed",
    }

    for outcome in ("PASS", "FAIL"):

        selected = [
            record
            for record in records
            if record["classification"] == outcome
        ]

        profiles = defaultdict(list)

        for record in selected:
            profile = tuple(record["covered_lines"])

            profiles[profile].append(
                record["test_id"]
            )

        key = outcome.lower()

        result[f"{key}_tests"] = len(selected)

        result[
            f"distinct_{key}_profiles"
        ] = len(profiles)

        result[
            f"{key}_profile_test_counts"
        ] = sorted(
            len(tests)
            for tests in profiles.values()
        )

        result[
            f"{key}_profile_line_counts"
        ] = sorted(
            len(profile)
            for profile in profiles
        )

    summary_file = (
        experiment_directory
        / "coverage"
        / "summary.json"
    )

    if summary_file.exists():
        result["collector_summary"] = json.loads(
            summary_file.read_text()
        )

    return result


def count_peach_chunk_structures(
    raw_directory: Path,
) -> int:

    chunk_directory = raw_directory / "chunks"

    if not chunk_directory.exists():
        return 0

    return sum(
        1
        for path in chunk_directory.glob("*.chunks")
        if path.is_file()
    )


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--mode",
        required=True,
        choices=[
            "afl",
            "aflsmart-nonstack",
            "aflsmart-mixed",
        ],
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Fuzzing duration in seconds.",
    )

    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
    )

    arguments = parser.parse_args()

    if not TARGET.exists():
        raise SystemExit(
            f"Missing AFLSmart target: {TARGET}"
        )

    if not SEED_DIRECTORY.exists():
        raise SystemExit(
            f"Missing seed directory: {SEED_DIRECTORY}"
        )

    if (
        arguments.mode.startswith("aflsmart")
        and not PIT_FILE.exists()
    ):
        raise SystemExit(
            f"Missing PIT file: {PIT_FILE}"
        )

    RESULTS_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    for repetition in range(
        1,
        arguments.repeat + 1,
    ):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        run_name = (
            f"{arguments.mode}"
            f"_r{repetition}_"
            f"{timestamp}"
        )

        experiment_directory = (
            RESULTS_ROOT / run_name
        )

        raw_directory = (
            experiment_directory / "raw"
        )

        experiment_directory.mkdir(
            parents=True
        )

        afl_arguments = run_fuzzer(
            arguments.mode,
            arguments.duration,
            raw_directory,
        )

        print()
        print("Classifying retained queue")
        print("=" * 72)

        classification_summary = classify_queue(
            raw_directory,
            experiment_directory,
        )

        print()
        print("Collecting source coverage")
        print("=" * 72)

        coverage_summary = collect_and_analyze_coverage(
        experiment_directory
        )

        print()
        print("Coverage diversity")
        print("=" * 72)

        print(
            json.dumps(
            coverage_summary,
            indent=2,
            )
        )

        fuzzer_stats = read_fuzzer_stats(
            raw_directory
        )

        metadata = {
            "mode": arguments.mode,
            "repetition": repetition,
            "duration_seconds": arguments.duration,
            "git_commit": get_git_commit(),
            "docker_image": IMAGE,
            "target": str(
                TARGET.relative_to(PROJECT_ROOT)
            ),
            "target_sha256": sha256_file(TARGET),
            "pit": (
                str(PIT_FILE.relative_to(PROJECT_ROOT))
                if arguments.mode.startswith("aflsmart")
                else None
            ),
            "pit_sha256": (
                sha256_file(PIT_FILE)
                if arguments.mode.startswith("aflsmart")
                else None
            ),
            "afl_arguments": afl_arguments,
            "classification": classification_summary,
            "fuzzer_stats": fuzzer_stats,
            "coverage": coverage_summary,

            "peach_chunk_structures": (
                count_peach_chunk_structures(
                raw_directory
                )
            ),
        }

        metadata_file = (
            experiment_directory
            / "metadata.json"
        )

        metadata_file.write_text(
            json.dumps(
                metadata,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        print()
        print("Experiment complete")
        print("=" * 72)

        print(
            json.dumps(
                classification_summary,
                indent=2,
            )
        )

        print()
        print(
            f"Results: {experiment_directory}"
        )


if __name__ == "__main__":
    main()