from __future__ import annotations

import argparse
import importlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Deletion:
    path: str
    kind: str
    start: int
    end: int


def span(node: yaml.nodes.Node) -> tuple[int, int]:
    return (
        node.start_mark.index,
        node.end_mark.index,
    )


def deletion_span(
    child_spans: list[tuple[int, int]],
    index: int,
) -> tuple[int, int]:
    """
    Return a deletion span that removes one child from a flow collection
    together with the appropriate separator.

    First child:
        remove child + following comma/whitespace.

    Other children:
        remove preceding comma/whitespace + child.

    Sole child:
        remove only the child.
    """

    current_start, current_end = child_spans[index]

    if len(child_spans) == 1:
        return current_start, current_end

    if index == 0:
        next_start, _ = child_spans[index + 1]
        return current_start, next_start

    _, previous_end = child_spans[index - 1]
    return previous_end, current_end


def collect_deletions(
    source: str,
    node: yaml.nodes.Node,
    path: str = "root",
) -> list[Deletion]:
    deletions: list[Deletion] = []

    if isinstance(node, yaml.nodes.SequenceNode):
        if node.flow_style:
            child_spans = [
                span(child)
                for child in node.value
            ]

            for index, child in enumerate(node.value):
                start, end = deletion_span(
                    child_spans,
                    index,
                )

                if start < end:
                    deletions.append(
                        Deletion(
                            path=f"{path}.item[{index}]",
                            kind="sequence_item",
                            start=start,
                            end=end,
                        )
                    )

        for index, child in enumerate(node.value):
            deletions.extend(
                collect_deletions(
                    source,
                    child,
                    f"{path}.item[{index}]",
                )
            )

    elif isinstance(node, yaml.nodes.MappingNode):
        if node.flow_style:
            entry_spans: list[tuple[int, int]] = []

            for key, value in node.value:
                entry_start = key.start_mark.index
                entry_end = value.end_mark.index

                entry_spans.append(
                    (entry_start, entry_end)
                )

            for index, (key, value) in enumerate(node.value):
                entry_start, entry_end = entry_spans[index]

                # PyYAML represents the special "?" mapping used by
                # this bug with zero-width key/value nodes. Do not
                # create a zero-width deletion for that artificial
                # entry. The enclosing sequence item remains removable.
                if entry_start >= entry_end:
                    continue

                start, end = deletion_span(
                    entry_spans,
                    index,
                )

                if start < end:
                    deletions.append(
                        Deletion(
                            path=f"{path}.entry[{index}]",
                            kind="mapping_entry",
                            start=start,
                            end=end,
                        )
                    )

        else:
            # Keep the original line separators. In particular, yaml-cpp's
            # CR regression depends on literal carriage returns, so a
            # parse/dump round trip would change the test case.
            for index, (key, value) in enumerate(node.value):
                start = key.start_mark.index
                if index + 1 < len(node.value):
                    end = node.value[index + 1][0].start_mark.index
                else:
                    end = value.end_mark.index

                if start < end:
                    deletions.append(
                        Deletion(
                            path=f"{path}.entry[{index}]",
                            kind="block_mapping_entry",
                            start=start,
                            end=end,
                        )
                    )

        for index, (key, value) in enumerate(node.value):
            deletions.extend(
                collect_deletions(
                    source,
                    key,
                    f"{path}.entry[{index}].key",
                )
            )

            deletions.extend(
                collect_deletions(
                    source,
                    value,
                    f"{path}.entry[{index}].value",
                )
            )

    elif isinstance(node, yaml.nodes.ScalarNode):
        if node.style in {"|", ">"} and path.endswith(".value"):
            start, end = span(node)
            lines = source[start:end].splitlines(keepends=True)
            offset = start + (len(lines[0]) if lines else 0)

            for index, line in enumerate(lines[1:]):
                if line:
                    deletions.append(
                        Deletion(
                            path=f"{path}.line[{index}]",
                            kind="block_scalar_line",
                            start=offset,
                            end=offset + len(line),
                        )
                    )
                offset += len(line)

        # Delete content while preserving double-quote syntax.
        # Do not alter mapping keys.
        if node.style == '"' and path.endswith(".value"):
            start, end = span(node)
            if (
                end - start > 2
                and source[start] == '"'
                and source[end - 1] == '"'
            ):
                deletions.append(
                    Deletion(
                        path=f"{path}.content",
                        kind="quoted_scalar_content",
                        start=start + 1,
                        end=end - 1,
                    )
                )

    return deletions


def parse_yaml(source: str) -> yaml.nodes.Node | None:
    return yaml.compose(
        source,
        Loader=yaml.SafeLoader,
    )


def valid_yaml(source: str) -> bool:
    try:
        root = parse_yaml(source)
    except yaml.YAMLError:
        return False

    return root is not None


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate one-step structure-aware YAML deletion candidates."
        )
    )

    parser.add_argument(
        "input_file",
        type=Path,
    )

    parser.add_argument(
        "--output-directory",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--oracle-module",
        default="oracle_libyaml_flow",
    )

    arguments = parser.parse_args()

    source = arguments.input_file.read_bytes().decode("utf-8")

    root = parse_yaml(source)

    if root is None:
        raise SystemExit(
            "ERROR: input contains no YAML document"
        )

    deletions = collect_deletions(
        source,
        root,
    )

    output_directory = arguments.output_directory
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    oracle_module = importlib.import_module(
        arguments.oracle_module
    )

    classify = getattr(
        oracle_module,
        "classify",
    )

    records: list[dict[str, object]] = []

    print(
        f"Input: {arguments.input_file}"
    )
    print(
        f"Characters: {len(source)}"
    )
    print(
        f"Structural deletions: {len(deletions)}"
    )
    print()

    for index, deletion in enumerate(deletions):
        candidate = (
            source[:deletion.start]
            + source[deletion.end:]
        )

        removed = source[
            deletion.start:deletion.end
        ]

        parses = valid_yaml(candidate)

        candidate_file = (
            output_directory
            / f"{index:02d}.yaml"
        )

        candidate_file.write_bytes(candidate.encode("utf-8"))

        if parses:
            outcome = classify(
                candidate_file
            )
        else:
            outcome = "INVALID_YAML"

        record = {
            **asdict(deletion),
            "candidate_file": str(candidate_file),
            "removed": removed,
            "valid_yaml": parses,
            "outcome": outcome,
            "candidate": candidate,
        }

        records.append(record)

        print(
            f"{index:02d} "
            f"{deletion.kind:<14} "
            f"{deletion.path:<42} "
            f"[{deletion.start}:{deletion.end}] "
            f"remove={removed!r} "
            f"valid={parses} "
            f"outcome={outcome}"
        )

    results_file = (
        output_directory
        / "results.json"
    )

    results_file.write_text(
        json.dumps(
            records,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    valid_count = sum(
        bool(record["valid_yaml"])
        for record in records
    )

    invalid_count = (
        len(records) - valid_count
    )

    outcomes: dict[str, int] = {}

    for record in records:
        outcome = str(record["outcome"])

        outcomes[outcome] = (
            outcomes.get(outcome, 0) + 1
        )

    print()
    print("===== SUMMARY =====")
    print(
        f"Candidates: {len(records)}"
    )
    print(
        f"Valid YAML: {valid_count}"
    )
    print(
        f"Invalid YAML: {invalid_count}"
    )

    for outcome in sorted(outcomes):
        print(
            f"{outcome}: {outcomes[outcome]}"
        )

    print(
        f"Results: {results_file}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
