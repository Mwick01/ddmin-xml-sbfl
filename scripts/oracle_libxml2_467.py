from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import subprocess
from typing import Literal


Outcome = Literal[
    "PASS",
    "FAIL",
    "UNRESOLVED",
]


PROJECT_ROOT = Path(__file__).resolve().parent.parent

BUGGY_PROGRAM = (
    PROJECT_ROOT
    / "build"
    / "libxml2_467_buggy"
    / "xmllint"
)

FIXED_PROGRAM = (
    PROJECT_ROOT
    / "build"
    / "libxml2_467_fixed"
    / "xmllint"
)

TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class ExecutionResult:
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool


def normalize_output(output: str) -> str:
    return "\n".join(
        line.rstrip()
        for line in output.strip().splitlines()
    )


def run_program(
    program: Path,
    xml_file: Path,
) -> ExecutionResult:

    try:
        completed = subprocess.run(
            [
                str(program),
                "--nonet",
                "--dtdattr",
                "--format",
                str(xml_file),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
        )

        return ExecutionResult(
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            timed_out=False,
        )

    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""

        if isinstance(stdout, bytes):
            stdout = stdout.decode(
                "utf-8",
                errors="replace",
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                "utf-8",
                errors="replace",
            )

        return ExecutionResult(
            return_code=None,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )


def classify(xml_file: Path) -> Outcome:

    xml_file = xml_file.resolve()

    #
    # The fixed revision defines the valid input domain.
    #
    fixed = run_program(
        FIXED_PROGRAM,
        xml_file,
    )

    if (
        fixed.timed_out
        or fixed.return_code != 0
    ):
        return "UNRESOLVED"

    #
    # Only compare buggy behavior for inputs which the fixed
    # revision accepts successfully.
    #
    buggy = run_program(
        BUGGY_PROGRAM,
        xml_file,
    )

    if (
        buggy.timed_out
        or buggy.return_code != 0
    ):
        return "UNRESOLVED"

    fixed_output = normalize_output(
        fixed.stdout
    )

    buggy_output = normalize_output(
        buggy.stdout
    )

    #
    # Both historical revisions accept the XML and produce
    # the same resulting serialization.
    #
    if buggy_output == fixed_output:
        return "PASS"

    #
    # Both revisions accept the XML but produce different
    # namespace/default-attribute semantics.
    #
    return "FAIL"


def print_details(
    xml_file: Path,
) -> None:

    fixed = run_program(
        FIXED_PROGRAM,
        xml_file,
    )

    buggy = run_program(
        BUGGY_PROGRAM,
        xml_file,
    )

    print(f"Input   : {xml_file}")
    print(f"Outcome : {classify(xml_file)}")

    print()
    print("Fixed")
    print(f"  rc     : {fixed.return_code}")
    print(f"  stdout : {fixed.stdout.strip()!r}")
    print(f"  stderr : {fixed.stderr.strip()!r}")

    print()
    print("Buggy")
    print(f"  rc     : {buggy.return_code}")
    print(f"  stdout : {buggy.stdout.strip()!r}")
    print(f"  stderr : {buggy.stderr.strip()!r}")


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "xml_file",
        type=Path,
    )

    parser.add_argument(
        "--details",
        action="store_true",
    )

    arguments = parser.parse_args()

    xml_file = arguments.xml_file.resolve()

    if arguments.details:
        print_details(xml_file)
    else:
        print(classify(xml_file))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
