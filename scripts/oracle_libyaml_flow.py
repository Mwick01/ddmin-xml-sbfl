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


PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

BUGGY_PROGRAM = (
    PROJECT_ROOT
    / "build"
    / "libyaml_flow"
    / "flow_buggy"
)

FIXED_PROGRAM = (
    PROJECT_ROOT
    / "build"
    / "libyaml_flow"
    / "flow_fixed"
)

TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class ExecutionResult:
    return_code: int | None
    stdout: str
    stderr: str
    timed_out: bool


def run_program(
    program: Path,
    yaml_file: Path,
) -> ExecutionResult:

    try:
        completed = subprocess.run(
            [
                str(program),
                str(yaml_file),
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


def normalize_output(
    output: str,
) -> str:
    return output.strip()


def classify(
    yaml_file: Path,
) -> Outcome:

    yaml_file = yaml_file.resolve()

    fixed = run_program(
        FIXED_PROGRAM,
        yaml_file,
    )

    #
    # The fixed revision defines the valid
    # input domain.
    #
    if (
        fixed.timed_out
        or fixed.return_code != 0
    ):
        return "UNRESOLVED"

    buggy = run_program(
        BUGGY_PROGRAM,
        yaml_file,
    )

    #
    # A timeout is treated conservatively as
    # unresolved rather than as evidence of
    # the historical bug.
    #
    if buggy.timed_out:
        return "UNRESOLVED"

    #
    # Fixed accepts but buggy rejects/crashes.
    #
    if buggy.return_code != 0:
        return "FAIL"

    fixed_output = normalize_output(
        fixed.stdout
    )

    buggy_output = normalize_output(
        buggy.stdout
    )

    #
    # Both accept and produce the same parser
    # event stream.
    #
    if buggy_output == fixed_output:
        return "PASS"

    #
    # Fixed accepts but the buggy parser emits
    # a different event sequence.
    #
    return "FAIL"


def print_details(
    yaml_file: Path,
) -> None:

    fixed = run_program(
        FIXED_PROGRAM,
        yaml_file,
    )

    buggy = run_program(
        BUGGY_PROGRAM,
        yaml_file,
    )

    print(f"Input   : {yaml_file}")
    print(f"Outcome : {classify(yaml_file)}")

    print()
    print("Fixed 840b65c")
    print(f"  rc     : {fixed.return_code}")
    print(f"  stdout : {fixed.stdout!r}")
    print(f"  stderr : {fixed.stderr!r}")

    print()
    print("Buggy 588eabf")
    print(f"  rc     : {buggy.return_code}")
    print(f"  stdout : {buggy.stdout!r}")
    print(f"  stderr : {buggy.stderr!r}")


def main() -> int:

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "yaml_file",
        type=Path,
    )

    parser.add_argument(
        "--details",
        action="store_true",
    )

    args = parser.parse_args()

    path = args.yaml_file.resolve()

    if args.details:
        print_details(path)
    else:
        print(classify(path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
