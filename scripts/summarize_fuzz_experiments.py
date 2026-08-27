#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RESULTS_ROOT = (
    PROJECT_ROOT
    / "results"
    / "fuzz_experiments"
)


def as_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def mean(values):
    if not values:
        return 0.0

    return statistics.mean(values)


def median(values):
    if not values:
        return 0.0

    return statistics.median(values)


def stddev(values):
    if len(values) < 2:
        return 0.0

    return statistics.stdev(values)


def load_runs(duration: int):

    runs = []

    for metadata_file in sorted(
        RESULTS_ROOT.glob("*/metadata.json")
    ):
        metadata = json.loads(
            metadata_file.read_text()
        )

        if (
            metadata.get("duration_seconds")
            != duration
        ):
            continue

        run_directory = metadata_file.parent

        classification = metadata.get(
            "classification",
            {},
        )

        coverage = metadata.get(
            "coverage",
            {},
        )

        fuzzer_stats = metadata.get(
            "fuzzer_stats",
            {},
        )

        record = {
            "run_directory": run_directory,
            "run_name": run_directory.name,
            "mode": metadata.get("mode"),
            "repetition": metadata.get(
                "repetition"
            ),
            "git_commit": metadata.get(
                "git_commit"
            ),
            "duration_seconds": duration,

            "execs_done": as_int(
                fuzzer_stats.get("execs_done")
            ),

            "paths_found": as_int(
                fuzzer_stats.get("paths_found")
            ),

            "paths_total": as_int(
                fuzzer_stats.get("paths_total")
            ),

            "queue_entries": classification.get(
                "total_queue_entries",
                0,
            ),

            "unique_inputs": classification.get(
                "unique_inputs",
                0,
            ),

            "pass": classification.get(
                "PASS",
                0,
            ),

            "fail": classification.get(
                "FAIL",
                0,
            ),

            "unresolved": classification.get(
                "UNRESOLVED",
                0,
            ),

            "usable": classification.get(
                "usable",
                0,
            ),

            "usable_rate": classification.get(
                "usable_rate",
                0.0,
            ),

            "pass_profiles": coverage.get(
                "distinct_pass_profiles",
                0,
            ),

            "fail_profiles": coverage.get(
                "distinct_fail_profiles",
                0,
            ),

            "peach_chunks": metadata.get(
                "peach_chunk_structures",
                0,
            ),
        }

        #
        # Count generated FAIL inputs separately.
        #
        # Every experiment contains the original
        # DDMIN minimal failure. We do not want to
        # count that as a new fuzzer-generated FAIL.
        #

        generated_fail_count = 0

        generated_fail_hashes = set()

        classification_file = (
            run_directory
            / "classification.jsonl"
        )

        if classification_file.exists():

            for line in (
                classification_file
                .read_text()
                .splitlines()
            ):
                if not line.strip():
                    continue

                candidate = json.loads(line)

                if (
                    candidate.get(
                        "classification"
                    )
                    != "FAIL"
                ):
                    continue

                test_id = candidate.get(
                    "test_id",
                    "",
                )

                if (
                    "orig:minimal_failure.xml"
                    in test_id
                ):
                    continue

                generated_fail_count += 1

                digest = candidate.get(
                    "sha256"
                )

                if digest:
                    generated_fail_hashes.add(
                        digest
                    )

        record[
            "generated_fail_tests"
        ] = generated_fail_count

        record[
            "generated_fail_hashes"
        ] = generated_fail_hashes

        #
        # Recover the actual coverage profiles.
        #
        coverage_file = (
            run_directory
            / "coverage"
            / "coverage.jsonl"
        )

        pass_profiles = set()
        fail_profiles = set()
        generated_fail_profiles = set()

        if coverage_file.exists():

            for line in (
                coverage_file
                .read_text()
                .splitlines()
            ):
                if not line.strip():
                    continue

                candidate = json.loads(line)

                profile = tuple(
                    candidate.get(
                        "covered_lines",
                        [],
                    )
                )

                classification_name = (
                    candidate.get(
                        "classification"
                    )
                )

                test_id = candidate.get(
                    "test_id",
                    "",
                )

                if (
                    classification_name
                    == "PASS"
                ):
                    pass_profiles.add(profile)

                elif (
                    classification_name
                    == "FAIL"
                ):
                    fail_profiles.add(profile)

                    if (
                        "orig:minimal_failure.xml"
                        not in test_id
                    ):
                        generated_fail_profiles.add(
                            profile
                        )

        record[
            "pass_profile_values"
        ] = pass_profiles

        record[
            "fail_profile_values"
        ] = fail_profiles

        record[
            "generated_fail_profile_values"
        ] = generated_fail_profiles

        runs.append(record)

    return runs


def write_run_csv(runs, output_file):

    fields = [
        "mode",
        "repetition",
        "run_name",
        "git_commit",
        "duration_seconds",
        "execs_done",
        "paths_found",
        "paths_total",
        "queue_entries",
        "pass",
        "fail",
        "generated_fail_tests",
        "unresolved",
        "usable",
        "usable_rate",
        "pass_profiles",
        "fail_profiles",
        "peach_chunks",
    ]

    with output_file.open(
        "w",
        newline="",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )

        writer.writeheader()

        for run in runs:

            row = {
                key: run.get(key)
                for key in fields
            }

            writer.writerow(row)


def summarize_mode(mode_runs):

    pass_profiles_global = set()
    fail_profiles_global = set()
    generated_fail_profiles_global = set()

    generated_fail_hashes_global = set()

    commits = set()

    for run in mode_runs:

        commits.add(
            run["git_commit"]
        )

        pass_profiles_global.update(
            run["pass_profile_values"]
        )

        fail_profiles_global.update(
            run["fail_profile_values"]
        )

        generated_fail_profiles_global.update(
            run[
                "generated_fail_profile_values"
            ]
        )

        generated_fail_hashes_global.update(
            run[
                "generated_fail_hashes"
            ]
        )

    queue_total = sum(
        run["queue_entries"]
        for run in mode_runs
    )

    pass_total = sum(
        run["pass"]
        for run in mode_runs
    )

    fail_total = sum(
        run["fail"]
        for run in mode_runs
    )

    unresolved_total = sum(
        run["unresolved"]
        for run in mode_runs
    )

    usable_total = (
        pass_total
        + fail_total
    )

    paths = [
        run["paths_found"]
        for run in mode_runs
    ]

    executions = [
        run["execs_done"]
        for run in mode_runs
    ]

    generated_fails = [
        run["generated_fail_tests"]
        for run in mode_runs
    ]

    pass_profiles = [
        run["pass_profiles"]
        for run in mode_runs
    ]

    fail_profiles = [
        run["fail_profiles"]
        for run in mode_runs
    ]

    peach_chunks = [
        run["peach_chunks"]
        for run in mode_runs
    ]

    return {
        "runs": len(mode_runs),

        "git_commits": sorted(
            commit
            for commit in commits
            if commit
        ),

        "total_executions": sum(
            executions
        ),

        "mean_executions": mean(
            executions
        ),

        "median_executions": median(
            executions
        ),

        "mean_paths_found": mean(
            paths
        ),

        "median_paths_found": median(
            paths
        ),

        "min_paths_found": (
            min(paths)
            if paths
            else 0
        ),

        "max_paths_found": (
            max(paths)
            if paths
            else 0
        ),

        "stddev_paths_found": stddev(
            paths
        ),

        "total_queue_entries": (
            queue_total
        ),

        "total_PASS": pass_total,

        "total_FAIL_including_seed": (
            fail_total
        ),

        "total_UNRESOLVED": (
            unresolved_total
        ),

        "pooled_usable_rate": (
            usable_total / queue_total
            if queue_total
            else 0.0
        ),

        "generated_FAIL_occurrences": sum(
            generated_fails
        ),

        "unique_generated_FAIL_inputs": (
            len(
                generated_fail_hashes_global
            )
        ),

        "mean_generated_FAIL_per_run": (
            mean(generated_fails)
        ),

        "median_generated_FAIL_per_run": (
            median(generated_fails)
        ),

        "mean_PASS_profiles_per_run": (
            mean(pass_profiles)
        ),

        "median_PASS_profiles_per_run": (
            median(pass_profiles)
        ),

        "mean_FAIL_profiles_per_run": (
            mean(fail_profiles)
        ),

        "median_FAIL_profiles_per_run": (
            median(fail_profiles)
        ),

        "unique_PASS_profiles_across_runs": (
            len(pass_profiles_global)
        ),

        "unique_FAIL_profiles_across_runs": (
            len(fail_profiles_global)
        ),

        "unique_generated_FAIL_profiles_across_runs": (
            len(
                generated_fail_profiles_global
            )
        ),

        "total_peach_chunk_structures": (
            sum(peach_chunks)
        ),

        "median_peach_chunk_structures": (
            median(peach_chunks)
        ),
    }


def print_summary(mode, summary):

    print()
    print("=" * 78)
    print(mode.upper())
    print("=" * 78)

    print(
        f"Runs                              : "
        f"{summary['runs']}"
    )

    print(
        f"Total executions                  : "
        f"{summary['total_executions']}"
    )

    print(
        f"Paths found/run mean              : "
        f"{summary['mean_paths_found']:.2f}"
    )

    print(
        f"Paths found/run median            : "
        f"{summary['median_paths_found']:.2f}"
    )

    print(
        f"Paths range                       : "
        f"{summary['min_paths_found']} - "
        f"{summary['max_paths_found']}"
    )

    print()
    print(
        f"Retained queue entries            : "
        f"{summary['total_queue_entries']}"
    )

    print(
        f"PASS                              : "
        f"{summary['total_PASS']}"
    )

    print(
        f"FAIL including original seed      : "
        f"{summary['total_FAIL_including_seed']}"
    )

    print(
        f"UNRESOLVED                        : "
        f"{summary['total_UNRESOLVED']}"
    )

    print(
        f"Pooled usable rate                : "
        f"{summary['pooled_usable_rate'] * 100:.2f}%"
    )

    print()
    print(
        f"Generated FAIL occurrences        : "
        f"{summary['generated_FAIL_occurrences']}"
    )

    print(
        f"Unique generated FAIL inputs      : "
        f"{summary['unique_generated_FAIL_inputs']}"
    )

    print(
        f"Generated FAIL/run median         : "
        f"{summary['median_generated_FAIL_per_run']:.2f}"
    )

    print()
    print(
        f"PASS profiles/run median          : "
        f"{summary['median_PASS_profiles_per_run']:.2f}"
    )

    print(
        f"FAIL profiles/run median          : "
        f"{summary['median_FAIL_profiles_per_run']:.2f}"
    )

    print(
        f"Unique PASS profiles overall      : "
        f"{summary['unique_PASS_profiles_across_runs']}"
    )

    print(
        f"Unique FAIL profiles overall      : "
        f"{summary['unique_FAIL_profiles_across_runs']}"
    )

    print(
        f"Unique generated FAIL profiles    : "
        f"{summary['unique_generated_FAIL_profiles_across_runs']}"
    )

    if mode.startswith("aflsmart"):

        print()
        print(
            f"Total Peach chunk structures      : "
            f"{summary['total_peach_chunk_structures']}"
        )


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--duration",
        type=int,
        default=300,
    )

    arguments = parser.parse_args()

    runs = load_runs(
        arguments.duration
    )

    if not runs:
        raise SystemExit(
            "No matching experiment runs found."
        )

    modes = [
        "afl",
        "aflsmart-mixed",
        "aflsmart-nonstack",
    ]

    grouped = defaultdict(list)

    for run in runs:
        grouped[run["mode"]].append(run)

    summary = {}

    print()
    print(
        f"Pilot summary: "
        f"{arguments.duration}-second runs"
    )
    print("=" * 78)

    for mode in modes:

        mode_runs = grouped.get(
            mode,
            [],
        )

        if not mode_runs:
            continue

        mode_summary = summarize_mode(
            mode_runs
        )

        summary[mode] = mode_summary

        print_summary(
            mode,
            mode_summary,
        )

    output_csv = (
        RESULTS_ROOT
        / f"pilot_runs_{arguments.duration}s.csv"
    )

    output_json = (
        RESULTS_ROOT
        / f"pilot_summary_{arguments.duration}s.json"
    )

    write_run_csv(
        runs,
        output_csv,
    )

    output_json.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    print()
    print("=" * 78)
    print("Saved")
    print("=" * 78)

    print(
        f"Per-run CSV : {output_csv}"
    )

    print(
        f"Summary JSON: {output_json}"
    )


if __name__ == "__main__":
    main()