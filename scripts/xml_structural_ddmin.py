"""DTD-aware deletion reducer for the libxml2-467 XML fixture.

Supported units are a complete DOCTYPE, internal DTD declarations, simple
CDATA default attributes in ATTLIST declarations, element attributes, and
self-closing non-root elements. Every generated candidate is checked with
Python's strict XML parser before the subject oracle is called.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
from typing import Callable
from xml.dom import minidom


@dataclass(frozen=True)
class Operation:
    path: str
    kind: str
    start: int
    end: int


@dataclass(frozen=True)
class Doctype:
    start: int
    end: int
    subset_start: int | None
    subset_end: int | None


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def well_formed(source: str) -> bool:
    try:
        document = minidom.parseString(source.encode("utf-8"))
    except Exception:
        return False
    document.unlink()
    return True


def doctype_span(source: str) -> Doctype | None:
    match = re.search(r"<!DOCTYPE\b", source, re.IGNORECASE)
    if match is None:
        return None

    quote: str | None = None
    depth = 0
    subset_start: int | None = None
    subset_end: int | None = None
    for index in range(match.end(), len(source)):
        char = source[index]
        if quote:
            if char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char == "[":
            if depth == 0:
                subset_start = index + 1
            depth += 1
        elif char == "]" and depth:
            depth -= 1
            if depth == 0:
                subset_end = index
        elif char == ">" and depth == 0:
            return Doctype(match.start(), index + 1, subset_start, subset_end)
    raise ValueError("Unterminated DOCTYPE")


def markup_end(source: str, start: int) -> int:
    quote: str | None = None
    for index in range(start, len(source)):
        char = source[index]
        if quote:
            if char == quote:
                quote = None
        elif char in ('"', "'"):
            quote = char
        elif char == ">":
            return index + 1
    raise ValueError("Unterminated markup declaration")


DTD_START = re.compile(r"<!([A-Za-z]+)\b")
CDATA_DEFAULT = re.compile(
    r"\s+[A-Za-z_:][\w.:-]*\s+CDATA\s+(?:\"[^\"]*\"|'[^']*')",
    re.DOTALL,
)
TAG = re.compile(r"<(?P<name>[A-Za-z_][\w.:-]*)(?P<attrs>[^<>]*?)>", re.DOTALL)
ATTRIBUTE = re.compile(
    r"\s+[A-Za-z_:][\w.:-]*\s*=\s*(?:\"[^\"]*\"|'[^']*')",
    re.DOTALL,
)


def collect_operations(source: str) -> list[Operation]:
    operations: list[Operation] = []
    doctype = doctype_span(source)
    if doctype is not None:
        operations.append(Operation("doctype", "doctype", doctype.start, doctype.end))
        if doctype.subset_start is not None and doctype.subset_end is not None:
            subset = source[doctype.subset_start:doctype.subset_end]
            last_end = doctype.subset_start
            declaration_index = 0
            for match in DTD_START.finditer(subset):
                start = doctype.subset_start + match.start()
                if start < last_end:
                    continue
                end = markup_end(source, start)
                if end > doctype.subset_end:
                    continue
                path = f"doctype.declaration[{declaration_index}]"
                kind = match.group(1).lower()
                operations.append(Operation(path, f"dtd_{kind}", start, end))
                if kind == "attlist":
                    header = re.match(r"<!ATTLIST\s+[^\s>]+", source[start:end], re.IGNORECASE)
                    if header is not None:
                        body_start = start + header.end()
                        defaults = list(CDATA_DEFAULT.finditer(source[body_start:end - 1]))
                        if len(defaults) > 1:
                            for index, default in enumerate(defaults):
                                operations.append(Operation(
                                    f"{path}.default[{index}]", "dtd_cdata_default",
                                    body_start + default.start(), body_start + default.end(),
                                ))
                last_end = end
                declaration_index += 1

    element_index = 0
    for match in TAG.finditer(source):
        start, end = match.span()
        if doctype is not None and doctype.start <= start < doctype.end:
            continue
        path = f"element[{element_index}]"
        if element_index > 0 and source[start:end].rstrip().endswith("/>"):
            operations.append(Operation(path, "empty_element", start, end))
        attrs_start = match.start("attrs")
        for index, attribute in enumerate(ATTRIBUTE.finditer(match.group("attrs"))):
            operations.append(Operation(
                f"{path}.attribute[{index}]", "element_attribute",
                attrs_start + attribute.start(), attrs_start + attribute.end(),
            ))
        element_index += 1

    return sorted(operations, key=lambda op: (op.start, -op.end, op.path))


def apply_operations(source: str, selected: list[Operation]) -> str:
    unique = list({(op.start, op.end): op for op in selected}.values())
    effective = [
        op for op in unique
        if not any(
            other is not op and other.start <= op.start and op.end <= other.end
            for other in unique
        )
    ]
    effective.sort(key=lambda op: op.start)
    if any(left.end > right.start for left, right in zip(effective, effective[1:])):
        raise ValueError("Partially overlapping XML deletion spans")
    candidate = source
    for op in reversed(effective):
        candidate = candidate[:op.start] + candidate[op.end:]
    return candidate


def append_jsonl(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


class Recorder:
    def __init__(self, output: Path, temporary_file: Path, classify: Callable[[Path], str]):
        self.output = output
        self.temporary_file = temporary_file
        self.classify = classify
        self.cache: dict[str, str] = {}
        self.generated_attempts = 0
        self.oracle_attempts = 0
        self.counts: Counter[str] = Counter()
        temporary_file.parent.mkdir(parents=True, exist_ok=True)
        for folder in ("pass", "fail", "unresolved", "invalid_xml"):
            (output / folder).mkdir(parents=True, exist_ok=True)

    def evaluate(self, candidate: str, context: dict) -> str:
        self.generated_attempts += 1
        digest = sha256(candidate)
        cached = digest in self.cache
        if not cached:
            if not well_formed(candidate):
                outcome = "INVALID_XML"
            else:
                self.temporary_file.write_text(candidate, encoding="utf-8")
                outcome = self.classify(self.temporary_file)
                self.oracle_attempts += 1
            if outcome not in {"PASS", "FAIL", "UNRESOLVED", "INVALID_XML"}:
                raise ValueError(f"Unexpected oracle outcome: {outcome}")
            self.cache[digest] = outcome
            self.counts[outcome] += 1
            folder = outcome.lower()
            saved = self.output / folder / f"{digest}.xml"
            saved.write_text(candidate, encoding="utf-8")
            append_jsonl(self.output / "unique_candidates.jsonl", {
                "candidate_id": digest, "classification": outcome,
                "size_characters": len(candidate),
                "saved_path": str(saved.relative_to(self.output)),
                "first_context": context,
            })
        outcome = self.cache[digest]
        append_jsonl(self.output / "attempts.jsonl", {
            "attempt_number": self.generated_attempts, "candidate_id": digest,
            "classification": outcome, "cached": cached,
            "size_characters": len(candidate), "context": context,
        })
        return outcome


def parts(length: int, granularity: int) -> list[tuple[int, int]]:
    count = max(1, min(length, granularity))
    size, extra = divmod(length, count)
    result = []
    start = 0
    for index in range(count):
        end = start + size + (index < extra)
        result.append((start, end))
        start = end
    return result


def reduce(original: str, recorder: Recorder) -> tuple[str, int]:
    if recorder.evaluate(original, {"phase": "initial", "iteration": 0}) != "FAIL":
        raise ValueError("Original input must classify as FAIL and be well-formed XML")
    current = original
    iteration = 0
    granularity = 2
    while True:
        operations = collect_operations(current)
        if not operations:
            break
        granularity = min(max(1, granularity), len(operations))
        iteration += 1
        ranges = parts(len(operations), granularity)
        print(f"Iteration {iteration}: size={len(current)}, units={len(operations)}, parts={len(ranges)}")
        accepted = False
        for phase in ("subset_removal", "complement_removal"):
            for index, (start, end) in enumerate(ranges):
                chosen = (
                    operations[start:end]
                    if phase == "subset_removal"
                    else operations[:start] + operations[end:]
                )
                if not chosen:
                    continue
                candidate = apply_operations(current, chosen)
                if candidate == current:
                    continue
                context = {
                    "phase": phase, "iteration": iteration,
                    "granularity": granularity, "part_index": index,
                    "operation_paths": [op.path for op in chosen],
                }
                if recorder.evaluate(candidate, context) == "FAIL":
                    append_jsonl(recorder.output / "reductions.jsonl", {
                        **context, "previous_size": len(current),
                        "new_size": len(candidate), "candidate_id": sha256(candidate),
                    })
                    print(f"  Accepted FAIL: {len(current)} -> {len(candidate)}")
                    current = candidate
                    granularity = max(1, granularity - 1)
                    accepted = True
                    break
            if accepted:
                break
        if accepted:
            continue
        if granularity >= len(operations):
            break
        granularity = min(len(operations), granularity * 2)
    return current, iteration


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--temporary-file", type=Path)
    parser.add_argument("--oracle-module", default="oracle_libxml2_467")
    args = parser.parse_args()
    root = args.project_root.resolve()
    sys.path.insert(0, str(root / "scripts"))
    input_file = (root / args.input_file).resolve()
    results_root = (root / (args.results_root or "results/libxml2_467_structural_ddmin")).resolve()
    temporary_file = (root / (args.temporary_file or "temporary/libxml2_467_structural_candidate.xml")).resolve()
    original = input_file.read_text(encoding="utf-8")
    output = results_root / f"{datetime.now():%Y%m%d_%H%M%S_%f}"
    output.mkdir(parents=True, exist_ok=False)
    oracle = importlib.import_module(args.oracle_module)
    recorder = Recorder(output, temporary_file, oracle.classify)
    print("Input:", input_file)
    print("Results:", output)
    minimal, iterations = reduce(original, recorder)
    minimal_file = output / "minimal_failure.xml"
    minimal_file.write_text(minimal, encoding="utf-8")
    summary = {
        "input_file": str(input_file), "oracle_module": args.oracle_module,
        "original_candidate_id": sha256(original),
        "minimal_candidate_id": sha256(minimal),
        "original_size_characters": len(original),
        "minimal_size_characters": len(minimal),
        "reduction_percentage": round(100 * (len(original) - len(minimal)) / len(original), 2),
        "iterations": iterations,
        "generated_attempts": recorder.generated_attempts,
        "oracle_attempts": recorder.oracle_attempts,
        "unique_candidates": len(recorder.cache),
        "passing_candidates": recorder.counts["PASS"],
        "failing_candidates": recorder.counts["FAIL"],
        "unresolved_candidates": recorder.counts["UNRESOLVED"],
        "invalid_xml_candidates": recorder.counts["INVALID_XML"],
        "minimal_file": str(minimal_file),
        "reducer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
