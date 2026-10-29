"""Exploratory oracle for the TinyXML-2 #997 character-reference assertion.

The historical input is rejected by the fixed parser, so a FAIL here means
"the specific buggy assertion is reproduced", not a formal valid-input FAIL.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Literal


Outcome = Literal["PASS", "FAIL", "UNRESOLVED"]
ROOT = Path(__file__).resolve().parents[1]
SUBJECT = ROOT / "subjects" / "tinyxml2-character-ref"
BUGGY_PROGRAM = SUBJECT / "buggy_asan"
FIXED_PROGRAM = SUBJECT / "fixed_asan"
TIMEOUT_SECONDS = 2.0
ASSERTION_MARKERS = (
    "XMLUtil::GetCharacterRef",
    "digit == 0 || mult <= UINT_MAX / digit",
)


@dataclass(frozen=True)
class Run:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool


def run(program: Path, candidate: Path) -> Run:
    completed: subprocess.CompletedProcess[str]
    try:
        completed = subprocess.run(
            [str(program), str(candidate)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return Run(None, "", "", True)
    return Run(completed.returncode, completed.stdout, completed.stderr, False)


def classify(candidate: Path) -> Outcome:
    fixed = run(FIXED_PROGRAM, candidate)
    if fixed.timed_out or fixed.returncode not in (0, 2):
        return "UNRESOLVED"

    buggy = run(BUGGY_PROGRAM, candidate)
    if buggy.timed_out:
        return "UNRESOLVED"

    if buggy.returncode == -6 and all(
        marker in buggy.stderr for marker in ASSERTION_MARKERS
    ):
        return "FAIL"

    if (
        fixed.returncode == 0
        and buggy.returncode == 0
        and fixed.stdout.strip() == buggy.stdout.strip()
    ):
        return "PASS"

    return "UNRESOLVED"
