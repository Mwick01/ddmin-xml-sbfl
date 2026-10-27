"""Recompute yaml-cpp SBFL after excluding fixed-reference TREE=NULL tests."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import subprocess
import sys

from oracle_yamlcpp_cr import FIXED_PROGRAM, run_program


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "subjects/yamlcpp-cr-line-ending/buggy/src/stream.cpp"
FAULT_LINE = 265


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def fixed_tree_is_null(record: dict) -> bool:
    if record["classification"] == "PASS":
        return record["program_stdout"].strip() == "TREE=NULL"
    candidate = Path(record["candidate_file"])
    fixed = run_program(FIXED_PROGRAM, candidate)
    if fixed.timed_out or fixed.return_code != 0:
        raise RuntimeError(f"Fixed target no longer accepts {candidate}")
    return fixed.stdout.strip() == "TREE=NULL"


def filter_records(records: list[dict]) -> tuple[list[dict], dict]:
    retained = []
    removed = {"PASS": 0, "FAIL": 0}
    null_pass_avoids_fault = 0
    nonnull_pass_avoids_fault = 0
    for record in records:
        is_null = fixed_tree_is_null(record)
        if record["classification"] == "PASS" and FAULT_LINE not in record["covered_lines"]:
            if is_null:
                null_pass_avoids_fault += 1
            else:
                nonnull_pass_avoids_fault += 1
        if is_null:
            removed[record["classification"]] += 1
        else:
            retained.append(record)
    return retained, {
        "removed_TREE_NULL": removed,
        "NULL_PASS_avoids_fault": null_pass_avoids_fault,
        "NONNULL_PASS_avoids_fault": nonnull_pass_avoids_fault,
    }


def sbfl(records: list[dict], output: Path) -> dict:
    coverage = output / "coverage" / "coverage.jsonl"
    coverage.parent.mkdir(parents=True, exist_ok=True)
    coverage.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/sbfl.py"), str(output),
         "--source", str(SOURCE), "--fault-line", str(FAULT_LINE)],
        cwd=ROOT, check=True, stdout=subprocess.DEVNULL,
    )
    return json.loads((output / "sbfl/summary.json").read_text())


def compact_metric(summary: dict, metric: str) -> dict:
    item = summary[metric]
    return {
        "best_rank": item["best_rank"],
        "average_rank": item["average_rank"],
        "worst_rank": item["worst_rank"],
        "exam_percentage": item["exam_percentage_average"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--fuzz-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--duration", type=int, default=300)
    args = parser.parse_args()

    baseline, baseline_counts = filter_records(
        read_jsonl(args.baseline_run / "coverage/coverage.jsonl")
    )
    output_root = args.output_root.resolve()
    baseline_summary = sbfl(baseline, output_root / "baseline")
    rows = []
    runs = []
    for metadata_path in sorted(args.fuzz_root.rglob("metadata.json")):
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("subject") != "yamlcpp_cr" or metadata.get("duration_seconds") != args.duration:
            continue
        raw = read_jsonl(metadata_path.parent / "generated_eval/coverage/coverage.jsonl")
        generated, counts = filter_records(raw)
        summary = sbfl(
            baseline + generated,
            output_root / f"rep{int(metadata['repetition']):02d}" / metadata["mode"],
        )
        run = {
            "mode": metadata["mode"],
            "repetition": metadata["repetition"],
            "retained_PASS": sum(r["classification"] == "PASS" for r in generated),
            "retained_FAIL": sum(r["classification"] == "FAIL" for r in generated),
            **counts,
            "jaccard": compact_metric(summary, "jaccard"),
            "ochiai": compact_metric(summary, "ochiai"),
        }
        runs.append(run)
        rows.append({
            "mode": run["mode"],
            "repetition": run["repetition"],
            "retained_PASS": run["retained_PASS"],
            "retained_FAIL": run["retained_FAIL"],
            "removed_NULL_PASS": counts["removed_TREE_NULL"]["PASS"],
            "removed_NULL_FAIL": counts["removed_TREE_NULL"]["FAIL"],
            "NULL_PASS_avoids_fault": counts["NULL_PASS_avoids_fault"],
            "NONNULL_PASS_avoids_fault": counts["NONNULL_PASS_avoids_fault"],
            "jaccard_average_rank": run["jaccard"]["average_rank"],
            "jaccard_exam": run["jaccard"]["exam_percentage"],
            "ochiai_average_rank": run["ochiai"]["average_rank"],
            "ochiai_exam": run["ochiai"]["exam_percentage"],
        })

    if not rows:
        raise SystemExit(f"No matching runs in {args.fuzz_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / "per_run.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (output_root / "summary.json").write_text(
        json.dumps({
            "baseline_run": str(args.baseline_run.resolve()),
            "fuzz_root": str(args.fuzz_root.resolve()),
            "baseline_removed_TREE_NULL": baseline_counts["removed_TREE_NULL"],
            "baseline": {
                "PASS": baseline_summary["passing_tests"],
                "FAIL": baseline_summary["failing_tests"],
                "jaccard": compact_metric(baseline_summary, "jaccard"),
                "ochiai": compact_metric(baseline_summary, "ochiai"),
            },
            "runs": runs,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(f"Saved {len(rows)} non-null runs to {output_root}")


if __name__ == "__main__":
    main()
