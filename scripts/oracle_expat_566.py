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
    / "expat_566"
    / "model_buggy"
)

FIXED_PROGRAM = (
    PROJECT_ROOT
    / "build"
    / "expat_566"
    / "model_fixed"
)

TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class ExecutionResult:
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool


def normalize_output(output: str) -> str:
    return " ".join(output.split())


def run_program(
    program: Path,
    xml_file: Path,
) -> ExecutionResult:

    try:
        completed = subprocess.run(
            [
                str(program),
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
    # The fixed revision defines the valid domain.
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
    # The candidate is valid and contains an observable
    # 'junk' content model in the fixed revision.
    #
    fixed_output = normalize_output(
        fixed.stdout
    )

    if not fixed_output.startswith("MODEL="):
        return "UNRESOLVED"

    buggy = run_program(
        BUGGY_PROGRAM,
        xml_file,
    )

    #
    # Keep the oracle fault-specific. A buggy-side parse
    # failure or missing model is not automatically treated
    # as evidence of Expat #566.
    #
    if (
        buggy.timed_out
        or buggy.return_code != 0
    ):
        return "UNRESOLVED"

    buggy_output = normalize_output(
        buggy.stdout
    )

    if not buggy_output.startswith("MODEL="):
        return "UNRESOLVED"

    #
    # Same valid content model -> PASS.
    #
    if buggy_output == fixed_output:
        return "PASS"

    #
    # Fixed produces a valid model while buggy produces a
    # different model -> semantic manifestation of #566.
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
    print("Fixed Expat 2.4.6")
    print(f"  rc     : {fixed.return_code}")
    print(f"  stdout : {fixed.stdout.strip()!r}")
    print(f"  stderr : {fixed.stderr.strip()!r}")

    print()
    print("Buggy Expat 2.4.5")
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

    args = parser.parse_args()

    path = args.xml_file.resolve()

    if args.details:
        print_details(path)
    else:
        print(classify(path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
