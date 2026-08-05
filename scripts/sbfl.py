from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent

BUGGY_SOURCE = (
    PROJECT_ROOT
    / "subjects"
    / "invoice"
    / "buggy"
    / "invoice.c"
)

INSPECT_VALUES = (1, 3, 5, 10)
TIE_TOLERANCE = 1e-12


def load_coverage_records(
    records_file: Path,
) -> list[dict[str, Any]]:
    """Read coverage records from a JSON Lines file."""

    records: list[dict[str, Any]] = []

    for line_number, raw_line in enumerate(
        records_file.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line.strip():
            continue

        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON on line {line_number}: {error}"
            ) from error

        classification = record.get("classification")

        if classification not in {"PASS", "FAIL"}:
            raise ValueError(
                f"Invalid classification on line {line_number}: "
                f"{classification!r}"
            )

        records.append(record)

    if not records:
        raise ValueError("The coverage file contains no test records.")

    return records


def validate_records(
    records: list[dict[str, Any]],
) -> set[int]:
    """
    Verify that all test records refer to the same executable source lines.
    """

    expected_lines = set(records[0]["executable_lines"])

    if not expected_lines:
        raise ValueError("No executable source lines were recorded.")

    for index, record in enumerate(records, start=1):
        executable_lines = set(record["executable_lines"])
        covered_lines = set(record["covered_lines"])

        if executable_lines != expected_lines:
            raise ValueError(
                "Executable-line sets differ between tests. "
                f"Record {index}, test {record.get('test_id')}, "
                "does not match the first record."
            )

        if not covered_lines.issubset(executable_lines):
            unexpected = sorted(covered_lines - executable_lines)

            raise ValueError(
                f"Test {record.get('test_id')} contains covered lines "
                f"that are not executable: {unexpected}"
            )

    return expected_lines


def jaccard(
    ef: int,
    ep: int,
    nf: int,
) -> float:
    """Calculate Jaccard suspiciousness."""

    denominator = ef + ep + nf

    if denominator == 0:
        return 0.0

    return ef / denominator


def ochiai(
    ef: int,
    ep: int,
    nf: int,
) -> float:
    """Calculate Ochiai suspiciousness."""

    denominator = math.sqrt(
        (ef + nf) * (ef + ep)
    )

    if denominator == 0:
        return 0.0

    return ef / denominator


def build_spectrum(
    records: list[dict[str, Any]],
    executable_lines: set[int],
    source_lines: list[str],
    fault_lines: set[int],
) -> list[dict[str, Any]]:
    """
    Calculate coverage counts and suspiciousness for each executable line.
    """

    passing_tests = [
        set(record["covered_lines"])
        for record in records
        if record["classification"] == "PASS"
    ]

    failing_tests = [
        set(record["covered_lines"])
        for record in records
        if record["classification"] == "FAIL"
    ]

    if not passing_tests:
        raise ValueError(
            "SBFL requires at least one passing test."
        )

    if not failing_tests:
        raise ValueError(
            "SBFL requires at least one failing test."
        )

    rows: list[dict[str, Any]] = []

    for line_number in sorted(executable_lines):
        ef = sum(
            line_number in coverage
            for coverage in failing_tests
        )

        ep = sum(
            line_number in coverage
            for coverage in passing_tests
        )

        nf = len(failing_tests) - ef
        np = len(passing_tests) - ep

        source_text = ""

        if 1 <= line_number <= len(source_lines):
            source_text = source_lines[line_number - 1].strip()

        rows.append(
            {
                "line": line_number,
                "source": source_text,
                "ef": ef,
                "ep": ep,
                "nf": nf,
                "np": np,
                "jaccard": jaccard(ef, ep, nf),
                "ochiai": ochiai(ef, ep, nf),
                "faulty": line_number in fault_lines,
            }
        )

    return rows


def scores_equal(
    first: float,
    second: float,
) -> bool:
    """Compare suspiciousness scores safely."""

    return math.isclose(
        first,
        second,
        rel_tol=TIE_TOLERANCE,
        abs_tol=TIE_TOLERANCE,
    )


def create_ranking(
    spectrum: list[dict[str, Any]],
    metric: str,
) -> list[dict[str, Any]]:
    """
    Sort lines by suspiciousness and assign tie-aware ranks.

    For a tie occupying positions 2 through 5:

        best rank    = 2
        average rank = 3.5
        worst rank   = 5
    """

    ranking = [
        {
            **row,
            "score": float(row[metric]),
        }
        for row in spectrum
    ]

    ranking.sort(
        key=lambda row: (
            -row["score"],
            row["line"],
        )
    )

    index = 0

    while index < len(ranking):
        end = index + 1

        while (
            end < len(ranking)
            and scores_equal(
                ranking[index]["score"],
                ranking[end]["score"],
            )
        ):
            end += 1

        best_rank = index + 1
        worst_rank = end
        average_rank = (best_rank + worst_rank) / 2.0

        for tied_index in range(index, end):
            ranking[tied_index]["best_rank"] = best_rank
            ranking[tied_index]["average_rank"] = average_rank
            ranking[tied_index]["worst_rank"] = worst_rank

        index = end

    return ranking


def summarize_metric(
    ranking: list[dict[str, Any]],
    fault_lines: set[int],
    executable_line_count: int,
) -> dict[str, Any]:
    """Summarize how the known faulty lines were ranked."""

    faulty_entries = [
        row
        for row in ranking
        if row["line"] in fault_lines
    ]

    if not faulty_entries:
        raise ValueError(
            "None of the supplied faulty lines are executable."
        )

    # For multi-line faults, fault localization succeeds when the first
    # known faulty line is reached.
    first_fault = min(
        faulty_entries,
        key=lambda row: (
            row["average_rank"],
            row["line"],
        ),
    )

    fault_details = []

    for row in sorted(
        faulty_entries,
        key=lambda entry: entry["line"],
    ):
        fault_details.append(
            {
                "line": row["line"],
                "source": row["source"],
                "score": row["score"],
                "best_rank": row["best_rank"],
                "average_rank": row["average_rank"],
                "worst_rank": row["worst_rank"],
                "exam_score_average": (
                    row["average_rank"]
                    / executable_line_count
                ),
            }
        )

    average_rank = first_fault["average_rank"]

    return {
        "first_fault_line": first_fault["line"],
        "first_fault_source": first_fault["source"],
        "first_fault_score": first_fault["score"],
        "best_rank": first_fault["best_rank"],
        "average_rank": average_rank,
        "worst_rank": first_fault["worst_rank"],
        "executable_line_count": executable_line_count,
        "exam_score_average": (
            average_rank / executable_line_count
        ),
        "exam_percentage_average": (
            100.0
            * average_rank
            / executable_line_count
        ),
        "inspect_at_average_rank": {
            str(value): average_rank <= value
            for value in INSPECT_VALUES
        },
        "fault_lines": fault_details,
    }


def write_spectrum_csv(
    path: Path,
    spectrum: list[dict[str, Any]],
) -> None:
    """Write line spectra and both suspiciousness scores."""

    fieldnames = [
        "line",
        "source",
        "ef",
        "ep",
        "nf",
        "np",
        "jaccard",
        "ochiai",
        "faulty",
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in spectrum:
            writer.writerow(
                {
                    **row,
                    "jaccard": f"{row['jaccard']:.12f}",
                    "ochiai": f"{row['ochiai']:.12f}",
                }
            )


def write_ranking_csv(
    path: Path,
    ranking: list[dict[str, Any]],
) -> None:
    """Write one metric's suspiciousness ranking."""

    fieldnames = [
        "best_rank",
        "average_rank",
        "worst_rank",
        "line",
        "score",
        "ef",
        "ep",
        "nf",
        "np",
        "faulty",
        "source",
    ]

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for row in ranking:
            writer.writerow(
                {
                    "best_rank": row["best_rank"],
                    "average_rank": row["average_rank"],
                    "worst_rank": row["worst_rank"],
                    "line": row["line"],
                    "score": f"{row['score']:.12f}",
                    "ef": row["ef"],
                    "ep": row["ep"],
                    "nf": row["nf"],
                    "np": row["np"],
                    "faulty": row["faulty"],
                    "source": row["source"],
                }
            )


def format_rank_range(
    row: dict[str, Any],
) -> str:
    """Format a line's tie-aware rank."""

    if row["best_rank"] == row["worst_rank"]:
        return str(row["best_rank"])

    return (
        f"{row['best_rank']}-"
        f"{row['worst_rank']} "
        f"(avg {row['average_rank']:.1f})"
    )


def print_top_lines(
    metric: str,
    ranking: list[dict[str, Any]],
    limit: int = 10,
) -> None:
    """Print the highest-ranked source lines."""

    print()
    print(f"Top {limit} lines using {metric.upper()}")
    print("-" * 90)

    for row in ranking[:limit]:
        fault_marker = " <-- FAULT" if row["faulty"] else ""

        print(
            f"Rank {format_rank_range(row):<18} "
            f"Line {row['line']:<4} "
            f"Score {row['score']:.6f}  "
            f"ef={row['ef']} ep={row['ep']} "
            f"nf={row['nf']} np={row['np']}  "
            f"{row['source']}"
            f"{fault_marker}"
        )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate Jaccard and Ochiai SBFL rankings from "
            "per-test coverage records."
        )
    )

    parser.add_argument(
        "run_directory",
        type=Path,
        help="Path to one results/ddmin_runs/<run-id> directory.",
    )

    parser.add_argument(
        "--fault-line",
        type=int,
        nargs="+",
        required=True,
        help=(
            "Known faulty source line number. Multiple line numbers "
            "may be supplied for a multi-line fault."
        ),
    )

    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of top-ranked lines to print.",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    run_directory = arguments.run_directory.resolve()
    records_file = (
        run_directory
        / "coverage"
        / "coverage.jsonl"
    )

    if not run_directory.is_dir():
        print(
            f"Error: run directory not found: {run_directory}",
            file=sys.stderr,
        )
        return 2

    if not records_file.is_file():
        print(
            "Error: coverage records not found. Run "
            "collect_coverage.py first:\n"
            f"{records_file}",
            file=sys.stderr,
        )
        return 2

    if not BUGGY_SOURCE.is_file():
        print(
            f"Error: buggy source not found: {BUGGY_SOURCE}",
            file=sys.stderr,
        )
        return 2

    fault_lines = set(arguments.fault_line)

    try:
        records = load_coverage_records(records_file)
        executable_lines = validate_records(records)

        missing_fault_lines = (
            fault_lines - executable_lines
        )

        if missing_fault_lines:
            raise ValueError(
                "The following supplied faulty lines are not "
                f"executable according to gcov: "
                f"{sorted(missing_fault_lines)}"
            )

        source_lines = BUGGY_SOURCE.read_text(
            encoding="utf-8"
        ).splitlines()

        spectrum = build_spectrum(
            records=records,
            executable_lines=executable_lines,
            source_lines=source_lines,
            fault_lines=fault_lines,
        )

        jaccard_ranking = create_ranking(
            spectrum,
            "jaccard",
        )

        ochiai_ranking = create_ranking(
            spectrum,
            "ochiai",
        )

        jaccard_summary = summarize_metric(
            jaccard_ranking,
            fault_lines,
            len(executable_lines),
        )

        ochiai_summary = summarize_metric(
            ochiai_ranking,
            fault_lines,
            len(executable_lines),
        )

    except (ValueError, OSError) as error:
        print(f"SBFL calculation failed: {error}", file=sys.stderr)
        return 1

    sbfl_directory = run_directory / "sbfl"
    sbfl_directory.mkdir(parents=True, exist_ok=True)

    spectrum_file = sbfl_directory / "spectrum.csv"
    jaccard_file = sbfl_directory / "jaccard_ranking.csv"
    ochiai_file = sbfl_directory / "ochiai_ranking.csv"
    summary_file = sbfl_directory / "summary.json"

    write_spectrum_csv(
        spectrum_file,
        spectrum,
    )

    write_ranking_csv(
        jaccard_file,
        jaccard_ranking,
    )

    write_ranking_csv(
        ochiai_file,
        ochiai_ranking,
    )

    passing_count = sum(
        record["classification"] == "PASS"
        for record in records
    )

    failing_count = sum(
        record["classification"] == "FAIL"
        for record in records
    )

    summary = {
        "ddmin_run_directory": str(run_directory),
        "coverage_records": str(records_file),
        "buggy_source": str(BUGGY_SOURCE),
        "known_fault_lines": sorted(fault_lines),
        "passing_tests": passing_count,
        "failing_tests": failing_count,
        "total_tests": len(records),
        "executable_line_count": len(executable_lines),
        "jaccard": jaccard_summary,
        "ochiai": ochiai_summary,
        "output_files": {
            "spectrum": str(spectrum_file),
            "jaccard_ranking": str(jaccard_file),
            "ochiai_ranking": str(ochiai_file),
        },
    }

    summary_file.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"PASS tests: {passing_count}")
    print(f"FAIL tests: {failing_count}")
    print(f"Executable lines: {len(executable_lines)}")

    print_top_lines(
        "jaccard",
        jaccard_ranking,
        arguments.top,
    )

    print_top_lines(
        "ochiai",
        ochiai_ranking,
        arguments.top,
    )

    print()
    print("Known fault results")
    print("-" * 60)

    for metric, metric_summary in (
        ("Jaccard", jaccard_summary),
        ("Ochiai", ochiai_summary),
    ):
        print(
            f"{metric}: "
            f"line={metric_summary['first_fault_line']}, "
            f"score={metric_summary['first_fault_score']:.6f}, "
            f"rank={metric_summary['best_rank']}-"
            f"{metric_summary['worst_rank']} "
            f"(average={metric_summary['average_rank']:.2f}), "
            f"EXAM={metric_summary['exam_percentage_average']:.2f}%"
        )

    print()
    print(f"Spectrum: {spectrum_file}")
    print(f"Jaccard ranking: {jaccard_file}")
    print(f"Ochiai ranking: {ochiai_file}")
    print(f"Summary: {summary_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())