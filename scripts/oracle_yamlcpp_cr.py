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

SUBJECT_ROOT = (
    PROJECT_ROOT
    / "subjects"
    / "yamlcpp-cr-line-ending"
)

BUGGY_PROGRAM = SUBJECT_ROOT / "semantic_buggy"
FIXED_PROGRAM = SUBJECT_ROOT / "semantic_fixed"

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
            encoding="utf-8",
            errors="surrogateescape",
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
                errors="surrogateescape",
            )

        if isinstance(stderr, bytes):
            stderr = stderr.decode(
                "utf-8",
                errors="surrogateescape",
            )

        return ExecutionResult(
            return_code=None,
            stdout=stdout,
            stderr=stderr,
            timed_out=True,
        )


def normalize_output(output: str) -> str:
    #
    # Do NOT collapse internal whitespace here.
    # Scalar whitespace is part of the semantic result.
    #
    return output.strip()


def classify(
    yaml_file: Path,
) -> Outcome:

    yaml_file = yaml_file.resolve()

    #
    # The fixed revision defines the valid domain.
    #
    fixed = run_program(
        FIXED_PROGRAM,
        yaml_file,
    )

    if (
        fixed.timed_out
        or fixed.return_code != 0
    ):
        return "UNRESOLVED"

    fixed_output = normalize_output(
        fixed.stdout
    )

    if not fixed_output.startswith("TREE="):
        return "UNRESOLVED"

    buggy = run_program(
        BUGGY_PROGRAM,
        yaml_file,
    )

    if buggy.timed_out:
        return "UNRESOLVED"

    #
    # Fixed accepts but the buggy adjacent revision
    # rejects the same valid YAML.
    #
    if buggy.return_code != 0:
        return "FAIL"

    buggy_output = normalize_output(
        buggy.stdout
    )

    if not buggy_output.startswith("TREE="):
        return "UNRESOLVED"

    #
    # Same parsed YAML tree.
    #
    if buggy_output == fixed_output:
        return "PASS"

    #
    # Both accept, but produce different semantic trees.
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
    print("Fixed ee9c4d1")
    print(f"  rc     : {fixed.return_code}")
    print(f"  stdout : {fixed.stdout.strip()!r}")
    print(f"  stderr : {fixed.stderr.strip()!r}")

    print()
    print("Buggy b38ac5b")
    print(f"  rc     : {buggy.return_code}")
    print(f"  stdout : {buggy.stdout.strip()!r}")
    print(f"  stderr : {buggy.stderr.strip()!r}")


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
