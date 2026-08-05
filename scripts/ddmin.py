from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

from oracle import Outcome, classify


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "results" / "ddmin_runs"
DEFAULT_TEMP_FILE = PROJECT_ROOT / "temporary" / "ddmin_candidate.xml"


def append_json_line(path: Path, record: dict[str, Any]) -> None:
    """Append one JSON object to a JSON Lines file."""

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, sort_keys=True))
        file.write("\n")


def candidate_hash(candidate: str) -> str:
    """Create a stable identifier for a candidate."""

    return hashlib.sha256(candidate.encode("utf-8")).hexdigest()


def split_ranges(length: int, number_of_parts: int) -> list[tuple[int, int]]:
    """
    Divide a sequence into approximately equal, non-empty ranges.

    Each returned pair is:
        (start_index, end_index)

    The end index is exclusive.
    """

    if length <= 0:
        return []

    number_of_parts = max(1, min(number_of_parts, length))

    basic_size, remainder = divmod(length, number_of_parts)

    ranges: list[tuple[int, int]] = []
    start = 0

    for index in range(number_of_parts):
        part_size = basic_size + (1 if index < remainder else 0)
        end = start + part_size

        if start < end:
            ranges.append((start, end))

        start = end

    return ranges


class CandidateRecorder:
    """
    Execute and record every unique DDMIN candidate.

    Duplicate candidates are returned from the cache rather than executed
    again. Every attempted evaluation is still written to attempts.jsonl.
    """

    def __init__(
        self,
        temporary_file: Path,
        output_directory: Path,
    ) -> None:
        self.temporary_file = temporary_file
        self.output_directory = output_directory

        self.cache: dict[str, Outcome] = {}

        self.attempt_count = 0
        self.unique_count = 0
        self.outcome_counts: Counter[str] = Counter()

        self.attempt_log = output_directory / "attempts.jsonl"
        self.unique_log = output_directory / "unique_candidates.jsonl"

        for directory_name in ("pass", "fail", "unresolved"):
            (output_directory / directory_name).mkdir(
                parents=True,
                exist_ok=True,
            )

        temporary_file.parent.mkdir(parents=True, exist_ok=True)

    def evaluate(
        self,
        candidate: str,
        context: dict[str, Any] | None = None,
    ) -> Outcome:
        """
        Classify a candidate and record its result.

        The context records why DDMIN generated the candidate, such as:
        - iteration;
        - granularity;
        - subset or complement;
        - selected range.
        """

        self.attempt_count += 1

        if context is None:
            context = {}

        encoded_candidate = candidate.encode("utf-8")
        digest = hashlib.sha256(encoded_candidate).hexdigest()

        cached = digest in self.cache

        if cached:
            outcome = self.cache[digest]

        else:
            self.temporary_file.write_bytes(encoded_candidate)

            outcome = classify(self.temporary_file)

            self.cache[digest] = outcome
            self.unique_count += 1
            self.outcome_counts[outcome] += 1

            output_name = outcome.lower()
            saved_candidate = (
                self.output_directory
                / output_name
                / f"{digest}.xml"
            )

            saved_candidate.write_bytes(encoded_candidate)

            unique_record = {
                "candidate_id": digest,
                "classification": outcome,
                "size_characters": len(candidate),
                "size_bytes": len(encoded_candidate),
                "saved_path": str(
                    saved_candidate.relative_to(self.output_directory)
                ),
                "first_context": context,
            }

            append_json_line(self.unique_log, unique_record)

        attempt_record = {
            "attempt_number": self.attempt_count,
            "candidate_id": digest,
            "classification": outcome,
            "cached": cached,
            "size_characters": len(candidate),
            "size_bytes": len(encoded_candidate),
            "context": context,
        }

        append_json_line(self.attempt_log, attempt_record)

        return outcome


def ddmin(
    original: str,
    recorder: CandidateRecorder,
    reduction_log: Path,
) -> tuple[str, int]:
    """
    Minimize a failure-inducing string using the DDMIN algorithm.

    The function tests both:
    - individual subsets;
    - complements formed by removing individual subsets.

    Only candidates classified as FAIL are accepted as reductions.
    """

    initial_outcome = recorder.evaluate(
        original,
        {
            "phase": "initial",
            "iteration": 0,
            "granularity": 1,
        },
    )

    if initial_outcome != "FAIL":
        raise ValueError(
            "The original input must be classified as FAIL, "
            f"but it was classified as {initial_outcome}."
        )

    current = original
    granularity = 2
    iteration = 0

    while len(current) >= 2:
        iteration += 1

        ranges = split_ranges(len(current), granularity)
        reduction_found = False

        print(
            f"Iteration {iteration}: "
            f"size={len(current)}, "
            f"granularity={granularity}, "
            f"parts={len(ranges)}"
        )

        # First test each individual subset.
        for part_index, (start, end) in enumerate(ranges):
            subset = current[start:end]

            outcome = recorder.evaluate(
                subset,
                {
                    "phase": "subset",
                    "iteration": iteration,
                    "granularity": granularity,
                    "part_index": part_index,
                    "start": start,
                    "end": end,
                    "parent_size": len(current),
                },
            )

            if outcome == "FAIL":
                previous_size = len(current)
                current = subset

                append_json_line(
                    reduction_log,
                    {
                        "iteration": iteration,
                        "phase": "subset",
                        "part_index": part_index,
                        "previous_size": previous_size,
                        "new_size": len(current),
                        "candidate_id": candidate_hash(current),
                    },
                )

                granularity = max(granularity - 1, 2)
                reduction_found = True

                print(
                    f"  Accepted failing subset: "
                    f"{previous_size} -> {len(current)}"
                )

                break

        if reduction_found:
            continue

        # If no subset fails, test complements.
        for part_index, (start, end) in enumerate(ranges):
            complement = current[:start] + current[end:]

            outcome = recorder.evaluate(
                complement,
                {
                    "phase": "complement",
                    "iteration": iteration,
                    "granularity": granularity,
                    "part_index": part_index,
                    "removed_start": start,
                    "removed_end": end,
                    "parent_size": len(current),
                },
            )

            if outcome == "FAIL":
                previous_size = len(current)
                current = complement

                append_json_line(
                    reduction_log,
                    {
                        "iteration": iteration,
                        "phase": "complement",
                        "part_index": part_index,
                        "previous_size": previous_size,
                        "new_size": len(current),
                        "candidate_id": candidate_hash(current),
                    },
                )

                granularity = max(granularity - 1, 2)
                reduction_found = True

                print(
                    f"  Accepted failing complement: "
                    f"{previous_size} -> {len(current)}"
                )

                break

        if reduction_found:
            continue

        # DDMIN cannot divide the current input any further.
        if granularity >= len(current):
            break

        granularity = min(len(current), granularity * 2)

    return current, iteration


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply character-level DDMIN to a failure-inducing XML input."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
        help="Original XML file that the oracle classifies as FAIL.",
    )

    parser.add_argument(
        "--results-root",
        type=Path,
        default=DEFAULT_RESULTS_ROOT,
        help="Directory under which a new run directory is created.",
    )

    parser.add_argument(
        "--temporary-file",
        type=Path,
        default=DEFAULT_TEMP_FILE,
        help="Temporary XML file used when executing candidates.",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    input_file = arguments.input_file.resolve()

    if not input_file.is_file():
        print(f"Error: input file not found: {input_file}", file=sys.stderr)
        return 2

    try:
        original = input_file.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        print(f"Error: input is not valid UTF-8: {error}", file=sys.stderr)
        return 2

    run_id = (
        datetime.now().strftime("%Y%m%d_%H%M%S")
        + f"_{os.getpid()}"
    )

    results_root = arguments.results_root.resolve()
    run_directory = results_root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)

    recorder = CandidateRecorder(
        temporary_file=arguments.temporary_file.resolve(),
        output_directory=run_directory,
    )

    reduction_log = run_directory / "reductions.jsonl"

    print(f"Input: {input_file}")
    print(f"Original size: {len(original)} characters")
    print(f"Results: {run_directory}")
    print()

    try:
        minimal, iteration_count = ddmin(
            original=original,
            recorder=recorder,
            reduction_log=reduction_log,
        )
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    minimal_file = run_directory / "minimal_failure.xml"
    minimal_file.write_text(minimal, encoding="utf-8")

    original_size = len(original)
    minimal_size = len(minimal)

    if original_size == 0:
        reduction_percentage = 0.0
    else:
        reduction_percentage = (
            100.0 * (original_size - minimal_size) / original_size
        )

    summary = {
        "input_file": str(input_file),
        "original_candidate_id": candidate_hash(original),
        "minimal_candidate_id": candidate_hash(minimal),
        "original_size_characters": original_size,
        "minimal_size_characters": minimal_size,
        "reduction_percentage": round(reduction_percentage, 2),
        "iterations": iteration_count,
        "oracle_attempts": recorder.attempt_count,
        "unique_candidates": recorder.unique_count,
        "passing_candidates": recorder.outcome_counts["PASS"],
        "failing_candidates": recorder.outcome_counts["FAIL"],
        "unresolved_candidates": recorder.outcome_counts["UNRESOLVED"],
        "minimal_file": str(minimal_file),
    }

    summary_file = run_directory / "summary.json"

    summary_file.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print()
    print("DDMIN completed")
    print(f"Original size: {original_size}")
    print(f"Minimal size: {minimal_size}")
    print(f"Reduction: {reduction_percentage:.2f}%")
    print(f"Oracle attempts: {recorder.attempt_count}")
    print(f"Unique candidates: {recorder.unique_count}")
    print(f"PASS candidates: {recorder.outcome_counts['PASS']}")
    print(f"FAIL candidates: {recorder.outcome_counts['FAIL']}")
    print(
        "UNRESOLVED candidates: "
        f"{recorder.outcome_counts['UNRESOLVED']}"
    )
    print(f"Minimal failure: {minimal_file}")
    print(f"Summary: {summary_file}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())