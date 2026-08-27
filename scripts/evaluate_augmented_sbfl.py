#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

FUZZ_ROOT = (
    PROJECT_ROOT
    / "results"
    / "fuzz_experiments"
)

OUTPUT_ROOT = (
    PROJECT_ROOT
    / "results"
    / "augmented_sbfl"
)

MODES = (
    "afl",
    "aflsmart-mixed",
    "aflsmart-nonstack",
)


def read_jsonl(path: Path) -> list[dict]:
    records = []

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():

        if not line.strip():
            continue

        records.append(
            json.loads(line)
        )

    return records


def write_jsonl(
    path: Path,
    records: list[dict],
) -> None:

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:

        for record in records:
            handle.write(
                json.dumps(record)
                + "\n"
            )


def verify_compatible(
    baseline_records: list[dict],
    fuzz_records: list[dict],
) -> None:

    baseline_lines = set(
        baseline_records[0][
            "executable_lines"
        ]
    )

    for record in fuzz_records:

        fuzz_lines = set(
            record[
                "executable_lines"
            ]
        )

        if fuzz_lines != baseline_lines:
            raise RuntimeError(
                "Baseline and fuzz coverage "
                "use different executable-line sets."
            )


def prepare_baseline_records(
    records: list[dict],
) -> list[dict]:

    prepared = []

    for record in records:

        item = dict(record)

        item["test_id"] = (
            "baseline::"
            + str(
                record.get(
                    "test_id",
                    "unknown",
                )
            )
        )

        item[
            "augmentation_source"
        ] = "baseline"

        prepared.append(item)

    return prepared


def prepare_fuzz_records(
    records: list[dict],
) -> tuple[list[dict], int]:

    prepared = []

    skipped_original_seed = 0

    for record in records:

        test_id = str(
            record.get(
                "test_id",
                "",
            )
        )

        #
        # Every fuzz run starts from the
        # original DDMIN minimal FAIL seed.
        #
        # The DDMIN spectrum already contains
        # the baseline failure, so including
        # this queue entry would double-count it.
        #

        if (
            "orig:minimal_failure.xml"
            in test_id
        ):
            skipped_original_seed += 1
            continue

        item = dict(record)

        item["test_id"] = (
            "fuzz::"
            + test_id
        )

        item[
            "augmentation_source"
        ] = "fuzz"

        prepared.append(item)

    return (
        prepared,
        skipped_original_seed,
    )


def run_sbfl(
    run_directory: Path,
    fault_line: int,
) -> dict:

    command = [
        sys.executable,
        str(
            PROJECT_ROOT
            / "scripts"
            / "sbfl.py"
        ),
        str(run_directory),
        "--fault-line",
        str(fault_line),
    ]

    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True,
    )

    summary_file = (
        run_directory
        / "sbfl"
        / "summary.json"
    )

    return json.loads(
        summary_file.read_text(
            encoding="utf-8"
        )
    )


def metric_result(
    summary: dict,
    metric: str,
) -> dict:

    result = summary[metric]

    return {
        "score": (
            result[
                "first_fault_score"
            ]
        ),
        "best_rank": (
            result["best_rank"]
        ),
        "average_rank": (
            result[
                "average_rank"
            ]
        ),
        "worst_rank": (
            result["worst_rank"]
        ),
        "exam_percentage": (
            result[
                "exam_percentage_average"
            ]
        ),
    }


def evaluate_baseline(
    baseline_records: list[dict],
    fault_line: int,
) -> dict:

    baseline_output = (
        OUTPUT_ROOT
        / "baseline"
    )

    if baseline_output.exists():
        shutil.rmtree(
            baseline_output
        )

    records_file = (
        baseline_output
        / "coverage"
        / "coverage.jsonl"
    )

    write_jsonl(
        records_file,
        prepare_baseline_records(
            baseline_records
        ),
    )

    summary = run_sbfl(
        baseline_output,
        fault_line,
    )

    return {
        "passing_tests": (
            summary["passing_tests"]
        ),
        "failing_tests": (
            summary["failing_tests"]
        ),
        "total_tests": (
            summary["total_tests"]
        ),
        "jaccard": metric_result(
            summary,
            "jaccard",
        ),
        "ochiai": metric_result(
            summary,
            "ochiai",
        ),
    }


def evaluate_fuzz_run(
    metadata_file: Path,
    baseline_records: list[dict],
    fault_line: int,
) -> dict:

    fuzz_run = metadata_file.parent

    metadata = json.loads(
        metadata_file.read_text(
            encoding="utf-8"
        )
    )

    mode = metadata["mode"]

    fuzz_coverage = (
        fuzz_run
        / "coverage"
        / "coverage.jsonl"
    )

    if not fuzz_coverage.is_file():
        raise RuntimeError(
            f"Missing fuzz coverage: "
            f"{fuzz_coverage}"
        )

    fuzz_records = read_jsonl(
        fuzz_coverage
    )

    verify_compatible(
        baseline_records,
        fuzz_records,
    )

    prepared_baseline = (
        prepare_baseline_records(
            baseline_records
        )
    )

    (
        prepared_fuzz,
        skipped_seed,
    ) = prepare_fuzz_records(
        fuzz_records
    )

    combined_records = (
        prepared_baseline
        + prepared_fuzz
    )

    output_directory = (
        OUTPUT_ROOT
        / mode
        / fuzz_run.name
    )

    if output_directory.exists():
        shutil.rmtree(
            output_directory
        )

    combined_file = (
        output_directory
        / "coverage"
        / "coverage.jsonl"
    )

    write_jsonl(
        combined_file,
        combined_records,
    )

    summary = run_sbfl(
        output_directory,
        fault_line,
    )

    generated_pass = sum(
        record["classification"]
        == "PASS"
        for record in prepared_fuzz
    )

    generated_fail = sum(
        record["classification"]
        == "FAIL"
        for record in prepared_fuzz
    )

    result = {
        "mode": mode,
        "run_name": fuzz_run.name,
        "repetition": metadata.get(
            "repetition"
        ),
        "duration_seconds": (
            metadata.get(
                "duration_seconds"
            )
        ),

        "baseline_tests": len(
            baseline_records
        ),

        "added_fuzz_tests": len(
            prepared_fuzz
        ),

        "added_PASS": generated_pass,

        "added_FAIL": generated_fail,

        "skipped_original_seed": (
            skipped_seed
        ),

        "combined_PASS": (
            summary[
                "passing_tests"
            ]
        ),

        "combined_FAIL": (
            summary[
                "failing_tests"
            ]
        ),

        "combined_total": (
            summary[
                "total_tests"
            ]
        ),

        "jaccard": metric_result(
            summary,
            "jaccard",
        ),

        "ochiai": metric_result(
            summary,
            "ochiai",
        ),
    }

    result_file = (
        output_directory
        / "augmentation_summary.json"
    )

    result_file.write_text(
        json.dumps(
            result,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return result


def write_csv(
    results: list[dict],
    output_file: Path,
) -> None:

    fields = [
        "mode",
        "run_name",
        "repetition",
        "duration_seconds",
        "baseline_tests",
        "added_fuzz_tests",
        "added_PASS",
        "added_FAIL",
        "combined_PASS",
        "combined_FAIL",
        "combined_total",

        "jaccard_score",
        "jaccard_best_rank",
        "jaccard_average_rank",
        "jaccard_worst_rank",
        "jaccard_exam_percentage",

        "ochiai_score",
        "ochiai_best_rank",
        "ochiai_average_rank",
        "ochiai_worst_rank",
        "ochiai_exam_percentage",
    ]

    with output_file.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )

        writer.writeheader()

        for result in results:

            row = {
                "mode": result["mode"],
                "run_name": (
                    result["run_name"]
                ),
                "repetition": (
                    result["repetition"]
                ),
                "duration_seconds": (
                    result[
                        "duration_seconds"
                    ]
                ),

                "baseline_tests": (
                    result[
                        "baseline_tests"
                    ]
                ),

                "added_fuzz_tests": (
                    result[
                        "added_fuzz_tests"
                    ]
                ),

                "added_PASS": (
                    result[
                        "added_PASS"
                    ]
                ),

                "added_FAIL": (
                    result[
                        "added_FAIL"
                    ]
                ),

                "combined_PASS": (
                    result[
                        "combined_PASS"
                    ]
                ),

                "combined_FAIL": (
                    result[
                        "combined_FAIL"
                    ]
                ),

                "combined_total": (
                    result[
                        "combined_total"
                    ]
                ),
            }

            for metric in (
                "jaccard",
                "ochiai",
            ):
                metric_data = (
                    result[metric]
                )

                row[
                    f"{metric}_score"
                ] = metric_data["score"]

                row[
                    f"{metric}_best_rank"
                ] = metric_data[
                    "best_rank"
                ]

                row[
                    f"{metric}_average_rank"
                ] = metric_data[
                    "average_rank"
                ]

                row[
                    f"{metric}_worst_rank"
                ] = metric_data[
                    "worst_rank"
                ]

                row[
                    f"{metric}_exam_percentage"
                ] = metric_data[
                    "exam_percentage"
                ]

            writer.writerow(row)


def print_result(
    result: dict,
) -> None:

    print(
        f"{result['mode']:<22} "
        f"r{result['repetition']}  "
        f"+PASS={result['added_PASS']:<3} "
        f"+FAIL={result['added_FAIL']:<3} "
        f"| "
        f"Jaccard rank="
        f"{result['jaccard']['average_rank']:<5.1f} "
        f"EXAM="
        f"{result['jaccard']['exam_percentage']:<6.2f}% "
        f"| "
        f"Ochiai rank="
        f"{result['ochiai']['average_rank']:<5.1f} "
        f"EXAM="
        f"{result['ochiai']['exam_percentage']:<6.2f}%"
    )


def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--baseline-run",
        type=Path,
        required=True,
        help=(
            "Original DDMIN run containing "
            "coverage/coverage.jsonl."
        ),
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=300,
    )

    parser.add_argument(
        "--fault-line",
        type=int,
        default=144,
    )

    arguments = parser.parse_args()

    baseline_run = (
        arguments.baseline_run
        .resolve()
    )

    baseline_coverage = (
        baseline_run
        / "coverage"
        / "coverage.jsonl"
    )

    if not baseline_coverage.is_file():
        raise SystemExit(
            "Baseline coverage not found:\n"
            f"{baseline_coverage}\n\n"
            "Run collect_coverage.py on the "
            "baseline DDMIN run first."
        )

    baseline_records = read_jsonl(
        baseline_coverage
    )

    if not baseline_records:
        raise SystemExit(
            "Baseline coverage is empty."
        )

    OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 80)
    print("BASELINE DDMIN SBFL")
    print("=" * 80)

    baseline_summary = evaluate_baseline(
        baseline_records,
        arguments.fault_line,
    )

    print()
    print(
        "Baseline Jaccard: "
        f"rank="
        f"{baseline_summary['jaccard']['average_rank']:.1f}, "
        f"EXAM="
        f"{baseline_summary['jaccard']['exam_percentage']:.2f}%"
    )

    print(
        "Baseline Ochiai : "
        f"rank="
        f"{baseline_summary['ochiai']['average_rank']:.1f}, "
        f"EXAM="
        f"{baseline_summary['ochiai']['exam_percentage']:.2f}%"
    )

    metadata_files = []

    for metadata_file in sorted(
        FUZZ_ROOT.glob(
            "*/metadata.json"
        )
    ):

        metadata = json.loads(
            metadata_file.read_text(
                encoding="utf-8"
            )
        )

        if (
            metadata.get(
                "duration_seconds"
            )
            != arguments.duration
        ):
            continue

        if (
            metadata.get("mode")
            not in MODES
        ):
            continue

        metadata_files.append(
            metadata_file
        )

    print()
    print("=" * 80)
    print(
        "DDMIN + FUZZ AUGMENTED SBFL"
    )
    print("=" * 80)

    results = []

    for metadata_file in metadata_files:

        result = evaluate_fuzz_run(
            metadata_file,
            baseline_records,
            arguments.fault_line,
        )

        results.append(result)

        print_result(result)

    output_csv = (
        OUTPUT_ROOT
        / (
            f"augmented_sbfl_"
            f"{arguments.duration}s.csv"
        )
    )

    write_csv(
        results,
        output_csv,
    )

    combined_summary = {
        "baseline_run": str(
            baseline_run
        ),

        "fault_line": (
            arguments.fault_line
        ),

        "duration_seconds": (
            arguments.duration
        ),

        "baseline": (
            baseline_summary
        ),

        "runs": results,
    }

    output_json = (
        OUTPUT_ROOT
        / (
            f"augmented_sbfl_"
            f"{arguments.duration}s.json"
        )
    )

    output_json.write_text(
        json.dumps(
            combined_summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print("Saved")
    print("=" * 80)

    print(
        f"CSV : {output_csv}"
    )

    print(
        f"JSON: {output_json}"
    )


if __name__ == "__main__":
    main()