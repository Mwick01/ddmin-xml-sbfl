#!/usr/bin/env python3
"""DTD content-model-aware structural DDMIN screening for Expat issue 566.

The reducer removes whole grammar branches, strips quantifiers, and can remove
the containing DTD declaration or DOCTYPE. It never edits arbitrary characters
inside a name. Every unique candidate is XML-validated and checked by the
repository's existing Expat #566 semantic oracle.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
from xml_structural_ddmin import Recorder, append_jsonl, doctype_span, parts, sha256  # noqa: E402


@dataclass(frozen=True)
class Node:
    kind: str
    name: str = ''
    op: str = ''
    children: tuple[Node, ...] = ()
    quant: str = ''


class ModelParser:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0

    def space(self):
        while self.pos < len(self.text) and self.text[self.pos].isspace():
            self.pos += 1

    def cp(self) -> Node:
        self.space()
        if self.pos >= len(self.text):
            raise ValueError('Unexpected end of content model')
        if self.text[self.pos] == '(':
            self.pos += 1
            children = [self.cp()]
            self.space()
            if self.pos >= len(self.text) or self.text[self.pos] not in ',|':
                raise ValueError('Expected group separator')
            op = self.text[self.pos]
            while True:
                if self.text[self.pos] != op:
                    raise ValueError('Mixed group separators')
                self.pos += 1
                children.append(self.cp())
                self.space()
                if self.pos >= len(self.text):
                    raise ValueError('Unclosed group')
                if self.text[self.pos] == ')':
                    self.pos += 1
                    break
            node = Node('group', op=op, children=tuple(children))
        else:
            match = re.match(r'[A-Za-z_:][\w.:-]*', self.text[self.pos:])
            if match is None:
                raise ValueError(f'Expected XML name at offset {self.pos}')
            self.pos += len(match.group())
            node = Node('name', name=match.group())
        self.space()
        if self.pos < len(self.text) and self.text[self.pos] in '?*+':
            node = replace(node, quant=self.text[self.pos])
            self.pos += 1
        return node

    def parse(self) -> Node:
        self.space()
        if self.text[self.pos:].strip() in ('ANY', 'EMPTY'):
            return Node('keyword', name=self.text[self.pos:].strip())
        node = self.cp()
        self.space()
        if self.pos != len(self.text):
            raise ValueError(f'Unexpected content model suffix: {self.text[self.pos:]!r}')
        return node


def render(node: Node) -> str:
    if node.kind in ('name', 'keyword'):
        return node.name + node.quant
    if node.kind == 'group':
        return '(' + node.op.join(render(child) for child in node.children) + ')' + node.quant
    raise ValueError(node.kind)


DECLARATION = re.compile(r'<!ELEMENT\s+junk\s+(?P<model>[^<>]+)>', re.IGNORECASE | re.DOTALL)


def extract(source: str) -> tuple[re.Match[str], Node]:
    match = DECLARATION.search(source)
    if match is None:
        raise ValueError('Missing <!ELEMENT junk ...> declaration')
    return match, ModelParser(match.group('model')).parse()


@dataclass(frozen=True)
class Operation:
    kind: str
    path: tuple[int, ...] = ()

    def label(self) -> str:
        return self.kind + ':' + '.'.join(map(str, self.path))


def collect_operations(source: str) -> list[Operation]:
    try:
        _, root = extract(source)
    except ValueError:
        return []
    operations = [Operation('drop_doctype'), Operation('drop_declaration')]

    def walk(node: Node, path: tuple[int, ...]):
        if node.quant:
            operations.append(Operation('strip_quantifier', path))
        if node.kind == 'group':
            for index, child in enumerate(node.children):
                child_path = path + (index,)
                operations.append(Operation('drop_branch', child_path))
                walk(child, child_path)

    walk(root, ())
    return operations


def apply_operations(source: str, selected: list[Operation]) -> str | None:
    if not selected:
        return None
    kinds = {op.kind for op in selected}
    if 'drop_doctype' in kinds:
        span = doctype_span(source)
        return source[:span.start] + source[span.end:] if span else None
    match, root = extract(source)
    if 'drop_declaration' in kinds:
        return source[:match.start()] + source[match.end():]

    drops = {op.path for op in selected if op.kind == 'drop_branch'}
    strips = {op.path for op in selected if op.kind == 'strip_quantifier'}

    def rewrite(node: Node, path: tuple[int, ...]) -> Node | None:
        quant = '' if path in strips else node.quant
        if node.kind != 'group':
            return replace(node, quant=quant)
        children = []
        for index, child in enumerate(node.children):
            child_path = path + (index,)
            if child_path in drops:
                continue
            rewritten = rewrite(child, child_path)
            if rewritten is not None:
                children.append(rewritten)
        if not children:
            return None
        if len(children) == 1:
            child = children[0]
            if not quant:
                return child
            if child.quant:
                return None  # Nested quantifiers cannot be merged safely.
            return replace(child, quant=quant)
        return Node('group', op=node.op, children=tuple(children), quant=quant)

    reduced = rewrite(root, ())
    if reduced is None:
        return None
    new_model = render(reduced)
    return source[:match.start('model')] + new_model + source[match.end('model'):]


def reduce(original: str, recorder: Recorder) -> tuple[str, int]:
    if recorder.evaluate(original, {'phase': 'initial', 'iteration': 0}) != 'FAIL':
        raise ValueError('Original input is not a valid FAIL')
    current = original
    granularity = 2
    iteration = 0
    while True:
        operations = collect_operations(current)
        if not operations:
            break
        granularity = min(max(2, granularity), len(operations))
        iteration += 1
        ranges = parts(len(operations), granularity)
        print(f'Iteration {iteration}: size={len(current)}, units={len(operations)}, parts={len(ranges)}', flush=True)
        accepted = False
        for phase in ('subset_removal', 'complement_removal'):
            for index, (start, end) in enumerate(ranges):
                chosen = operations[start:end] if phase == 'subset_removal' else operations[:start] + operations[end:]
                candidate = apply_operations(current, chosen)
                if candidate is None or len(candidate) >= len(current):
                    continue
                context = {
                    'phase': phase, 'iteration': iteration, 'granularity': granularity,
                    'part_index': index, 'operations': [op.label() for op in chosen],
                }
                if recorder.evaluate(candidate, context) == 'FAIL':
                    previous_size = len(current)
                    append_jsonl(recorder.output / 'reductions.jsonl', {
                        **context, 'previous_size': previous_size, 'new_size': len(candidate),
                        'candidate_id': sha256(candidate),
                    })
                    current = candidate
                    granularity = max(2, granularity - 1)
                    accepted = True
                    print(f'  Accepted FAIL: {previous_size} -> {len(current)}', flush=True)
                    break
            if accepted:
                break
        if accepted:
            continue
        if granularity >= len(operations):
            break
        granularity = min(len(operations), granularity * 2)
    return current, iteration


def main():
    original_file = REPO / 'subjects/expat-566/input.xml'
    original = original_file.read_text()
    output = REPO / f'results/expat_566_structural_ddmin/{datetime.now():%Y%m%d_%H%M%S_%f}'
    output.mkdir(parents=True, exist_ok=False)
    temporary_file = REPO / 'temporary/expat_566_structural_candidate.xml'
    oracle = importlib.import_module('oracle_expat_566')
    recorder = Recorder(output, temporary_file, oracle.classify)
    print('Input:', original_file, flush=True)
    print('Results:', output, flush=True)
    minimal, iterations = reduce(original, recorder)
    minimal_file = output / 'minimal_failure.xml'
    minimal_file.write_text(minimal)
    summary = {
        'input_file': str(original_file), 'oracle_module': 'oracle_expat_566',
        'original_candidate_id': sha256(original), 'minimal_candidate_id': sha256(minimal),
        'original_size_characters': len(original), 'minimal_size_characters': len(minimal),
        'reduction_percentage': round(100 * (len(original)-len(minimal)) / len(original), 2),
        'iterations': iterations, 'generated_attempts': recorder.generated_attempts,
        'oracle_attempts': recorder.oracle_attempts, 'unique_candidates': len(recorder.cache),
        'passing_candidates': recorder.counts['PASS'],
        'failing_candidates': recorder.counts['FAIL'],
        'unresolved_candidates': recorder.counts['UNRESOLVED'],
        'invalid_xml_candidates': recorder.counts['INVALID_XML'],
        'minimal_file': str(minimal_file),
        'reducer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'reducer_file': str(Path(__file__).resolve()),
    }
    (output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
