from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml


@dataclass(frozen=True)
class StructuralUnit:
    path: str
    kind: str
    start: int
    end: int
    text: str


def node_span(node: yaml.nodes.Node) -> tuple[int, int]:
    return (
        node.start_mark.index,
        node.end_mark.index,
    )


def collect_units(
    source: str,
    node: yaml.nodes.Node,
    path: str = "root",
) -> list[StructuralUnit]:
    """
    Collect syntactic YAML units that may later be considered
    by structure-aware delta debugging.

    For now this only discovers structure. It does NOT mutate
    the input.
    """

    units: list[StructuralUnit] = []

    start, end = node_span(node)

    units.append(
        StructuralUnit(
            path=path,
            kind=type(node).__name__,
            start=start,
            end=end,
            text=source[start:end],
        )
    )

    if isinstance(node, yaml.nodes.SequenceNode):
        for index, child in enumerate(node.value):
            units.extend(
                collect_units(
                    source,
                    child,
                    f"{path}.item[{index}]",
                )
            )

    elif isinstance(node, yaml.nodes.MappingNode):
        for index, (key, value) in enumerate(node.value):
            units.extend(
                collect_units(
                    source,
                    key,
                    f"{path}.entry[{index}].key",
                )
            )

            units.extend(
                collect_units(
                    source,
                    value,
                    f"{path}.entry[{index}].value",
                )
            )

    return units


def parse_structure(source: str) -> list[StructuralUnit]:
    root = yaml.compose(
        source,
        Loader=yaml.SafeLoader,
    )

    if root is None:
        raise ValueError("YAML input contains no document")

    return collect_units(source, root)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Inspect structural YAML units."
    )

    parser.add_argument(
        "input_file",
        type=Path,
    )

    arguments = parser.parse_args()

    source = arguments.input_file.read_text(
        encoding="utf-8",
    )

    units = parse_structure(source)

    print(
        f"Input: {arguments.input_file}"
    )

    print(
        f"Characters: {len(source)}"
    )

    print(
        f"Structural units: {len(units)}"
    )

    print()

    for index, unit in enumerate(units):
        print(
            f"{index:02d} "
            f"{unit.path:<45} "
            f"{unit.kind:<12} "
            f"[{unit.start}:{unit.end}] "
            f"{unit.text!r}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
