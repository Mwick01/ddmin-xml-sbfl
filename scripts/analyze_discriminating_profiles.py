#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MODES = (
    "afl",
    "aflsmart-mixed",
    "aflsmart-nonstack",
)

METRICS = (
    "jaccard",
    "ochiai",
)

TOLERANCE = 1e-12


SUBJECTS = {
    "expat_resume": {
        "fault_line": 2912,
        "duration": 300,
        "baseline_run": (
            PROJECT_ROOT
            / "results"
            / "expat_resume"
            / "ddmin_rich_upstream_runs"
            / "20260831_215147_470087"
        ),
        "fuzz_root": (
            PROJECT_ROOT
            / "results"
            / "expat_resume"
            / "formal_300s"
        ),
        "analysis_root": (
            PROJECT_ROOT
            / "results"
            / "expat_resume"
            / "formal_300s_analysis"
        ),
    },
    "libyaml_flow": {
        "fault_line": 1062,
        "duration": 300,
        "baseline_run": (
            PROJECT_ROOT
            / "results"
            / "libyaml_flow"
            / "ddmin_rich_runs"
            / "20260921_232140_207481"
        ),
        "fuzz_root": (
            PROJECT_ROOT
            / "results"
            / "libyaml_flow"
            / "formal_300s"
        ),
        "analysis_root": (
            PROJECT_ROOT
            / "results"
            / "libyaml_flow"
            / "formal_300s_analysis"
        ),
    },
}


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_ranking(path: Path) -> dict[int, dict]:
    with path.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        return {
            int(row["line"]): row
            for row in csv.DictReader(handle)
        }


def write_csv(
    path: Path,
    rows: list[dict],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        path.write_text(
            "",
            encoding="utf-8",
        )
        return

    fields = list(rows[0].keys())

    with path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fields,
        )
        writer.writeheader()
        writer.writerows(rows)


def safe_div(
    numerator: float,
    denominator: float,
) -> float:
    if denominator == 0:
        return 0.0

    return numerator / denominator


def baseline_profile_keys(
    records: list[dict],
) -> set[tuple[str, tuple[int, ...]]]:
    return {
        (
            record["classification"],
            tuple(record["covered_lines"]),
        )
        for record in records
    }


def unique_new_profiles(
    records: list[dict],
    baseline_profiles: set[
        tuple[str, tuple[int, ...]]
    ],
) -> list[
    tuple[str, frozenset[int]]
]:
    profiles = {}

    for record in records:
        key = (
            record["classification"],
            tuple(record["covered_lines"]),
        )

        if key in baseline_profiles:
            continue

        profiles[key] = (
            record["classification"],
            frozenset(
                record["covered_lines"]
            ),
        )

    return list(
        profiles.values()
    )


def generated_test_items(
    records: list[dict],
) -> list[
    tuple[str, frozenset[int]]
]:
    return [
        (
            record["classification"],
            frozenset(
                record["covered_lines"]
            ),
        )
        for record in records
    ]


def direction_summary(
    items: list[
        tuple[str, frozenset[int]]
    ],
    competitors: set[int],
    fault_line: int,
) -> tuple[dict, dict[int, dict]]:
    """
    Compare the fault against each baseline-tied competitor.

    Helpful discrimination:
      PASS: competitor covered, fault not covered
      FAIL: fault covered, competitor not covered

    Harmful discrimination:
      PASS: fault covered, competitor not covered
      FAIL: competitor covered, fault not covered
    """

    per_competitor = {
        line: {
            "helpful_PASS": 0,
            "helpful_FAIL": 0,
            "harmful_PASS": 0,
            "harmful_FAIL": 0,
        }
        for line in competitors
    }

    helpful_pairs = 0
    harmful_pairs = 0

    helpful_pass_pairs = 0
    helpful_fail_pairs = 0

    harmful_pass_pairs = 0
    harmful_fail_pairs = 0

    helpful_items = 0
    harmful_items = 0
    mixed_items = 0
    discriminating_items = 0

    for outcome, covered in items:

        fault_covered = (
            fault_line in covered
        )

        has_helpful = False
        has_harmful = False

        for competitor in competitors:

            competitor_covered = (
                competitor in covered
            )

            if (
                fault_covered
                == competitor_covered
            ):
                continue

            helpful = (
                (
                    outcome == "PASS"
                    and not fault_covered
                    and competitor_covered
                )
                or
                (
                    outcome == "FAIL"
                    and fault_covered
                    and not competitor_covered
                )
            )

            if helpful:
                helpful_pairs += 1
                has_helpful = True

                if outcome == "PASS":
                    helpful_pass_pairs += 1
                    per_competitor[
                        competitor
                    ]["helpful_PASS"] += 1
                else:
                    helpful_fail_pairs += 1
                    per_competitor[
                        competitor
                    ]["helpful_FAIL"] += 1

            else:
                harmful_pairs += 1
                has_harmful = True

                if outcome == "PASS":
                    harmful_pass_pairs += 1
                    per_competitor[
                        competitor
                    ]["harmful_PASS"] += 1
                else:
                    harmful_fail_pairs += 1
                    per_competitor[
                        competitor
                    ]["harmful_FAIL"] += 1

        if has_helpful or has_harmful:
            discriminating_items += 1

        if has_helpful:
            helpful_items += 1

        if has_harmful:
            harmful_items += 1

        if has_helpful and has_harmful:
            mixed_items += 1

    possible_pairs = (
        len(items)
        * len(competitors)
    )

    competitors_with_helpful = 0
    competitors_with_harmful = 0

    competitors_net_helpful = 0
    competitors_net_harmful = 0
    competitors_net_zero = 0

    for line in competitors:

        counts = per_competitor[line]

        helpful_count = (
            counts["helpful_PASS"]
            + counts["helpful_FAIL"]
        )

        harmful_count = (
            counts["harmful_PASS"]
            + counts["harmful_FAIL"]
        )

        counts["helpful_total"] = (
            helpful_count
        )

        counts["harmful_total"] = (
            harmful_count
        )

        counts["net_helpful"] = (
            helpful_count
            - harmful_count
        )

        if helpful_count:
            competitors_with_helpful += 1

        if harmful_count:
            competitors_with_harmful += 1

        if helpful_count > harmful_count:
            competitors_net_helpful += 1
        elif harmful_count > helpful_count:
            competitors_net_harmful += 1
        else:
            competitors_net_zero += 1

    return {
        "items": len(items),

        "discriminating_items":
            discriminating_items,

        "helpful_items":
            helpful_items,

        "harmful_items":
            harmful_items,

        "mixed_direction_items":
            mixed_items,

        "helpful_pairs":
            helpful_pairs,

        "harmful_pairs":
            harmful_pairs,

        "net_pairs":
            helpful_pairs
            - harmful_pairs,

        "helpful_PASS_pairs":
            helpful_pass_pairs,

        "helpful_FAIL_pairs":
            helpful_fail_pairs,

        "harmful_PASS_pairs":
            harmful_pass_pairs,

        "harmful_FAIL_pairs":
            harmful_fail_pairs,

        "discriminating_density":
            safe_div(
                helpful_pairs
                + harmful_pairs,
                possible_pairs,
            ),

        "helpful_density":
            safe_div(
                helpful_pairs,
                possible_pairs,
            ),

        "harmful_density":
            safe_div(
                harmful_pairs,
                possible_pairs,
            ),

        "net_density":
            safe_div(
                helpful_pairs
                - harmful_pairs,
                possible_pairs,
            ),

        "helpful_PASS_share":
            safe_div(
                helpful_pass_pairs,
                helpful_pairs,
            ),

        "helpful_FAIL_share":
            safe_div(
                helpful_fail_pairs,
                helpful_pairs,
            ),

        "competitors_with_helpful":
            competitors_with_helpful,

        "competitors_with_harmful":
            competitors_with_harmful,

        "competitors_net_helpful":
            competitors_net_helpful,

        "competitors_net_harmful":
            competitors_net_harmful,

        "competitors_net_zero":
            competitors_net_zero,

        "competitors_net_helpful_fraction":
            safe_div(
                competitors_net_helpful,
                len(competitors),
            ),

        "competitors_net_harmful_fraction":
            safe_div(
                competitors_net_harmful,
                len(competitors),
            ),
    }, per_competitor


def tied_competitors(
    ranking: dict[int, dict],
    fault_line: int,
) -> set[int]:

    fault_score = float(
        ranking[fault_line]["score"]
    )

    return {
        line
        for line, row in ranking.items()
        if (
            line != fault_line
            and abs(
                float(row["score"])
                - fault_score
            )
            < TOLERANCE
        )
    }


def movement(
    current_ranking: dict[int, dict],
    fault_line: int,
    competitor: int,
) -> str:

    fault_score = float(
        current_ranking[
            fault_line
        ]["score"]
    )

    competitor_score = float(
        current_ranking[
            competitor
        ]["score"]
    )

    if (
        competitor_score
        > fault_score
        + TOLERANCE
    ):
        return "above"

    if (
        competitor_score
        < fault_score
        - TOLERANCE
    ):
        return "below"

    return "equal"


def mean(values: list[float]) -> float:
    return (
        statistics.mean(values)
        if values
        else 0.0
    )


SUMMARY_METRICS = (
    "rank_improvement",
    "rank_improvement_fraction",

    "actual_below_fraction",
    "actual_above_fraction",

    "new_profile_discriminating_density",
    "new_profile_helpful_density",
    "new_profile_harmful_density",
    "new_profile_net_density",
    "new_profile_helpful_PASS_share",
    "new_profile_helpful_FAIL_share",

    "test_discriminating_density",
    "test_helpful_density",
    "test_harmful_density",
    "test_net_density",
    "test_helpful_PASS_share",
    "test_helpful_FAIL_share",

    "test_competitors_net_helpful_fraction",
    "test_competitors_net_harmful_fraction",
)


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Post-hoc analysis of generated coverage "
            "profiles that discriminate a known fault "
            "from statements tied with it in the "
            "DDMIN baseline."
        )
    )

    parser.add_argument(
        "--subject",
        action="append",
        choices=sorted(
            SUBJECTS
        ),
        dest="subjects",
        help=(
            "Subject to analyze. Repeat for multiple "
            "subjects. Default: all configured subjects."
        ),
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=(
            PROJECT_ROOT
            / "results"
            / "cross_subject"
            / "discriminating_profiles"
        ),
    )

    args = parser.parse_args()

    selected_subjects = (
        args.subjects
        if args.subjects
        else list(
            SUBJECTS
        )
    )

    output_root = (
        args.output_root.resolve()
    )

    output_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    per_run_rows = []
    competitor_rows = []

    for subject_name in selected_subjects:

        config = SUBJECTS[
            subject_name
        ]

        fault_line = int(
            config["fault_line"]
        )

        baseline_run = (
            config[
                "baseline_run"
            ].resolve()
        )

        fuzz_root = (
            config[
                "fuzz_root"
            ].resolve()
        )

        analysis_root = (
            config[
                "analysis_root"
            ].resolve()
        )

        baseline_coverage = (
            baseline_run
            / "coverage"
            / "coverage.jsonl"
        )

        required = (
            baseline_coverage,
            fuzz_root,
            analysis_root,
        )

        for path in required:
            if not path.exists():
                raise SystemExit(
                    f"Missing required path: "
                    f"{path}"
                )

        baseline_records = (
            read_jsonl(
                baseline_coverage
            )
        )

        baseline_profiles = (
            baseline_profile_keys(
                baseline_records
            )
        )

        metadata_files = sorted(
            fuzz_root.rglob(
                "metadata.json"
            )
        )

        if not metadata_files:
            raise SystemExit(
                f"No metadata files under "
                f"{fuzz_root}"
            )

        for metadata_file in metadata_files:

            metadata = json.loads(
                metadata_file.read_text(
                    encoding="utf-8"
                )
            )

            if (
                metadata.get(
                    "subject"
                )
                != subject_name
            ):
                continue

            if (
                metadata.get(
                    "duration_seconds"
                )
                != config[
                    "duration"
                ]
            ):
                continue

            mode = metadata.get(
                "mode"
            )

            if mode not in MODES:
                continue

            repetition = int(
                metadata[
                    "repetition"
                ]
            )

            fuzz_coverage = (
                metadata_file.parent
                / "generated_eval"
                / "coverage"
                / "coverage.jsonl"
            )

            if not fuzz_coverage.is_file():
                raise SystemExit(
                    "Missing fuzz coverage: "
                    f"{fuzz_coverage}"
                )

            fuzz_records = (
                read_jsonl(
                    fuzz_coverage
                )
            )

            new_profiles = (
                unique_new_profiles(
                    fuzz_records,
                    baseline_profiles,
                )
            )

            test_items = (
                generated_test_items(
                    fuzz_records
                )
            )

            new_pass_profiles = sum(
                outcome == "PASS"
                for outcome, _
                in new_profiles
            )

            new_fail_profiles = sum(
                outcome == "FAIL"
                for outcome, _
                in new_profiles
            )

            for score_metric in METRICS:

                baseline_ranking_path = (
                    analysis_root
                    / "baseline"
                    / "sbfl"
                    / (
                        f"{score_metric}"
                        "_ranking.csv"
                    )
                )

                current_ranking_path = (
                    analysis_root
                    / (
                        f"rep"
                        f"{repetition:02d}"
                    )
                    / mode
                    / "sbfl"
                    / (
                        f"{score_metric}"
                        "_ranking.csv"
                    )
                )

                baseline_ranking = (
                    load_ranking(
                        baseline_ranking_path
                    )
                )

                current_ranking = (
                    load_ranking(
                        current_ranking_path
                    )
                )

                competitors = (
                    tied_competitors(
                        baseline_ranking,
                        fault_line,
                    )
                )

                if not competitors:
                    raise RuntimeError(
                        f"{subject_name}: "
                        "baseline fault has no "
                        "tied competitors."
                    )

                profile_summary, profile_detail = (
                    direction_summary(
                        new_profiles,
                        competitors,
                        fault_line,
                    )
                )

                test_summary, test_detail = (
                    direction_summary(
                        test_items,
                        competitors,
                        fault_line,
                    )
                )

                movement_counts = {
                    "above": 0,
                    "below": 0,
                    "equal": 0,
                }

                for competitor in competitors:
                    state = movement(
                        current_ranking,
                        fault_line,
                        competitor,
                    )

                    movement_counts[
                        state
                    ] += 1

                    source = (
                        baseline_ranking[
                            competitor
                        ].get(
                            "source",
                            "",
                        )
                    )

                    competitor_rows.append({
                        "subject":
                            subject_name,

                        "mode":
                            mode,

                        "repetition":
                            repetition,

                        "metric":
                            score_metric,

                        "fault_line":
                            fault_line,

                        "competitor_line":
                            competitor,

                        "source":
                            source,

                        "movement":
                            state,

                        "new_profile_helpful_PASS":
                            profile_detail[
                                competitor
                            ]["helpful_PASS"],

                        "new_profile_helpful_FAIL":
                            profile_detail[
                                competitor
                            ]["helpful_FAIL"],

                        "new_profile_harmful_PASS":
                            profile_detail[
                                competitor
                            ]["harmful_PASS"],

                        "new_profile_harmful_FAIL":
                            profile_detail[
                                competitor
                            ]["harmful_FAIL"],

                        "new_profile_net":
                            profile_detail[
                                competitor
                            ]["net_helpful"],

                        "test_helpful_PASS":
                            test_detail[
                                competitor
                            ]["helpful_PASS"],

                        "test_helpful_FAIL":
                            test_detail[
                                competitor
                            ]["helpful_FAIL"],

                        "test_harmful_PASS":
                            test_detail[
                                competitor
                            ]["harmful_PASS"],

                        "test_harmful_FAIL":
                            test_detail[
                                competitor
                            ]["harmful_FAIL"],

                        "test_net":
                            test_detail[
                                competitor
                            ]["net_helpful"],
                    })

                baseline_average_rank = float(
                    baseline_ranking[
                        fault_line
                    ]["average_rank"]
                )

                current_average_rank = float(
                    current_ranking[
                        fault_line
                    ]["average_rank"]
                )

                rank_improvement = (
                    baseline_average_rank
                    - current_average_rank
                )

                competitor_count = len(
                    competitors
                )

                row = {
                    "subject":
                        subject_name,

                    "mode":
                        mode,

                    "repetition":
                        repetition,

                    "metric":
                        score_metric,

                    "fault_line":
                        fault_line,

                    "baseline_average_rank":
                        baseline_average_rank,

                    "current_average_rank":
                        current_average_rank,

                    "rank_improvement":
                        rank_improvement,

                    "rank_improvement_fraction":
                        safe_div(
                            rank_improvement,
                            baseline_average_rank,
                        ),

                    "baseline_tie_size":
                        competitor_count + 1,

                    "competitor_count":
                        competitor_count,

                    "actual_below":
                        movement_counts[
                            "below"
                        ],

                    "actual_equal":
                        movement_counts[
                            "equal"
                        ],

                    "actual_above":
                        movement_counts[
                            "above"
                        ],

                    "actual_below_fraction":
                        safe_div(
                            movement_counts[
                                "below"
                            ],
                            competitor_count,
                        ),

                    "actual_above_fraction":
                        safe_div(
                            movement_counts[
                                "above"
                            ],
                            competitor_count,
                        ),

                    "generated_usable_tests":
                        len(
                            fuzz_records
                        ),

                    "new_profiles":
                        len(
                            new_profiles
                        ),

                    "new_PASS_profiles":
                        new_pass_profiles,

                    "new_FAIL_profiles":
                        new_fail_profiles,
                }

                for key, value in (
                    profile_summary.items()
                ):
                    row[
                        f"new_profile_{key}"
                    ] = value

                for key, value in (
                    test_summary.items()
                ):
                    row[
                        f"test_{key}"
                    ] = value

                per_run_rows.append(
                    row
                )

                print(
                    f"{subject_name:<14} "
                    f"{mode:<20} "
                    f"r{repetition} "
                    f"{score_metric:<7} "
                    f"rank "
                    f"{baseline_average_rank:.1f}"
                    f"->{current_average_rank:.1f} "
                    f"below="
                    f"{movement_counts['below']}"
                    f"/{competitor_count} "
                    f"profile-net="
                    f"{profile_summary['net_density']:+.4f} "
                    f"test-net="
                    f"{test_summary['net_density']:+.4f} "
                    f"help-PASS="
                    f"{test_summary['helpful_PASS_share']:.2f}"
                )

    per_run_rows.sort(
        key=lambda row: (
            row["subject"],
            row["mode"],
            row["repetition"],
            row["metric"],
        )
    )

    competitor_rows.sort(
        key=lambda row: (
            row["subject"],
            row["mode"],
            row["repetition"],
            row["metric"],
            row["competitor_line"],
        )
    )

    per_run_file = (
        output_root
        / "per_run.csv"
    )

    competitor_file = (
        output_root
        / "competitor_details.csv"
    )

    write_csv(
        per_run_file,
        per_run_rows,
    )

    write_csv(
        competitor_file,
        competitor_rows,
    )

    #
    # Subject/mode/metric means.
    #
    grouped = defaultdict(
        list
    )

    for row in per_run_rows:
        grouped[
            (
                row["subject"],
                row["mode"],
                row["metric"],
            )
        ].append(
            row
        )

    summary_rows = []

    for (
        subject,
        mode,
        score_metric,
    ), rows in sorted(
        grouped.items()
    ):

        summary = {
            "subject":
                subject,

            "mode":
                mode,

            "metric":
                score_metric,

            "n":
                len(rows),
        }

        for field in SUMMARY_METRICS:

            values = [
                float(
                    row[field]
                )
                for row in rows
            ]

            summary[
                f"{field}_mean"
            ] = mean(
                values
            )

            summary[
                f"{field}_median"
            ] = (
                statistics.median(
                    values
                )
            )

        summary_rows.append(
            summary
        )

    summary_file = (
        output_root
        / "subject_mode_summary.csv"
    )

    write_csv(
        summary_file,
        summary_rows,
    )

    #
    # Equal-weight cross-subject descriptive summary.
    #
    cross_rows = []

    normalized_fields = (
        "rank_improvement_fraction",
        "actual_below_fraction",
        "actual_above_fraction",

        "new_profile_helpful_density",
        "new_profile_harmful_density",
        "new_profile_net_density",
        "new_profile_helpful_PASS_share",
        "new_profile_helpful_FAIL_share",

        "test_helpful_density",
        "test_harmful_density",
        "test_net_density",
        "test_helpful_PASS_share",
        "test_helpful_FAIL_share",

        "test_competitors_net_helpful_fraction",
        "test_competitors_net_harmful_fraction",
    )

    for mode in MODES:

        for score_metric in METRICS:

            subject_rows = [
                row
                for row in summary_rows
                if (
                    row["mode"]
                    == mode
                    and
                    row["metric"]
                    == score_metric
                )
            ]

            if not subject_rows:
                continue

            cross = {
                "mode":
                    mode,

                "metric":
                    score_metric,

                "subjects":
                    len(
                        subject_rows
                    ),
            }

            for field in normalized_fields:

                key = (
                    f"{field}_mean"
                )

                cross[
                    f"{field}"
                    "_equal_subject_mean"
                ] = mean([
                    float(
                        row[key]
                    )
                    for row
                    in subject_rows
                ])

            cross_rows.append(
                cross
            )

    cross_file = (
        output_root
        / "cross_subject_equal_weight.csv"
    )

    write_csv(
        cross_file,
        cross_rows,
    )

    readme = output_root / "README.md"

    readme.write_text(
        """# Discriminating-profile post-hoc analysis

This analysis was performed after the formal fuzzing experiments.
It does not modify or rerun any frozen fuzzing configuration.

For every source line tied with the representative fault in the
DDMIN-only baseline, generated coverage is classified directionally.

Helpful discrimination:

- PASS covers the competitor but not the fault.
- FAIL covers the fault but not the competitor.

Harmful discrimination:

- PASS covers the fault but not the competitor.
- FAIL covers the competitor but not the fault.

The analysis reports two views.

1. `new_profile_*` counts each distinct generated coverage profile
   once, and excludes profiles already present in the DDMIN baseline.
   This measures the quality of newly introduced spectrum diversity.

2. `test_*` counts every generated usable test in the augmented suite.
   This preserves multiplicity and therefore more closely represents
   the spectra that actually affected SBFL.

`net_density` is:

    (helpful pairs - harmful pairs)
    / possible fault-competitor pairs

Positive values favor separation of the fault from its baseline-tied
competitors. Negative values favor the reverse direction.

The analysis is descriptive/post-hoc and should not be presented as
a preregistered confirmatory metric.
""",
        encoding="utf-8",
    )

    print()
    print("Saved:")
    print(f"  {per_run_file}")
    print(f"  {competitor_file}")
    print(f"  {summary_file}")
    print(f"  {cross_file}")
    print(f"  {readme}")


if __name__ == "__main__":
    main()
