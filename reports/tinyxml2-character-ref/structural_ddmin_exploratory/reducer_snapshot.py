#!/usr/bin/env python3
"""Exploratory structural deletion of malformed TinyXML-2 #997 fragments.

This is not a strict XML-tree reducer. The historical input is malformed and
contains non-UTF-8 bytes. Lossless units are document markup/comment/text nodes,
complete quoted attributes, and attribute-value reference/raw-text fragments.
Names, reference bodies and raw-text runs are atomic: no byte/character phase,
rewriting, repair, insertion, or XML validity filter is applied.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys


@dataclass(frozen=True)
class Unit:
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class Group:
    path: str
    kind: str
    units: tuple[Unit, ...]


ATTRIBUTE = re.compile(rb'''([A-Za-z_:][A-Za-z0-9_.:-]*)\s*=\s*(["'])(.*?)\2''', re.DOTALL)
REFERENCE = re.compile(rb'&(?:#[^;]*|[A-Za-z_:][A-Za-z0-9_.:-]*);')
TAG_HEAD = re.compile(rb'<[A-Za-z_:][A-Za-z0-9_.:-]*')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def document_nodes(data: bytes) -> list[Unit]:
    """Quote-aware lexical nodes; incomplete final markup ends at EOF."""
    nodes = []
    start = 0
    while start < len(data):
        if data[start:start + 4] == b'<!--':
            close = data.find(b'-->', start + 4)
            end = close + 3 if close >= 0 else len(data)
            kind = 'comment'
        elif data[start:start + 1] == b'<':
            quote = None
            depth = 0
            end = len(data)
            for offset in range(start + 1, len(data)):
                value = data[offset]
                if quote is not None:
                    if value == quote:
                        quote = None
                elif value in (34, 39):
                    quote = value
                elif value == 91:
                    depth += 1
                elif value == 93 and depth:
                    depth -= 1
                elif value == 62 and depth == 0:
                    end = offset + 1
                    break
            kind = 'markup' if data[end - 1:end] == b'>' else 'incomplete_markup'
        else:
            close = data.find(b'<', start + 1)
            end = close if close >= 0 else len(data)
            kind = 'text'
        nodes.append(Unit(start, end, kind))
        start = end
    assert b''.join(data[node.start:node.end] for node in nodes) == data
    return nodes


def collect_groups(data: bytes) -> list[Group]:
    nodes = document_nodes(data)
    groups = [Group('document.children', 'document_nodes', tuple(nodes))]
    for index, node in enumerate(nodes):
        segment = data[node.start:node.end]
        head = TAG_HEAD.match(segment)
        if head is None:
            continue
        attributes = []
        for attr_index, match in enumerate(ATTRIBUTE.finditer(segment, head.end())):
            # Include whitespace owned by the attribute, but preserve adjacent
            # malformed attributes even when they have no intervening space.
            start = match.start()
            while start > head.end() and segment[start - 1] in b' \t\r\n':
                start -= 1
            attributes.append(Unit(node.start + start, node.start + match.end(), 'quoted_attribute'))
            value_start = node.start + match.start(3)
            value = match.group(3)
            fragments = []
            cursor = 0
            for reference in REFERENCE.finditer(value):
                if reference.start() > cursor:
                    fragments.append(Unit(value_start + cursor, value_start + reference.start(), 'raw_value_run'))
                fragments.append(Unit(value_start + reference.start(), value_start + reference.end(), 'reference_fragment'))
                cursor = reference.end()
            if cursor < len(value):
                fragments.append(Unit(value_start + cursor, value_start + len(value), 'raw_value_run'))
            if fragments:
                groups.append(Group(f'document.node[{index}].attribute[{attr_index}].value', 'value_fragments', tuple(fragments)))
        if attributes:
            groups.append(Group(f'document.node[{index}].attributes', 'attributes', tuple(attributes)))
    # Coarse nodes, then attributes, then their value fragments.
    return sorted(groups, key=lambda group: {'document_nodes': 0, 'attributes': 1, 'value_fragments': 2}[group.kind])


def remove_units(data: bytes, units: list[Unit] | tuple[Unit, ...]) -> bytes:
    ordered = sorted(units, key=lambda unit: (unit.start, unit.end))
    assert all(0 <= unit.start < unit.end <= len(data) for unit in ordered)
    assert all(left.end <= right.start for left, right in zip(ordered, ordered[1:]))
    result = data
    for unit in reversed(ordered):
        result = result[:unit.start] + result[unit.end:]
    return result


def partitions(length: int, number: int) -> list[tuple[int, int]]:
    size, extra = divmod(length, min(length, number))
    ranges = []
    start = 0
    for index in range(min(length, number)):
        end = start + size + (index < extra)
        ranges.append((start, end))
        start = end
    return ranges


class Recorder:
    def __init__(self, directory: Path, classify):
        self.directory = directory
        self.classify = classify
        self.cache = {}
        self.attempts = 0
        self.counts = Counter()
        for label in ('pass', 'fail', 'unresolved'):
            (directory / label).mkdir(parents=True)

    def log(self, name: str, row: dict):
        with (self.directory / name).open('a') as handle:
            handle.write(json.dumps(row, sort_keys=True) + '\n')

    def evaluate(self, data: bytes, context: dict) -> str:
        digest = sha(data)
        cached = digest in self.cache
        self.attempts += 1
        if not cached:
            temporary = self.directory / '_candidate.xml'
            temporary.write_bytes(data)
            label = self.classify(temporary)
            assert label in ('PASS', 'FAIL', 'UNRESOLVED')
            destination = self.directory / label.lower() / (digest + '.xml')
            destination.write_bytes(data)
            self.cache[digest] = label
            self.counts[label] += 1
            self.log('unique_candidates.jsonl', {'candidate_id': digest, 'classification': label,
                'size_bytes': len(data), 'saved_path': str(destination.relative_to(self.directory)), 'first_context': context})
        label = self.cache[digest]
        self.log('attempts.jsonl', {'attempt': self.attempts, 'candidate_id': digest, 'classification': label,
            'cached': cached, 'size_bytes': len(data), 'context': context})
        return label


def reduce(data: bytes, recorder: Recorder):
    assert recorder.evaluate(data, {'phase': 'initial'}) == 'FAIL'
    current = data
    iteration = 0
    while True:
        iteration += 1
        accepted = None
        for group in collect_groups(current):
            units = list(group.units)
            trials = [('remove_all', units)]
            granularity = 2
            while len(units) > 1:
                for start, end in partitions(len(units), granularity):
                    trials.append(('keep_subset', units[:start] + units[end:]))
                    trials.append(('remove_subset', units[start:end]))
                if granularity >= len(units):
                    break
                granularity = min(len(units), 2 * granularity)
            for phase, selected in trials:
                if not selected:
                    continue
                candidate = remove_units(current, selected)
                context = {'phase': phase, 'iteration': iteration, 'group': group.path,
                    'group_kind': group.kind, 'deleted_units': [asdict(unit) for unit in selected]}
                if recorder.evaluate(candidate, context) == 'FAIL':
                    assert len(candidate) < len(current)
                    recorder.log('reductions.jsonl', {**context, 'candidate_id': sha(candidate),
                        'previous_bytes': len(current), 'new_bytes': len(candidate)})
                    accepted = candidate
                    print(f'ACCEPT {group.kind}: {len(current)} -> {len(candidate)} bytes', flush=True)
                    break
            if accepted is not None:
                break
        if accepted is None:
            break
        current = accepted
    audit = []
    for group in collect_groups(current):
        for unit in group.units:
            candidate = remove_units(current, [unit])
            context = {'phase': 'one_unit_minimality_audit', 'group': group.path, 'unit': asdict(unit)}
            label = recorder.evaluate(candidate, context)
            assert label != 'FAIL', (group, unit)
            audit.append({**context, 'candidate_id': sha(candidate), 'classification': label})
    return current, iteration, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--input-file', type=Path, default=Path('subjects/tinyxml2-character-ref/poc.xml'))
    args = parser.parse_args()
    root = args.project_root.resolve()
    sys.path.insert(0, str(root / 'scripts'))
    oracle = importlib.import_module('oracle_tinyxml2_character_ref')
    original_path = root / args.input_file
    data = original_path.read_bytes()
    stamp = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime('%Y%m%d_%H%M%S_%f')
    directory = root / 'results/tinyxml2_character_ref' / ('structural_ddmin_exploratory_' + stamp)
    directory.mkdir(parents=True)
    (directory / 'original.xml').write_bytes(data)
    (directory / 'initial_structure.json').write_text(json.dumps([asdict(group) for group in collect_groups(data)], indent=2) + '\n')
    print('RUN ' + str(directory), flush=True)
    recorder = Recorder(directory, oracle.classify)
    minimal, iterations, audit = reduce(data, recorder)
    (directory / 'minimal_failure.xml').write_bytes(minimal)
    (directory / '_candidate.xml').unlink(missing_ok=True)
    summary = {'status': 'EXPLORATORY_MALFORMED_FRAGMENT_STRUCTURAL_DDMIN', 'input_file': str(original_path),
        'run_directory': str(directory), 'original_bytes': len(data), 'minimal_bytes': len(minimal),
        'reduction_percentage': 100 * (len(data) - len(minimal)) / len(data),
        'original_sha256': sha(data), 'minimal_sha256': sha(minimal),
        'iterations': iterations, 'attempts': recorder.attempts, 'unique_candidates': len(recorder.cache),
        'counts': {label: recorder.counts[label] for label in ('PASS', 'FAIL', 'UNRESOLVED')},
        'byte_preserving_deletion_only': True, 'character_reduction_used': False,
        'strict_xml_validation_used': False, 'one_unit_minimality_verified': True,
        'minimality_scope': 'recomputed document nodes, complete quoted attributes, reference/raw attribute-value fragments',
        'minimality_audit': audit, 'final_structure': [asdict(group) for group in collect_groups(minimal)],
        'reducer_sha256': sha(Path(__file__).read_bytes())}
    (directory / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
