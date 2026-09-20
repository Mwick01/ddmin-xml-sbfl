#!/usr/bin/env python3

from __future__ import annotations


import argparse
import hashlib
import importlib
import json
import os
import shlex
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

IMAGE = "ddmin-aflsmart"
MODES = ("afl", "aflsmart-mixed", "aflsmart-nonstack")


@dataclass(frozen=True)
class Subject:
    name: str
    seed_directory: Path
    pit_file: Path
    target: Path
    oracle_module: str
    coverage_source: Path
    coverage_binary: Path
    coverage_object: Path
    fault_line: int


SUBJECTS = {
    "expat_resume": Subject(
        name="expat_resume",
        seed_directory=PROJECT_ROOT / "aflsmart" / "expat_resume_rich_seeds",
        pit_file=PROJECT_ROOT / "aflsmart" / "expat_resume.xml",
        target=PROJECT_ROOT / "build" / "aflsmart" / "expat_resume" / "resume_buggy",
        oracle_module="oracle_expat_resume",
        coverage_source=PROJECT_ROOT / "third_party" / "expat-2.2.5" / "expat" / "lib" / "xmlparse.c",
        coverage_binary=PROJECT_ROOT / "build" / "expat_resume" / "resume_buggy_cov",
        coverage_object=PROJECT_ROOT / "build" / "expat-2.2.5-cov" / "CMakeFiles" / "expat.dir" / "lib" / "xmlparse.c.o",
        fault_line=2912,
    ),
}


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def corpus_sha256(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in directory.iterdir() if p.is_file()):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def git_dirty() -> bool:
    return bool(
        subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )


def load_oracle(module_name: str):
    module = importlib.import_module(module_name)
    return module.classify


def baseline_hashes(baseline_run: Path) -> set[str]:
    hashes: set[str] = set()
    for dirname in ("pass", "fail"):
        directory = baseline_run / dirname
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if path.is_file():
                hashes.add(sha256_file(path))
    return hashes


def build_afl_arguments(subject: Subject, mode: str, raw_directory: Path) -> list[str]:
    arguments = [
        "/aflsmart/afl-fuzz",
        "-m", "200",
        "-d",
        "-i", rel(subject.seed_directory),
        "-o", rel(raw_directory),
    ]

    if mode.startswith("aflsmart"):
        arguments += ["-w", "peach", "-g", rel(subject.pit_file)]

    if mode == "aflsmart-mixed":
        arguments.append("-h")

    arguments += ["--", f"./{rel(subject.target)}", "@@"]
    return arguments


def run_fuzzer(subject: Subject, mode: str, duration: int, raw_directory: Path) -> list[str]:
    afl_arguments = build_afl_arguments(subject, mode, raw_directory)
    inner = ["timeout", "-s", "INT", f"{duration}s", *afl_arguments]

    command = [
        "docker", "run", "--rm",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "-e", "HOME=/tmp",
        "-e", "TMPDIR=/tmp",
        "-e", "AFL_PATH=/aflsmart",
        "-e", "AFL_SKIP_CPUFREQ=1",
        "-e", "AFL_NO_AFFINITY=1",
        "-e", "AFL_NO_UI=1",
        "-v", f"{PROJECT_ROOT}:/work",
        "-w", "/work",
        IMAGE,
        "bash", "-lc",
        'export PATH="/aflsmart/peach-3.0.202-source/output/linux_x86_64_release/bin:/aflsmart:$PATH"; '
        + shlex.join(inner),
    ]

    print(f"\n=== {mode} | {duration}s | {raw_directory} ===\n", flush=True)
    result = subprocess.run(command, cwd=PROJECT_ROOT)

    if result.returncode not in {0, 124}:
        raise RuntimeError(f"Fuzzer exited unexpectedly: {result.returncode}")

    return afl_arguments


def classify_generated_queue(
    subject: Subject,
    raw_directory: Path,
    run_directory: Path,
    baseline_digest_set: set[str],
) -> dict:
    classify = load_oracle(subject.oracle_module)

    queue_directory = raw_directory / "queue"
    generated_eval = run_directory / "generated_eval"

    if generated_eval.exists():
        shutil.rmtree(generated_eval)

    pass_dir = generated_eval / "pass"
    fail_dir = generated_eval / "fail"
    pass_dir.mkdir(parents=True)
    fail_dir.mkdir(parents=True)

    queue_files = sorted(
        path for path in queue_directory.iterdir()
        if path.is_file() and path.name.startswith("id:")
    )

    counts = Counter()
    records = []
    seen: set[str] = set()
    seed_entries = 0

    for path in queue_files:
        if ",orig:" in path.name:
            seed_entries += 1
            records.append({
                "test_id": path.name,
                "kind": "seed",
                "size_bytes": path.stat().st_size,
            })
            continue

        digest = sha256_file(path)

        if digest in baseline_digest_set:
            counts["duplicate_baseline"] += 1
            records.append({
                "test_id": path.name,
                "kind": "generated",
                "sha256": digest,
                "duplicate_baseline": True,
                "size_bytes": path.stat().st_size,
            })
            continue

        if digest in seen:
            counts["duplicate_generated"] += 1
            records.append({
                "test_id": path.name,
                "kind": "generated",
                "sha256": digest,
                "duplicate_generated": True,
                "size_bytes": path.stat().st_size,
            })
            continue

        seen.add(digest)
        outcome = classify(path)
        counts[outcome] += 1

        if outcome in {"PASS", "FAIL"}:
            destination = pass_dir if outcome == "PASS" else fail_dir
            shutil.copy2(path, destination / f"{digest[:12]}_{path.name}")

        records.append({
            "test_id": path.name,
            "kind": "generated",
            "sha256": digest,
            "classification": outcome,
            "duplicate_generated": False,
            "duplicate_baseline": False,
            "size_bytes": path.stat().st_size,
        })

    with (run_directory / "classification.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")

    evaluated = counts["PASS"] + counts["FAIL"] + counts["UNRESOLVED"]
    usable = counts["PASS"] + counts["FAIL"]

    return {
        "raw_queue_entries": len(queue_files),
        "seed_entries": seed_entries,
        "generated_queue_entries": len(queue_files) - seed_entries,
        "unique_generated_evaluated": evaluated,
        "PASS": counts["PASS"],
        "FAIL": counts["FAIL"],
        "UNRESOLVED": counts["UNRESOLVED"],
        "duplicate_generated": counts["duplicate_generated"],
        "duplicate_baseline": counts["duplicate_baseline"],
        "usable": usable,
        "usable_rate": usable / evaluated if evaluated else 0.0,
    }


def read_fuzzer_stats(raw_directory: Path) -> dict:
    stats_file = raw_directory / "fuzzer_stats"
    if not stats_file.exists():
        return {}
    stats = {}
    for line in stats_file.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            stats[key.strip()] = value.strip()
    return stats


def mutation_counts(raw_directory: Path) -> dict:
    queue = raw_directory / "queue"
    names = [p.name for p in queue.iterdir() if p.is_file()]
    return {
        "havoc_smart_retained": sum("op:havoc-smart" in name for name in names),
        "havoc_retained": sum("op:havoc," in name for name in names),
        "splice_retained": sum("op:splice" in name for name in names),
    }


def chunk_count(raw_directory: Path) -> int:
    directory = raw_directory / "chunks"
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.glob("*.chunks") if path.is_file())


def collect_coverage(subject: Subject, run_directory: Path) -> dict:
    generated_eval = run_directory / "generated_eval"
    pass_count = sum(1 for p in (generated_eval / "pass").iterdir() if p.is_file())
    fail_count = sum(1 for p in (generated_eval / "fail").iterdir() if p.is_file())

    if pass_count + fail_count == 0:
        return {
            "status": "skipped",
            "reason": "No generated PASS/FAIL tests remained after deduplication.",
            "pass_tests": pass_count,
            "fail_tests": fail_count,
        }

    collector = PROJECT_ROOT / "scripts" / "collect_coverage.py"
    subprocess.run(
        [
            sys.executable,
            str(collector),
            str(generated_eval),
            "--oracle-module", subject.oracle_module,
            "--source", rel(subject.coverage_source),
            "--binary", rel(subject.coverage_binary),
            "--object", rel(subject.coverage_object),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )

    coverage_file = generated_eval / "coverage" / "coverage.jsonl"
    records = [
        json.loads(line)
        for line in coverage_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    result = {"status": "completed"}
    for outcome in ("PASS", "FAIL"):
        selected = [r for r in records if r["classification"] == outcome]
        profiles = defaultdict(list)
        for record in selected:
            profiles[tuple(record["covered_lines"])].append(record["test_id"])
        key = outcome.lower()
        result[f"{key}_tests"] = len(selected)
        result[f"distinct_{key}_profiles"] = len(profiles)
        result[f"{key}_profile_test_counts"] = sorted(len(v) for v in profiles.values())
        result[f"{key}_profile_line_counts"] = sorted(len(k) for k in profiles)

    summary_file = generated_eval / "coverage" / "summary.json"
    if summary_file.exists():
        result["collector_summary"] = json.loads(summary_file.read_text(encoding="utf-8"))

    return result


def validate_subject(subject: Subject, baseline_run: Path) -> None:
    required = [
        subject.seed_directory,
        subject.pit_file,
        subject.target,
        subject.coverage_source,
        subject.coverage_binary,
        subject.coverage_object,
        baseline_run / "coverage" / "coverage.jsonl",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        text = "\n".join(str(path) for path in missing)
        raise SystemExit(f"Missing required paths:\n{text}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", choices=sorted(SUBJECTS), default="expat_resume")
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=MODES,
        default=list(MODES),
    )
    parser.add_argument(
        "--results-root",
        type=Path,
        default=None,
        help="Default: results/<subject>/formal_<duration>s",
    )
    parser.add_argument("--allow-dirty", action="store_true")
    arguments = parser.parse_args()

    subject = SUBJECTS[arguments.subject]
    baseline_run = arguments.baseline_run.resolve()
    validate_subject(subject, baseline_run)

    dirty = git_dirty()
    if dirty and not arguments.allow_dirty:
        raise SystemExit(
            "Git working tree is dirty. Commit the experiment scripts/config first, "
            "or rerun with --allow-dirty for a non-formal diagnostic run."
        )

    results_root = (
        arguments.results_root.resolve()
        if arguments.results_root
        else PROJECT_ROOT / "results" / subject.name / f"formal_{arguments.duration}s"
    )
    results_root.mkdir(parents=True, exist_ok=True)

    baseline_digest_set = baseline_hashes(baseline_run)
    commit = git_commit()

    for repetition in range(1, arguments.repetitions + 1):
        rep_directory = results_root / f"rep{repetition:02d}"
        rep_directory.mkdir(parents=True, exist_ok=True)

        for mode in arguments.modes:
            run_directory = rep_directory / mode
            raw_directory = run_directory / "raw"

            if run_directory.exists() and any(run_directory.iterdir()):
                raise SystemExit(
                    f"Refusing to overwrite existing run: {run_directory}\n"
                    "Use a new results root if you intentionally want another experiment."
                )

            run_directory.mkdir(parents=True, exist_ok=True)

            afl_arguments = run_fuzzer(
                subject,
                mode,
                arguments.duration,
                raw_directory,
            )

            classification = classify_generated_queue(
                subject,
                raw_directory,
                run_directory,
                baseline_digest_set,
            )

            coverage = collect_coverage(subject, run_directory)
            stats = read_fuzzer_stats(raw_directory)
            mutations = mutation_counts(raw_directory)
            chunks = chunk_count(raw_directory)

            if mode.startswith("aflsmart") and chunks == 0:
                raise RuntimeError(
                    f"{mode} produced no Peach chunk structures; "
                    "do not treat this run as structure-aware."
                )

            metadata = {
                "subject": subject.name,
                "mode": mode,
                "repetition": repetition,
                "duration_seconds": arguments.duration,
                "git_commit": commit,
                "git_dirty": dirty,
                "docker_image": IMAGE,
                "baseline_run": str(baseline_run),
                "fault_line": subject.fault_line,
                "seed_directory": rel(subject.seed_directory),
                "seed_corpus_sha256": corpus_sha256(subject.seed_directory),
                "target": rel(subject.target),
                "target_sha256": sha256_file(subject.target),
                "pit": rel(subject.pit_file) if mode.startswith("aflsmart") else None,
                "pit_sha256": sha256_file(subject.pit_file) if mode.startswith("aflsmart") else None,
                "oracle_module": subject.oracle_module,
                "coverage_source": rel(subject.coverage_source),
                "coverage_binary": rel(subject.coverage_binary),
                "coverage_object": rel(subject.coverage_object),
                "afl_arguments": afl_arguments,
                "classification": classification,
                "coverage": coverage,
                "fuzzer_stats": stats,
                "peach_chunk_structures": chunks,
                "mutation_counts": mutations,
            }

            (run_directory / "metadata.json").write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            print("\nRun complete")
            print(json.dumps({
                "rep": repetition,
                "mode": mode,
                "classification": classification,
                "chunks": chunks,
                "mutations": mutations,
            }, indent=2))


if __name__ == "__main__":
    main()