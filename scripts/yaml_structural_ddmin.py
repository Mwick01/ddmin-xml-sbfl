from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import importlib
import json
import os
from pathlib import Path
from typing import Any

from yaml_structural_candidates import (
    Deletion,
    collect_deletions,
    parse_yaml,
    valid_yaml,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_RESULTS_ROOT = (
    PROJECT_ROOT
    / "results"
    / "yaml_structural_ddmin_runs"
)

DEFAULT_TEMP_FILE = (
    PROJECT_ROOT
    / "temporary"
    / "yaml_structural_ddmin_candidate.yaml"
)


def append_json_line(
    path: Path,
    record: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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


def candidate_hash(candidate: str) -> str:
    return hashlib.sha256(
        candidate.encode("utf-8")
    ).hexdigest()


def split_ranges(
    length: int,
    number_of_parts: int,
) -> list[tuple[int, int]]:
    if length <= 0:
        return []

    number_of_parts = max(
        1,
        min(number_of_parts, length),
    )

    basic_size, remainder = divmod(
        length,
        number_of_parts,
    )

    ranges: list[tuple[int, int]] = []

    start = 0

    for index in range(number_of_parts):
        size = basic_size + (
            1 if index < remainder else 0
        )

        end = start + size

        if start < end:
            ranges.append(
                (start, end)
            )

        start = end

    return ranges


def apply_deletions(
    source: str,
    deletions: list[Deletion],
) -> str:
    """
    Apply a group of logical structural deletions safely.

    Structural deletion spans are valid only for the source from which
    they were discovered. They must therefore NOT be merged and applied
    as frozen character ranges.

    Instead:

    1. discard duplicate operations;
    2. discard descendants when their ancestor is already selected;
    3. process operations from right to left in the original document;
    4. reparse after every deletion;
    5. rediscover the requested logical path in the new tree;
    6. use its newly calculated separator-aware span.

    Processing from right to left preserves the positional paths of
    structural units that occur earlier in the document.
    """

    if not deletions:
        return source

    #
    # Deduplicate logical operations by path.
    #
    by_path: dict[str, Deletion] = {}

    for deletion in deletions:
        if deletion.start < deletion.end:
            by_path[deletion.path] = deletion

    selected = list(by_path.values())

    if not selected:
        return source

    selected_paths = {
        deletion.path
        for deletion in selected
    }

    #
    # If an ancestor and one of its descendants are both selected,
    # deleting the ancestor already removes the descendant.
    #
    effective: list[Deletion] = []

    for deletion in selected:
        has_selected_ancestor = any(
            deletion.path.startswith(
                other_path + "."
            )
            for other_path in selected_paths
            if other_path != deletion.path
        )

        if not has_selected_ancestor:
            effective.append(deletion)

    #
    # Right-to-left is essential.
    #
    # Example:
    #
    #   root.entry[0]
    #   root.entry[1]
    #
    # Delete entry[1] first. That leaves entry[0]'s identity and index
    # unchanged. Deleting entry[0] first would cause entry[1] to shift.
    #
    effective.sort(
        key=lambda deletion: (
            deletion.start,
            deletion.end,
        ),
        reverse=True,
    )

    candidate = source

    for requested in effective:
        #
        # Every intermediate candidate should itself remain valid YAML.
        # If a structural deletion unexpectedly violates that invariant,
        # return it so CandidateRecorder records INVALID_YAML rather than
        # silently hiding the failure.
        #
        if not valid_yaml(candidate):
            return candidate

        root = parse_yaml(candidate)

        if root is None:
            return candidate

        current_operations = collect_deletions(
            candidate,
            root,
        )

        matches = [
            operation
            for operation in current_operations
            if (
                operation.path == requested.path
                and operation.kind == requested.kind
            )
        ]

        if len(matches) != 1:
            raise RuntimeError(
                "Could not uniquely rediscover structural operation "
                f"{requested.path!r} ({requested.kind!r}); "
                f"found {len(matches)} matches."
            )

        current = matches[0]

        candidate = (
            candidate[:current.start]
            + candidate[current.end:]
        )

    return candidate


class CandidateRecorder:
    def __init__(
        self,
        temporary_file: Path,
        output_directory: Path,
        classifier,
    ) -> None:
        self.temporary_file = temporary_file
        self.output_directory = output_directory
        self.classifier = classifier

        self.cache: dict[str, str] = {}

        self.generated_attempts = 0
        self.oracle_attempts = 0
        self.unique_count = 0

        self.outcome_counts: Counter[str] = Counter()

        self.attempt_log = (
            output_directory
            / "attempts.jsonl"
        )

        self.unique_log = (
            output_directory
            / "unique_candidates.jsonl"
        )

        for directory_name in (
            "pass",
            "fail",
            "unresolved",
            "invalid_yaml",
        ):
            (
                output_directory
                / directory_name
            ).mkdir(
                parents=True,
                exist_ok=True,
            )

        temporary_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def evaluate(
        self,
        candidate: str,
        context: dict[str, Any],
    ) -> str:
        self.generated_attempts += 1

        encoded = candidate.encode("utf-8")

        digest = hashlib.sha256(
            encoded
        ).hexdigest()

        cached = digest in self.cache

        if cached:
            outcome = self.cache[digest]

        else:
            if not valid_yaml(candidate):
                outcome = "INVALID_YAML"

            else:
                self.temporary_file.write_bytes(
                    encoded
                )

                outcome = self.classifier(
                    self.temporary_file
                )

                self.oracle_attempts += 1

            self.cache[digest] = outcome
            self.unique_count += 1
            self.outcome_counts[outcome] += 1

            directory_name = {
                "PASS": "pass",
                "FAIL": "fail",
                "UNRESOLVED": "unresolved",
                "INVALID_YAML": "invalid_yaml",
            }[outcome]

            saved_candidate = (
                self.output_directory
                / directory_name
                / f"{digest}.yaml"
            )

            saved_candidate.write_bytes(
                encoded
            )

            append_json_line(
                self.unique_log,
                {
                    "candidate_id": digest,
                    "classification": outcome,
                    "size_characters": len(candidate),
                    "size_bytes": len(encoded),
                    "saved_path": str(
                        saved_candidate.relative_to(
                            self.output_directory
                        )
                    ),
                    "first_context": context,
                },
            )

        append_json_line(
            self.attempt_log,
            {
                "attempt_number": self.generated_attempts,
                "candidate_id": digest,
                "classification": outcome,
                "cached": cached,
                "size_characters": len(candidate),
                "size_bytes": len(encoded),
                "context": context,
            },
        )

        return outcome


def make_candidate(
    current: str,
    operations: list[Deletion],
    selected_indexes: list[int],
) -> str:
    selected = [
        operations[index]
        for index in selected_indexes
    ]

    return apply_deletions(
        current,
        selected,
    )


def structural_ddmin(
    original: str,
    recorder: CandidateRecorder,
    reduction_log: Path,
) -> tuple[str, int]:
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
            "The original input must classify as FAIL, "
            f"not {initial_outcome}."
        )

    current = original

    iteration = 0
    granularity = 2

    while True:
        root = parse_yaml(current)

        if root is None:
            raise RuntimeError(
                "Accepted candidate unexpectedly has no YAML document."
            )

        operations = collect_deletions(
            current,
            root,
        )

        if not operations:
            break

        granularity = min(
            max(1, granularity),
            len(operations),
        )

        iteration += 1

        ranges = split_ranges(
            len(operations),
            granularity,
        )

        reduction_found = False

        print(
            f"Iteration {iteration}: "
            f"size={len(current)}, "
            f"structural_units={len(operations)}, "
            f"granularity={granularity}, "
            f"parts={len(ranges)}"
        )

        #
        # First try removing each selected structural subset.
        #
        for part_index, (start, end) in enumerate(ranges):
            selected_indexes = list(
                range(start, end)
            )

            candidate = make_candidate(
                current,
                operations,
                selected_indexes,
            )

            if candidate == current:
                continue

            outcome = recorder.evaluate(
                candidate,
                {
                    "phase": "subset_removal",
                    "iteration": iteration,
                    "granularity": granularity,
                    "part_index": part_index,
                    "operation_indexes": selected_indexes,
                    "operation_paths": [
                        operations[index].path
                        for index in selected_indexes
                    ],
                    "parent_size": len(current),
                },
            )

            if outcome == "FAIL":
                previous_size = len(current)

                current = candidate

                append_json_line(
                    reduction_log,
                    {
                        "iteration": iteration,
                        "phase": "subset_removal",
                        "part_index": part_index,
                        "previous_size": previous_size,
                        "new_size": len(current),
                        "candidate_id": candidate_hash(
                            current
                        ),
                        "operation_paths": [
                            operations[index].path
                            for index in selected_indexes
                        ],
                    },
                )

                print(
                    "  Accepted failing structural subset: "
                    f"{previous_size} -> {len(current)}"
                )

                granularity = max(
                    1,
                    granularity - 1,
                )

                reduction_found = True
                break

        if reduction_found:
            continue

        #
        # If no subset removal preserves failure, try the
        # complementary group of structural deletions.
        #
        all_indexes = list(
            range(len(operations))
        )

        for part_index, (start, end) in enumerate(ranges):
            excluded = set(
                range(start, end)
            )

            selected_indexes = [
                index
                for index in all_indexes
                if index not in excluded
            ]

            if not selected_indexes:
                continue

            candidate = make_candidate(
                current,
                operations,
                selected_indexes,
            )

            if candidate == current:
                continue

            outcome = recorder.evaluate(
                candidate,
                {
                    "phase": "complement_removal",
                    "iteration": iteration,
                    "granularity": granularity,
                    "part_index": part_index,
                    "operation_indexes": selected_indexes,
                    "operation_paths": [
                        operations[index].path
                        for index in selected_indexes
                    ],
                    "parent_size": len(current),
                },
            )

            if outcome == "FAIL":
                previous_size = len(current)

                current = candidate

                append_json_line(
                    reduction_log,
                    {
                        "iteration": iteration,
                        "phase": "complement_removal",
                        "part_index": part_index,
                        "previous_size": previous_size,
                        "new_size": len(current),
                        "candidate_id": candidate_hash(
                            current
                        ),
                        "operation_paths": [
                            operations[index].path
                            for index in selected_indexes
                        ],
                    },
                )

                print(
                    "  Accepted failing structural complement: "
                    f"{previous_size} -> {len(current)}"
                )

                granularity = max(
                    1,
                    granularity - 1,
                )

                reduction_found = True
                break

        if reduction_found:
            continue

        if granularity >= len(operations):
            break

        granularity = min(
            len(operations),
            granularity * 2,
        )

    return current, iteration


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply structure-aware delta debugging "
            "to a YAML failure-inducing input."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
    )

    parser.add_argument(
        "--results-root",
        type=Path,
        default=DEFAULT_RESULTS_ROOT,
    )

    parser.add_argument(
        "--temporary-file",
        type=Path,
        default=DEFAULT_TEMP_FILE,
    )

    parser.add_argument(
        "--oracle-module",
        default="oracle_libyaml_flow",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    input_file = arguments.input_file.resolve()

    if not input_file.is_file():
        print(
            f"ERROR: input not found: {input_file}"
        )
        return 2

    original = input_file.read_text(
        encoding="utf-8"
    )

    run_id = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        + f"_{os.getpid()}"
    )

    results_root = (
        arguments.results_root.resolve()
    )

    run_directory = (
        results_root
        / run_id
    )

    run_directory.mkdir(
        parents=True,
        exist_ok=False,
    )

    oracle_module = importlib.import_module(
        arguments.oracle_module
    )

    classifier = getattr(
        oracle_module,
        "classify",
    )

    recorder = CandidateRecorder(
        temporary_file=(
            arguments.temporary_file.resolve()
        ),
        output_directory=run_directory,
        classifier=classifier,
    )

    reduction_log = (
        run_directory
        / "reductions.jsonl"
    )

    print(
        f"Input: {input_file}"
    )

    print(
        f"Original size: {len(original)} characters"
    )

    print(
        f"Results: {run_directory}"
    )

    print()

    try:
        minimal, iteration_count = (
            structural_ddmin(
                original,
                recorder,
                reduction_log,
            )
        )

    except ValueError as error:
        print(
            f"ERROR: {error}"
        )
        return 1

    minimal_file = (
        run_directory
        / "minimal_failure.yaml"
    )

    minimal_file.write_text(
        minimal,
        encoding="utf-8",
    )

    original_size = len(original)
    minimal_size = len(minimal)

    reduction_percentage = (
        0.0
        if original_size == 0
        else (
            100.0
            * (
                original_size
                - minimal_size
            )
            / original_size
        )
    )

    summary = {
        "input_file": str(input_file),
        "original_candidate_id": candidate_hash(
            original
        ),
        "minimal_candidate_id": candidate_hash(
            minimal
        ),
        "original_size_characters": original_size,
        "minimal_size_characters": minimal_size,
        "reduction_percentage": round(
            reduction_percentage,
            2,
        ),
        "iterations": iteration_count,
        "generated_attempts": (
            recorder.generated_attempts
        ),
        "oracle_attempts": (
            recorder.oracle_attempts
        ),
        "unique_candidates": (
            recorder.unique_count
        ),
        "passing_candidates": (
            recorder.outcome_counts["PASS"]
        ),
        "failing_candidates": (
            recorder.outcome_counts["FAIL"]
        ),
        "unresolved_candidates": (
            recorder.outcome_counts["UNRESOLVED"]
        ),
        "invalid_yaml_candidates": (
            recorder.outcome_counts["INVALID_YAML"]
        ),
        "minimal_file": str(minimal_file),
        "oracle_module": arguments.oracle_module,
    }

    summary_file = (
        run_directory
        / "summary.json"
    )

    summary_file.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("STRUCTURAL DDMIN COMPLETED")
    print(
        f"Original size: {original_size}"
    )
    print(
        f"Minimal size: {minimal_size}"
    )
    print(
        f"Reduction: {reduction_percentage:.2f}%"
    )
    print(
        "Generated attempts: "
        f"{recorder.generated_attempts}"
    )
    print(
        "Oracle attempts: "
        f"{recorder.oracle_attempts}"
    )
    print(
        "Unique candidates: "
        f"{recorder.unique_count}"
    )
    print(
        "PASS candidates: "
        f"{recorder.outcome_counts['PASS']}"
    )
    print(
        "FAIL candidates: "
        f"{recorder.outcome_counts['FAIL']}"
    )
    print(
        "UNRESOLVED candidates: "
        f"{recorder.outcome_counts['UNRESOLVED']}"
    )
    print(
        "INVALID YAML candidates: "
        f"{recorder.outcome_counts['INVALID_YAML']}"
    )
    print(
        f"Minimal failure: {minimal_file}"
    )
    print(
        f"Summary: {summary_file}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
