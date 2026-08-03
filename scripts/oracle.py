from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import subprocess
import sys
from typing import Literal


Outcome = Literal["PASS", "FAIL", "UNRESOLVED"]


@dataclass(frozen=True)
class ExecutionResult:
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool


PROJECT_ROOT = Path(__file__).resolve().parent.parent

FIXED_PROGRAM = PROJECT_ROOT / "build" / "invoice_fixed"
BUGGY_PROGRAM = PROJECT_ROOT / "build" / "invoice_buggy"

TIMEOUT_SECONDS = 2.0


def normalize_output(output: str) -> str:
    """
    Remove differences in spacing and line endings that do not affect
    the program's semantic result.
    """
    return " ".join(output.split())


def run_program(
    program: Path,
    xml_file: Path,
    timeout_seconds: float = TIMEOUT_SECONDS,
) -> ExecutionResult:
    """
    Run one program against one XML input.
    """

    if not program.is_file():
        raise FileNotFoundError(f"Program not found: {program}")

    try:
        completed = subprocess.run(
            [str(program), str(xml_file)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
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
            stdout = stdout.decode("utf-8", errors="replace")

        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")

        return ExecutionResult(
            return_code=None,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )


def classify(xml_file: Path) -> Outcome:
    """
    Classify an XML input.

    PASS:
        Both programs accept the input and produce the same output.

    FAIL:
        Both programs accept the input but produce different outputs.

    UNRESOLVED:
        The fixed program rejects the input, either program times out,
        or the buggy program terminates abnormally.
    """

    xml_file = xml_file.resolve()

    if not xml_file.is_file():
        raise FileNotFoundError(f"XML file not found: {xml_file}")

    fixed_result = run_program(FIXED_PROGRAM, xml_file)
    buggy_result = run_program(BUGGY_PROGRAM, xml_file)

    if fixed_result.timed_out or buggy_result.timed_out:
        return "UNRESOLVED"

    # The fixed program defines the valid input domain.
    if fixed_result.return_code != 0:
        return "UNRESOLVED"

    # For this experiment, we are studying a functional-output fault,
    # not a crash fault.
    if buggy_result.return_code != 0:
        return "UNRESOLVED"

    fixed_output = normalize_output(fixed_result.stdout)
    buggy_output = normalize_output(buggy_result.stdout)

    if fixed_output == buggy_output:
        return "PASS"

    return "FAIL"


def print_detailed_result(xml_file: Path) -> Outcome:
    """
    Print execution details for debugging and validation.
    """

    fixed_result = run_program(FIXED_PROGRAM, xml_file)
    buggy_result = run_program(BUGGY_PROGRAM, xml_file)

    outcome = classify(xml_file)

    print(f"Input: {xml_file}")
    print(f"Outcome: {outcome}")
    print()

    print("Fixed program:")
    print(f"  Exit code: {fixed_result.return_code}")
    print(f"  Timed out: {fixed_result.timed_out}")
    print(f"  Stdout: {fixed_result.stdout.strip()!r}")
    print(f"  Stderr: {fixed_result.stderr.strip()!r}")
    print()

    print("Buggy program:")
    print(f"  Exit code: {buggy_result.return_code}")
    print(f"  Timed out: {buggy_result.timed_out}")
    print(f"  Stdout: {buggy_result.stdout.strip()!r}")
    print(f"  Stderr: {buggy_result.stderr.strip()!r}")

    return outcome


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Classify an XML input as PASS, FAIL, or UNRESOLVED."
    )

    parser.add_argument(
        "xml_file",
        type=Path,
        help="Path to the XML input file.",
    )

    parser.add_argument(
        "--details",
        action="store_true",
        help="Show outputs, exit codes, and timeout information.",
    )

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        xml_file = arguments.xml_file.resolve()

        if arguments.details:
            print_detailed_result(xml_file)
        else:
            print(classify(xml_file))

        return 0

    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2

    except OSError as error:
        print(f"Execution error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())