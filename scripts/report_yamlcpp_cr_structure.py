"""Export a matched character/structural yaml-cpp CR experiment report."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil
import statistics


ROOT = Path(__file__).resolve().parent.parent
MODES = ("afl", "aflsmart-mixed", "aflsmart-nonstack")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def matching_metadata(roots: dict[str, Path]) -> dict:
    found = {}
    for cohort, root in roots.items():
        metadata = [load(path) for path in sorted(root.rglob("metadata.json"))]
        keys = {(item["mode"], item["repetition"]) for item in metadata}
        modes = ("afl",) if cohort.endswith("_afl") else MODES[1:]
        expected = {(mode, rep) for mode in modes for rep in range(1, 6)}
        if len(metadata) != len(expected) or keys != expected:
            raise ValueError(f"{cohort}: missing or duplicate formal runs")
        for item in metadata:
            if item["git_dirty"] or item["duration_seconds"] != 300:
                raise ValueError(f"{cohort}: dirty or non-300-second run")
            if item["mode"] != "afl" and item["peach_chunk_structures"] <= 0:
                raise ValueError(f"{cohort}: missing Peach chunks")
        found[cohort] = metadata

    comparable = (
        "target_sha256", "docker_image", "oracle_module",
        "fault_line", "order_seed", "coverage_source", "coverage_binary",
    )
    for key in comparable:
        values = {item[key] for items in found.values() for item in items}
        if len(values) != 1:
            raise ValueError(f"Mismatched {key}: {values}")
    pits = {
        item["pit_sha256"]
        for items in found.values() for item in items
        if item["mode"] != "afl"
    }
    if len(pits) != 1:
        raise ValueError(f"Mismatched AFLsmart PIT hashes: {pits}")
    for arm in ("character", "structural"):
        seeds = {
            item["seed_corpus_sha256"]
            for cohort, items in found.items() if cohort.startswith(arm + "_")
            for item in items
        }
        if len(seeds) != 1:
            raise ValueError(f"{arm}: different seed corpus between modes")
    return {
        "shared": {
            **{key: next(iter(found.values()))[0][key] for key in comparable},
            "aflsmart_pit_sha256": next(iter(pits)),
        },
        "cohorts": {
            cohort: {
                "git_commit": items[0]["git_commit"],
                "seed_corpus_sha256": items[0]["seed_corpus_sha256"],
                "runs": len(items),
            }
            for cohort, items in found.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--structural-ddmin", type=Path, required=True)
    parser.add_argument("--structural-fuzz", type=Path, required=True)
    parser.add_argument("--structural-primary", type=Path, required=True)
    parser.add_argument("--structural-nonnull", type=Path, required=True)
    parser.add_argument("--structural-afl-fuzz", type=Path, required=True)
    parser.add_argument("--structural-afl-primary", type=Path, required=True)
    parser.add_argument("--structural-afl-nonnull", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/yamlcpp_cr_structure_comparison")
    args = parser.parse_args()

    char_ddmin = ROOT / "results/yamlcpp_cr_ddmin/20260924_192913_477043"
    char_afl_fuzz = ROOT / "results/yamlcpp_cr/formal_afl_300s"
    char_smart_fuzz = ROOT / "results/yamlcpp_cr/formal_aflsmart_300s"
    sources = {
        "character": {
            "ddmin": char_ddmin,
            "afl": (
                char_afl_fuzz,
                ROOT / "results/yamlcpp_cr/formal_afl_300s_evaluation",
                ROOT / "results/yamlcpp_cr/character_afl_300s_nonnull_recheck",
            ),
            "aflsmart": (
                char_smart_fuzz,
                ROOT / "results/yamlcpp_cr/formal_aflsmart_300s_evaluation",
                ROOT / "results/yamlcpp_cr/character_aflsmart_300s_nonnull_recheck",
            ),
        },
        "structural": {
            "ddmin": args.structural_ddmin,
            "afl": (
                args.structural_afl_fuzz,
                args.structural_afl_primary,
                args.structural_afl_nonnull,
            ),
            "aflsmart": (
                args.structural_fuzz,
                args.structural_primary,
                args.structural_nonnull,
            ),
        },
    }
    metadata = matching_metadata({
        f"{arm}_{kind}": paths[kind][0]
        for arm, paths in sources.items()
        for kind in ("afl", "aflsmart")
    })

    ddmin_rows = []
    primary_rows = []
    nonnull_rows = []
    comparison_rows = []
    for arm, paths in sources.items():
        ddmin = load(paths["ddmin"] / "summary.json")
        primary = load(paths["aflsmart"][1] / "summary.json")
        nonnull = load(paths["aflsmart"][2] / "summary.json")
        baseline = primary["baseline"]["jaccard"]
        nonnull_baseline = nonnull["baseline"]["jaccard"]
        ddmin_rows.append({
            "arm": arm,
            "original_bytes": ddmin["original_size_characters"],
            "minimal_bytes": ddmin["minimal_size_characters"],
            "reduction_percent": ddmin["reduction_percentage"],
            "evaluation_attempts": ddmin.get("generated_attempts", ddmin["oracle_attempts"]),
            "unique_candidates": ddmin["unique_candidates"],
            "classifier_calls": ddmin["oracle_attempts"] if arm == "structural" else ddmin["unique_candidates"],
            "PASS": ddmin["passing_candidates"],
            "FAIL": ddmin["failing_candidates"],
            "UNRESOLVED": ddmin["unresolved_candidates"],
            "INVALID_YAML": ddmin.get("invalid_yaml_candidates", 0),
            "baseline_jaccard_average_rank": baseline["average_rank"],
            "baseline_jaccard_EXAM_percent": baseline["exam_percentage"],
        })
        for mode in MODES:
            kind = "afl" if mode == "afl" else "aflsmart"
            primary = load(paths[kind][1] / "summary.json")
            nonnull = load(paths[kind][2] / "summary.json")
            if primary["baseline"]["jaccard"]["average_rank"] != baseline["average_rank"]:
                raise ValueError(f"{arm}: primary baseline differs between modes")
            if nonnull["baseline"]["jaccard"]["average_rank"] != nonnull_baseline["average_rank"]:
                raise ValueError(f"{arm}: non-null baseline differs between modes")
            null_by_key = {(r["mode"], r["repetition"]): r for r in nonnull["runs"]}
            for run in primary["runs"]:
                if run["mode"] != mode:
                    continue
                key = (mode, run["repetition"])
                if key not in null_by_key:
                    raise ValueError(f"Missing non-null run: {arm} {key}")
                null = null_by_key[key]
                primary_rows.append({
                    "arm": arm, "mode": mode, "repetition": key[1],
                    "added_PASS": run["added_PASS"], "added_FAIL": run["added_FAIL"],
                    "new_PASS_profiles": run["new_PASS_profiles"],
                    "new_FAIL_profiles": run["new_FAIL_profiles"],
                    "generated_UNRESOLVED": run["classification"].get("UNRESOLVED"),
                    "execs_done": int(run["fuzzer_stats"]["execs_done"]),
                    "peach_chunks": run["peach_chunk_structures"],
                    "havoc_smart_retained": run["mutation_counts"].get("havoc_smart_retained", 0),
                    "jaccard_average_rank": run["jaccard"]["average_rank"],
                    "jaccard_EXAM_percent": run["jaccard"]["exam_percentage"],
                    "ochiai_average_rank": run["ochiai"]["average_rank"],
                })
                nonnull_rows.append({
                    "arm": arm, "mode": mode, "repetition": key[1],
                    "retained_PASS": null["retained_PASS"],
                    "retained_FAIL": null["retained_FAIL"],
                    "removed_NULL_PASS": null["removed_TREE_NULL"]["PASS"],
                    "removed_NULL_FAIL": null["removed_TREE_NULL"]["FAIL"],
                    "NULL_PASS_avoids_fault": null["NULL_PASS_avoids_fault"],
                    "NONNULL_PASS_avoids_fault": null["NONNULL_PASS_avoids_fault"],
                    "jaccard_average_rank": null["jaccard"]["average_rank"],
                    "jaccard_EXAM_percent": null["jaccard"]["exam_percentage"],
                    "ochiai_average_rank": null["ochiai"]["average_rank"],
                })
            rows = [r for r in primary_rows if r["arm"] == arm and r["mode"] == mode]
            null_rows = [r for r in nonnull_rows if r["arm"] == arm and r["mode"] == mode]
            if len(rows) != 5 or len(null_rows) != 5:
                raise ValueError(f"Expected five evaluated runs: {arm} {mode}")
            mean = lambda group, column: statistics.mean(r[column] for r in group)
            comparison_rows.append({
                "arm": arm, "mode": mode, "repetitions": 5,
                "seed_count": ddmin["failing_candidates"],
                "baseline_average_rank": baseline["average_rank"],
                "mean_primary_average_rank": mean(rows, "jaccard_average_rank"),
                "mean_primary_EXAM_percent": mean(rows, "jaccard_EXAM_percent"),
                "primary_runs_better_than_baseline": sum(
                    r["jaccard_average_rank"] < baseline["average_rank"] for r in rows
                ),
                "nonnull_baseline_average_rank": nonnull_baseline["average_rank"],
                "mean_nonnull_average_rank": mean(null_rows, "jaccard_average_rank"),
                "nonnull_runs_better_than_baseline": sum(
                    r["jaccard_average_rank"] < nonnull_baseline["average_rank"]
                    for r in null_rows
                ),
                "mean_added_FAIL": mean(rows, "added_FAIL"),
                "mean_added_PASS": mean(rows, "added_PASS"),
                "mean_execs_done": mean(rows, "execs_done"),
                "mean_new_PASS_profiles": mean(rows, "new_PASS_profiles"),
                "mean_new_FAIL_profiles": mean(rows, "new_FAIL_profiles"),
                "mean_peach_chunks": mean(rows, "peach_chunks"),
                "mean_havoc_smart_retained": mean(rows, "havoc_smart_retained"),
                "NULL_PASS_avoids_fault_total": sum(
                    r["NULL_PASS_avoids_fault"] for r in null_rows
                ),
                "NONNULL_PASS_avoids_fault_total": sum(
                    r["NONNULL_PASS_avoids_fault"] for r in null_rows
                ),
            })

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "ddmin_comparison.csv", ddmin_rows)
    write_csv(output / "fuzz_comparison.csv", comparison_rows)
    write_csv(output / "primary_per_run.csv", primary_rows)
    write_csv(output / "nonnull_per_run.csv", nonnull_rows)
    (output / "provenance.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    shutil.copy2(args.structural_ddmin / "summary.json", output / "structural_ddmin_summary.json")
    shutil.copy2(args.structural_primary / "summary.json", output / "structural_primary_summary.json")
    shutil.copy2(args.structural_nonnull / "summary.json", output / "structural_nonnull_summary.json")
    shutil.copy2(args.structural_afl_primary / "summary.json", output / "structural_afl_primary_summary.json")
    shutil.copy2(args.structural_afl_nonnull / "summary.json", output / "structural_afl_nonnull_summary.json")
    print(f"Saved comparison to {output}")


if __name__ == "__main__":
    main()
