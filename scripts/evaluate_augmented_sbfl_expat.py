#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import shutil
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODES = ("afl", "aflsmart-mixed", "aflsmart-nonstack")

SUBJECTS = {
    "expat_resume": {
        "source": (
            PROJECT_ROOT
            / "third_party"
            / "expat-2.2.5"
            / "expat"
            / "lib"
            / "xmlparse.c"
        ),
        "fault_line": 2912,
    },
    "libyaml_flow": {
        "source": (
            PROJECT_ROOT
            / "third_party"
            / "libyaml-588eabf"
            / "src"
            / "parser.c"
        ),
        "fault_line": 1062,
    },
    "yamlcpp_cr": {
        "source": (
            PROJECT_ROOT
            / "subjects"
            / "yamlcpp-cr-line-ending"
            / "buggy"
            / "src"
            / "stream.cpp"
        ),
        "fault_line": 265,
    },
}


def rel(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def tagged(records: list[dict], prefix: str) -> list[dict]:
    result = []
    for record in records:
        item = dict(record)
        item["test_id"] = f"{prefix}::{record.get('test_id', 'unknown')}"
        item["augmentation_source"] = prefix
        result.append(item)
    return result


def verify_compatible(baseline_records: list[dict], fuzz_records: list[dict]) -> None:
    baseline_lines = set(baseline_records[0]["executable_lines"])
    for record in fuzz_records:
        if set(record["executable_lines"]) != baseline_lines:
            raise RuntimeError(
                "Baseline and fuzz coverage use different executable-line sets."
            )


def profiles(records: list[dict]) -> dict[str, set[tuple[int, ...]]]:
    result = {"PASS": set(), "FAIL": set()}
    for record in records:
        outcome = record["classification"]
        if outcome in result:
            result[outcome].add(tuple(record["covered_lines"]))
    return result


def run_sbfl(run_directory: Path, source: Path, fault_line: int) -> dict:
    command = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "sbfl.py"),
        str(run_directory),
        "--source",
        rel(source),
        "--fault-line",
        str(fault_line),
    ]
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)
    summary_file = run_directory / "sbfl" / "summary.json"
    return json.loads(summary_file.read_text(encoding="utf-8"))


def metric_result(summary: dict, metric: str) -> dict:
    result = summary[metric]
    return {
        "score": result["first_fault_score"],
        "best_rank": result["best_rank"],
        "average_rank": result["average_rank"],
        "worst_rank": result["worst_rank"],
        "exam_percentage": result["exam_percentage_average"],
    }


def load_ranking(path: Path) -> dict[int, dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            int(row["line"]): row
            for row in csv.DictReader(handle)
        }


def tie_diagnostics(
    baseline_ranking: dict[int, dict],
    current_ranking: dict[int, dict],
    fault_line: int,
) -> dict:
    baseline_fault_score = float(baseline_ranking[fault_line]["score"])
    current_fault_score = float(current_ranking[fault_line]["score"])

    baseline_tie = {
        line
        for line, row in baseline_ranking.items()
        if abs(float(row["score"]) - baseline_fault_score) < 1e-12
    }

    current_tie = {
        line
        for line, row in current_ranking.items()
        if abs(float(row["score"]) - current_fault_score) < 1e-12
    }

    above = 0
    below = 0
    still_equal = 0

    for line in baseline_tie:
        score = float(current_ranking[line]["score"])
        if score > current_fault_score:
            above += 1
        elif score < current_fault_score:
            below += 1
        else:
            still_equal += 1

    return {
        "baseline_fault_tie_size": len(baseline_tie),
        "current_fault_tie_size": len(current_tie),
        "baseline_tied_above_fault": above,
        "baseline_tied_below_fault": below,
        "baseline_tied_still_equal": still_equal,
    }


def evaluate_baseline(
    baseline_records: list[dict],
    output_root: Path,
    source: Path,
    fault_line: int,
) -> tuple[dict, dict[str, dict[int, dict]]]:
    baseline_output = output_root / "baseline"
    if baseline_output.exists():
        shutil.rmtree(baseline_output)

    write_jsonl(
        baseline_output / "coverage" / "coverage.jsonl",
        tagged(baseline_records, "baseline"),
    )

    summary = run_sbfl(baseline_output, source, fault_line)

    rankings = {
        metric: load_ranking(
            baseline_output / "sbfl" / f"{metric}_ranking.csv"
        )
        for metric in ("jaccard", "ochiai")
    }

    baseline_profiles = profiles(baseline_records)

    result = {
        "passing_tests": summary["passing_tests"],
        "failing_tests": summary["failing_tests"],
        "total_tests": summary["total_tests"],
        "distinct_pass_profiles": len(baseline_profiles["PASS"]),
        "distinct_fail_profiles": len(baseline_profiles["FAIL"]),
        "jaccard": metric_result(summary, "jaccard"),
        "ochiai": metric_result(summary, "ochiai"),
    }

    for metric in ("jaccard", "ochiai"):
        result[metric]["tie"] = tie_diagnostics(
            rankings[metric],
            rankings[metric],
            fault_line,
        )

    return result, rankings


def evaluate_fuzz_run(
    metadata_file: Path,
    baseline_records: list[dict],
    baseline_profile_sets: dict[str, set[tuple[int, ...]]],
    baseline_rankings: dict[str, dict[int, dict]],
    output_root: Path,
    source: Path,
    fault_line: int,
) -> dict:
    run_directory = metadata_file.parent
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    mode = metadata["mode"]

    fuzz_coverage = run_directory / "generated_eval" / "coverage" / "coverage.jsonl"
    if not fuzz_coverage.is_file():
        raise RuntimeError(f"Missing fuzz coverage: {fuzz_coverage}")

    fuzz_records = read_jsonl(fuzz_coverage)
    verify_compatible(baseline_records, fuzz_records)

    fuzz_profile_sets = profiles(fuzz_records)
    new_pass_profiles = fuzz_profile_sets["PASS"] - baseline_profile_sets["PASS"]
    new_fail_profiles = fuzz_profile_sets["FAIL"] - baseline_profile_sets["FAIL"]

    combined_records = tagged(baseline_records, "baseline") + tagged(fuzz_records, "fuzz")

    output_directory = (
        output_root
        / f"rep{int(metadata['repetition']):02d}"
        / mode
    )

    if output_directory.exists():
        shutil.rmtree(output_directory)

    write_jsonl(
        output_directory / "coverage" / "coverage.jsonl",
        combined_records,
    )

    summary = run_sbfl(output_directory, source, fault_line)

    result = {
        "subject": metadata["subject"],
        "mode": mode,
        "repetition": metadata["repetition"],
        "duration_seconds": metadata["duration_seconds"],
        "git_commit": metadata.get("git_commit"),
        "baseline_tests": len(baseline_records),
        "added_fuzz_tests": len(fuzz_records),
        "added_PASS": sum(r["classification"] == "PASS" for r in fuzz_records),
        "added_FAIL": sum(r["classification"] == "FAIL" for r in fuzz_records),
        "distinct_PASS_profiles": len(fuzz_profile_sets["PASS"]),
        "distinct_FAIL_profiles": len(fuzz_profile_sets["FAIL"]),
        "new_PASS_profiles": len(new_pass_profiles),
        "new_FAIL_profiles": len(new_fail_profiles),
        "classification": metadata.get("classification", {}),
        "fuzzer_stats": metadata.get("fuzzer_stats", {}),
        "peach_chunk_structures": metadata.get("peach_chunk_structures", 0),
        "mutation_counts": metadata.get("mutation_counts", {}),
        "combined_PASS": summary["passing_tests"],
        "combined_FAIL": summary["failing_tests"],
        "combined_total": summary["total_tests"],
        "jaccard": metric_result(summary, "jaccard"),
        "ochiai": metric_result(summary, "ochiai"),
    }

    for metric in ("jaccard", "ochiai"):
        current_ranking = load_ranking(
            output_directory / "sbfl" / f"{metric}_ranking.csv"
        )
        result[metric]["tie"] = tie_diagnostics(
            baseline_rankings[metric],
            current_ranking,
            fault_line,
        )

    (output_directory / "augmentation_summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return result


def safe_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def numeric_run_row(result: dict) -> dict:
    classification = result.get("classification", {})
    stats = result.get("fuzzer_stats", {})
    mutation = result.get("mutation_counts", {})

    return {
        "repetition": result["repetition"],
        "added_PASS": result["added_PASS"],
        "added_FAIL": result["added_FAIL"],
        "generated_UNRESOLVED": classification.get("UNRESOLVED"),
        "usable_rate": classification.get("usable_rate"),
        "execs_done": safe_int(stats.get("execs_done")),
        "paths_total": safe_int(stats.get("paths_total")),
        "stability": safe_float(str(stats.get("stability", "")).rstrip("%")),
        "distinct_PASS_profiles": result["distinct_PASS_profiles"],
        "distinct_FAIL_profiles": result["distinct_FAIL_profiles"],
        "new_PASS_profiles": result["new_PASS_profiles"],
        "new_FAIL_profiles": result["new_FAIL_profiles"],
        "havoc_smart_retained": mutation.get("havoc_smart_retained"),
        "jaccard_best_rank": result["jaccard"]["best_rank"],
        "jaccard_average_rank": result["jaccard"]["average_rank"],
        "jaccard_worst_rank": result["jaccard"]["worst_rank"],
        "jaccard_exam_percentage": result["jaccard"]["exam_percentage"],
        "jaccard_tie_size": result["jaccard"]["tie"]["current_fault_tie_size"],
        "jaccard_baseline_tied_above": result["jaccard"]["tie"]["baseline_tied_above_fault"],
        "jaccard_baseline_tied_below": result["jaccard"]["tie"]["baseline_tied_below_fault"],
        "ochiai_best_rank": result["ochiai"]["best_rank"],
        "ochiai_average_rank": result["ochiai"]["average_rank"],
        "ochiai_worst_rank": result["ochiai"]["worst_rank"],
        "ochiai_exam_percentage": result["ochiai"]["exam_percentage"],
        "ochiai_tie_size": result["ochiai"]["tie"]["current_fault_tie_size"],
        "ochiai_baseline_tied_above": result["ochiai"]["tie"]["baseline_tied_above_fault"],
        "ochiai_baseline_tied_below": result["ochiai"]["tie"]["baseline_tied_below_fault"],
    }


def aggregate_values(values: list[float]) -> dict:
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def aggregate_results(results: list[dict]) -> dict:
    by_mode: dict[str, list[dict]] = defaultdict(list)
    for result in results:
        by_mode[result["mode"]].append(numeric_run_row(result))

    aggregate = {}
    for mode, rows in by_mode.items():
        metrics = {}
        keys = [key for key in rows[0] if key != "repetition"]
        for key in keys:
            values = [
                row[key]
                for row in rows
                if isinstance(row[key], (int, float))
            ]
            if values:
                metrics[key] = aggregate_values(values)
        aggregate[mode] = {
            "repetitions": len(rows),
            "metrics": metrics,
        }

    return aggregate


def write_per_run_csv(results: list[dict], path: Path) -> None:
    rows = []
    for result in results:
        row = {"mode": result["mode"], **numeric_run_row(result)}
        rows.append(row)

    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_aggregate_csv(aggregate: dict, path: Path) -> None:
    fields = ["mode", "metric", "n", "mean", "median", "min", "max", "stdev"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for mode in MODES:
            if mode not in aggregate:
                continue
            for metric, stats in aggregate[mode]["metrics"].items():
                writer.writerow({
                    "mode": mode,
                    "metric": metric,
                    **stats,
                })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subject", choices=sorted(SUBJECTS), default="expat_resume")
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--fuzz-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--fault-line", type=int, default=None)
    arguments = parser.parse_args()

    subject = SUBJECTS[arguments.subject]
    source = subject["source"]
    fault_line = arguments.fault_line or subject["fault_line"]

    baseline_run = arguments.baseline_run.resolve()
    fuzz_root = arguments.fuzz_root.resolve()
    output_root = (
        arguments.output_root.resolve()
        if arguments.output_root
        else PROJECT_ROOT / "results" / arguments.subject / f"formal_{arguments.duration}s_analysis"
    )
    output_root.mkdir(parents=True, exist_ok=True)

    baseline_coverage = baseline_run / "coverage" / "coverage.jsonl"
    if not baseline_coverage.is_file():
        raise SystemExit(f"Baseline coverage not found: {baseline_coverage}")

    baseline_records = read_jsonl(baseline_coverage)
    if not baseline_records:
        raise SystemExit("Baseline coverage is empty.")

    baseline_profile_sets = profiles(baseline_records)

    baseline_summary, baseline_rankings = evaluate_baseline(
        baseline_records,
        output_root,
        source,
        fault_line,
    )

    metadata_files = []
    for metadata_file in sorted(fuzz_root.rglob("metadata.json")):
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))

        if metadata.get("subject") != arguments.subject:
            continue
        if metadata.get("duration_seconds") != arguments.duration:
            continue
        if metadata.get("mode") not in MODES:
            continue

        metadata_files.append(metadata_file)

    if not metadata_files:
        raise SystemExit(f"No matching fuzz runs found under {fuzz_root}")

    results = []
    for metadata_file in metadata_files:
        result = evaluate_fuzz_run(
            metadata_file,
            baseline_records,
            baseline_profile_sets,
            baseline_rankings,
            output_root,
            source,
            fault_line,
        )
        results.append(result)

        print(
            f"{result['mode']:<22} "
            f"r{result['repetition']} "
            f"+PASS={result['added_PASS']:<3} "
            f"+FAIL={result['added_FAIL']:<3} "
            f"newFAILprof={result['new_FAIL_profiles']:<3} "
            f"Javg={result['jaccard']['average_rank']:<7.1f} "
            f"JEXAM={result['jaccard']['exam_percentage']:<6.2f}% "
            f"above={result['jaccard']['tie']['baseline_tied_above_fault']:<3} "
            f"below={result['jaccard']['tie']['baseline_tied_below_fault']:<3}"
        )

    aggregate = aggregate_results(results)

    per_run_csv = output_root / "per_run.csv"
    aggregate_csv = output_root / "aggregate.csv"
    summary_json = output_root / "summary.json"

    write_per_run_csv(results, per_run_csv)
    write_aggregate_csv(aggregate, aggregate_csv)

    summary_json.write_text(
        json.dumps({
            "subject": arguments.subject,
            "baseline_run": str(baseline_run),
            "fuzz_root": str(fuzz_root),
            "duration_seconds": arguments.duration,
            "fault_line": fault_line,
            "baseline": baseline_summary,
            "runs": results,
            "aggregate": aggregate,
        }, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print("\nSaved")
    print(f"Per-run CSV : {per_run_csv}")
    print(f"Aggregate   : {aggregate_csv}")
    print(f"JSON        : {summary_json}")


if __name__ == "__main__":
    main()