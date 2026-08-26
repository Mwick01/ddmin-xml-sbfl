from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from oracle import classify


PROJECT_ROOT = Path(__file__).resolve().parent.parent

BUGGY_SOURCE = (
    PROJECT_ROOT / "subjects" / "invoice" / "buggy" / "invoice.c"
)

COVERAGE_BINARY = PROJECT_ROOT / "build" / "invoice_buggy_cov"
COVERAGE_OBJECT = PROJECT_ROOT / "build" / "invoice_buggy_cov.o"
COVERAGE_DATA = PROJECT_ROOT / "build" / "invoice_buggy_cov.gcda"

TIMEOUT_SECONDS = 2.0

GCOV_LINE_PATTERN = re.compile(
    r"^\s*([^:]+):\s*(\d+):(.*)$"
)

UNEXECUTED_MARKERS = {
    "#####",
    "=====",
    "$$$$$",
    "%%%%%",
}


def append_json_line(
    path: Path,
    record: dict[str, Any],
) -> None:
    """Append one JSON object to a JSON Lines file."""

    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, sort_keys=True))
        file.write("\n")


def file_sha256(path: Path) -> str:
    """Calculate the SHA-256 digest of a file."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(65536):
            digest.update(chunk)

    return digest.hexdigest()


def command_version(command: str) -> str:
    """Return the first line of a command's version output."""

    completed = subprocess.run(
        [command, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )

    output = completed.stdout.strip() or completed.stderr.strip()

    if not output:
        return "unknown"

    return output.splitlines()[0]


def reset_coverage_data() -> None:
    """
    Delete runtime coverage from previous executions.

    This is essential because GCC normally accumulates coverage counters
    across program executions.
    """

    for data_file in (
        PROJECT_ROOT / "build"
    ).glob("invoice_buggy_cov*.gcda"):
        data_file.unlink(missing_ok=True)


def run_instrumented_program(
    candidate_file: Path,
) -> subprocess.CompletedProcess[str]:
    """Execute the coverage-instrumented buggy program."""

    try:
        completed = subprocess.run(
            [str(COVERAGE_BINARY), str(candidate_file)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )

    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"Instrumented program timed out for {candidate_file}"
        ) from error

    if completed.returncode != 0:
        raise RuntimeError(
            "Instrumented buggy program returned a nonzero exit code.\n"
            f"Candidate: {candidate_file}\n"
            f"Exit code: {completed.returncode}\n"
            f"Stdout: {completed.stdout!r}\n"
            f"Stderr: {completed.stderr!r}"
        )

    if not COVERAGE_DATA.is_file():
        raise RuntimeError(
            "The instrumented program did not create the expected "
            f"coverage data file: {COVERAGE_DATA}"
        )

    return completed


def run_gcov() -> str:
    """Run gcov and return its source-annotated output."""

    completed = subprocess.run(
        [
            "gcov",
            "--stdout",
            "--object-file",
            str(COVERAGE_OBJECT),
            str(BUGGY_SOURCE),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "gcov failed.\n"
            f"Exit code: {completed.returncode}\n"
            f"Stdout: {completed.stdout}\n"
            f"Stderr: {completed.stderr}"
        )

    return completed.stdout


def resolve_reported_source(source_text: str) -> Path:
    """Resolve a source pathname reported by gcov."""

    source_path = Path(source_text)

    if not source_path.is_absolute():
        source_path = PROJECT_ROOT / source_path

    return source_path.resolve()


def parse_execution_count(count_field: str) -> int | None:
    """
    Convert a gcov execution field into a numeric count.

    Returns:
        None for non-executable lines.
        0 for executable but unexecuted lines.
        A positive integer for executed lines.
    """

    normalized = count_field.strip()

    if normalized == "-":
        return None

    if normalized in UNEXECUTED_MARKERS:
        return 0

    # gcov may add '*' when only some blocks on a line executed.
    normalized = normalized.rstrip("*").replace(",", "")

    if normalized.isdigit():
        return int(normalized)

    raise ValueError(
        f"Unsupported gcov execution count: {count_field!r}"
    )


def parse_gcov_output(
    gcov_output: str,
) -> dict[int, int]:
    """
    Parse line execution counts for the buggy invoice source.

    Returns:
        Dictionary mapping source line number to execution count.
    """

    expected_source = BUGGY_SOURCE.resolve()
    current_source: Path | None = None

    execution_counts: dict[int, int] = {}

    for raw_line in gcov_output.splitlines():
        match = GCOV_LINE_PATTERN.match(raw_line)

        if match is None:
            continue

        count_field = match.group(1).strip()
        line_number = int(match.group(2))
        source_text = match.group(3)

        # Source metadata appears as:
        # -:0:Source:/absolute/path/invoice.c
        if line_number == 0:
            if source_text.startswith("Source:"):
                reported_source = source_text.removeprefix(
                    "Source:"
                ).strip()

                current_source = resolve_reported_source(
                    reported_source
                )

            continue

        # Ignore any source or header other than the target buggy file.
        if (
            current_source is not None
            and current_source != expected_source
        ):
            continue

        execution_count = parse_execution_count(count_field)

        if execution_count is None:
            continue

        # For normal C source there should be one entry per line.
        # max() also handles any repeated gcov entries safely for
        # binary statement coverage.
        previous_count = execution_counts.get(line_number, 0)

        execution_counts[line_number] = max(
            previous_count,
            execution_count,
        )

    if not execution_counts:
        raise RuntimeError(
            "No executable source lines were found in gcov output."
        )

    return execution_counts


def collect_candidate_coverage(
    candidate_file: Path,
    expected_label: str,
) -> dict[str, Any]:
    """Collect independent line coverage for one candidate."""

    actual_label = classify(candidate_file)

    if actual_label != expected_label:
        raise RuntimeError(
            "Candidate label changed before coverage collection.\n"
            f"Candidate: {candidate_file}\n"
            f"Expected: {expected_label}\n"
            f"Actual: {actual_label}"
        )

    reset_coverage_data()

    execution = run_instrumented_program(candidate_file)
    gcov_output = run_gcov()

    execution_counts = parse_gcov_output(gcov_output)

    executable_lines = sorted(execution_counts)
    covered_lines = sorted(
        line_number
        for line_number, count in execution_counts.items()
        if count > 0
    )

    return {
        "test_id": candidate_file.name,
        "candidate_file": str(candidate_file),
        "classification": expected_label,
        "program_exit_code": execution.returncode,
        "program_stdout": execution.stdout.strip(),
        "program_stderr": execution.stderr.strip(),
        "executable_lines": executable_lines,
        "covered_lines": covered_lines,
        "execution_counts": {
            str(line_number): execution_counts[line_number]
            for line_number in executable_lines
        },
    }


def find_candidate_files(
    run_directory: Path,
) -> list[tuple[str, Path]]:
    """Find all unique PASS and FAIL candidates."""

    pass_directory = run_directory / "pass"
    fail_directory = run_directory / "fail"

    passing_files = sorted(
        path
        for path in pass_directory.iterdir()
        if path.is_file()
    )

    failing_files = sorted(
        path
        for path in fail_directory.iterdir()
        if path.is_file()
    )

    if not passing_files:
        raise RuntimeError(
            "No PASS candidates were found. "
            "SBFL needs at least one passing test."
        )

    if not failing_files:
        raise RuntimeError(
            "No FAIL candidates were found. "
            "SBFL needs at least one failing test."
        )

    candidates: list[tuple[str, Path]] = []

    candidates.extend(
        ("PASS", path.resolve())
        for path in passing_files
    )

    candidates.extend(
        ("FAIL", path.resolve())
        for path in failing_files
    )

    return candidates


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect independent gcov line coverage for all PASS and "
            "FAIL candidates in a DDMIN run."
        )
    )

    parser.add_argument(
        "run_directory",
        type=Path,
        help="Path to one results/ddmin_runs/<run-id> directory.",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    run_directory = arguments.run_directory.resolve()

    if not run_directory.is_dir():
        print(
            f"Error: run directory not found: {run_directory}",
            file=sys.stderr,
        )
        return 2

    required_files = [
        BUGGY_SOURCE,
        COVERAGE_BINARY,
        COVERAGE_OBJECT,
    ]

    for required_file in required_files:
        if not required_file.is_file():
            print(
                f"Error: required file not found: {required_file}",
                file=sys.stderr,
            )
            return 2

    try:
        candidates = find_candidate_files(run_directory)
    except RuntimeError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    coverage_directory = run_directory / "coverage"
    coverage_directory.mkdir(parents=True, exist_ok=True)

    records_file = coverage_directory / "coverage.jsonl"
    summary_file = coverage_directory / "summary.json"

    # Make repeated runs overwrite old coverage results.
    records_file.write_text("", encoding="utf-8")

    all_executable_lines: set[int] = set()
    all_covered_lines: set[int] = set()

    passing_count = 0
    failing_count = 0

    total_candidates = len(candidates)

    print(f"DDMIN run: {run_directory}")
    print(f"Candidates: {total_candidates}")
    print(f"Coverage output: {coverage_directory}")
    print()

    try:
        for index, (label, candidate_file) in enumerate(
            candidates,
            start=1,
        ):
            print(
                f"[{index}/{total_candidates}] "
                f"{label} {candidate_file.name[:12]}...",
                end=" ",
                flush=True,
            )

            record = collect_candidate_coverage(
                candidate_file,
                label,
            )

            append_json_line(records_file, record)

            covered_lines = set(record["covered_lines"])
            executable_lines = set(record["executable_lines"])

            all_covered_lines.update(covered_lines)
            all_executable_lines.update(executable_lines)

            if label == "PASS":
                passing_count += 1
            else:
                failing_count += 1

            print(
                f"covered={len(covered_lines)}/"
                f"{len(executable_lines)}"
            )

    except (RuntimeError, ValueError, OSError) as error:
        print()
        print(f"Coverage collection failed: {error}", file=sys.stderr)
        return 1

    finally:
        reset_coverage_data()

    summary = {
        "ddmin_run_directory": str(run_directory),
        "buggy_source": str(BUGGY_SOURCE),
        "buggy_source_sha256": file_sha256(BUGGY_SOURCE),
        "coverage_binary": str(COVERAGE_BINARY),
        "coverage_object": str(COVERAGE_OBJECT),
        "gcc_version": command_version("gcc"),
        "gcov_version": command_version("gcov"),
        "total_tests": total_candidates,
        "passing_tests": passing_count,
        "failing_tests": failing_count,
        "executable_line_count": len(all_executable_lines),
        "covered_line_union_count": len(all_covered_lines),
        "executable_lines": sorted(all_executable_lines),
        "covered_line_union": sorted(all_covered_lines),
        "coverage_records": str(records_file),
    }

    summary_file.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print()
    print("Coverage collection completed")
    print(f"PASS tests: {passing_count}")
    print(f"FAIL tests: {failing_count}")
    print(
        f"Executable source lines: {len(all_executable_lines)}"
    )
    print(
        f"Lines covered by at least one test: "
        f"{len(all_covered_lines)}"
    )
    print(f"Records: {records_file}")
    print(f"Summary: {summary_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())