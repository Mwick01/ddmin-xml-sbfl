"""Compare existing 30-second TinyXML character and structural seed pipelines."""
from pathlib import Path
import csv
import hashlib
import json
import shutil

ROOT = Path('/home/user/ddmin-xml-sbfl')
PARENT = ROOT / 'reports/tinyxml2-character-ref'
OUT = PARENT / 'pipeline_comparison_30s'
OUT.mkdir(exist_ok=True)
SOURCES = {
    'character': PARENT / 'three_methods_30s',
    'structural_fragment': PARENT / 'three_methods_structural_30s',
}
MODES = ['afl', 'aflsmart-nonstack', 'aflsmart-mixed']
LABELS = {'baseline': 'DDMIN baseline', 'afl': 'Plain AFL',
          'aflsmart-nonstack': 'AFLSmart nonstack', 'aflsmart-mixed': 'AFLSmart mixed'}

def read_json(path):
    return json.loads(path.read_text())

def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

campaigns = {name: read_json(path / 'campaign.json') for name, path in SOURCES.items()}
assert all(campaign['status'] == 'COMPLETE_EXPLORATORY' for campaign in campaigns.values())
assert all(campaign['methods'] == MODES and campaign['duration_seconds_each'] == 30 for campaign in campaigns.values())
assert all(campaign['seed_labels'] == ({'PASS': 6, 'FAIL': 1} if name == 'character' else {'PASS': 1, 'FAIL': 7})
           for name, campaign in campaigns.items())
assert campaigns['character']['docker_image_id'] == campaigns['structural_fragment']['docker_image_id']
assert campaigns['character']['model_sha256'] == campaigns['structural_fragment']['model_sha256']
shared_hashes = {key: campaigns['character']['sha256'][key] for key in set(campaigns['character']['sha256']) & set(campaigns['structural_fragment']['sha256'])
                 if campaigns['character']['sha256'][key] == campaigns['structural_fragment']['sha256'][key]}
expected_shared = [
    'subjects/tinyxml2-character-ref/buggy/tinyxml2.cpp',
    'subjects/tinyxml2-character-ref/fuzz_driver.cpp',
    'build/aflsmart/tinyxml2_character_ref/tinyxml_buggy',
    'build/tinyxml2_character_ref_cov/tinyxml_cov',
    'build/tinyxml2_character_ref_cov/tinyxml2.o',
    'build/tinyxml2_character_ref_cov/tinyxml2.gcno',
    'scripts/oracle_tinyxml2_character_ref.py',
    'subjects/tinyxml2-character-ref/buggy_asan',
    'subjects/tinyxml2-character-ref/fixed_asan',
]
assert all(key in shared_hashes for key in expected_shared)
assert sha(SOURCES['character'] / 'tinyxml2_character_ref_fragments.xml') == campaigns['character']['model_sha256']
assert sha(SOURCES['structural_fragment'] / 'tinyxml2_character_ref_fragments.xml') == campaigns['structural_fragment']['model_sha256']
assert campaigns['character']['seed_manifest'].keys() != campaigns['structural_fragment']['seed_manifest'].keys()
seed_hashes = {name: set(campaign['seed_manifest'].values()) for name, campaign in campaigns.items()}
seed_overlap = sorted(seed_hashes['character'] & seed_hashes['structural_fragment'])
baselines = {name: read_json(path / 'baseline_sbfl_summary.json') for name, path in SOURCES.items()}
mode_summaries = {name: {mode: read_json(path / mode / 'summary.json') for mode in MODES}
                  for name, path in SOURCES.items()}

def tie(path):
    with path.open(newline='') as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1563
    return {int(row['line']) for row in rows if row['best_rank'] == '1' and float(row['score']) == 1.0}

ties = {}
for name, path in SOURCES.items():
    # Baseline ranking is stored at the DDMIN report and in the raw run.
    baseline_ranking = (PARENT / 'jaccard_ranking.csv' if name == 'character'
                        else PARENT / 'structural_ddmin_exploratory/jaccard_ranking.csv')
    ties[name] = {'baseline': tie(baseline_ranking)}
    for mode in MODES:
        ties[name][mode] = tie(path / mode / 'jaccard_ranking.csv')

rows = []
for pipeline in ('character', 'structural_fragment'):
    campaign = campaigns[pipeline]
    baseline = baselines[pipeline]
    assert (baseline['passing_tests'], baseline['failing_tests']) == (
        (6, 29) if pipeline == 'character' else (1, 7))
    for mode in ['baseline'] + MODES:
        s = None if mode == 'baseline' else mode_summaries[pipeline][mode]
        suite = baseline if s is None else s['augmented']
        counts = {'PASS': 0, 'FAIL': 0, 'UNRESOLVED': 0} if s is None else s['classification_counts']
        assert suite['passing_tests'] == baseline['passing_tests'] + counts['PASS']
        assert suite['failing_tests'] == baseline['failing_tests'] + counts['FAIL']
        assert len(ties[pipeline][mode]) == suite['jaccard']['worst_rank']
        if s is not None:
            assert s['validation']['repeated_counts_identical'] == counts['PASS'] + counts['FAIL']
        for metric in ('jaccard', 'ochiai'):
            r = suite[metric]
            b = baseline[metric]
            assert r['first_fault_line'] == 550 and r['executable_line_count'] == b['executable_line_count'] == 1563
            rows.append({'pipeline': pipeline, 'suite': mode, 'metric': metric,
                'seed_pass': campaign['seed_labels']['PASS'], 'seed_fail': campaign['seed_labels']['FAIL'],
                'baseline_pass': baseline['passing_tests'], 'baseline_fail': baseline['failing_tests'],
                'new_pass': counts['PASS'], 'new_fail': counts['FAIL'], 'new_unresolved': counts['UNRESOLVED'],
                'combined_pass': suite['passing_tests'], 'combined_fail': suite['failing_tests'],
                'executions': '' if s is None else int(s['fuzz']['stats']['execs_done']),
                'fault_score': r['first_fault_score'], 'best_rank': r['best_rank'],
                'average_rank': r['average_rank'], 'worst_rank': r['worst_rank'],
                'tie_width': len(ties[pipeline][mode]), 'exam_percentage': r['exam_percentage_average'],
                'rank_improvement': b['average_rank'] - r['average_rank'],
                'exam_improvement_percentage_points': b['exam_percentage_average'] - r['exam_percentage_average'],
                'relative_improvement_percent': 100 * (b['average_rank'] - r['average_rank']) / b['average_rank']})

with (OUT / 'comparison.csv').open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
overlap = {}
for mode in ['baseline'] + MODES:
    character = ties['character'][mode]
    structural = ties['structural_fragment'][mode]
    overlap[mode] = {'character_width': len(character), 'structural_width': len(structural),
        'common_lines': len(character & structural), 'character_only': sorted(character - structural),
        'structural_only': sorted(structural - character), 'sets_equal': character == structural}
save_json(OUT / 'tie_overlap.json', overlap)
provenance = {'seed_overlap_sha256': seed_overlap, 'seed_overlap_count': len(seed_overlap),
    'seed_hashes': {name: sorted(values) for name, values in seed_hashes.items()},
    'seed_selection': {'character': 'all 6 DDMIN PASS candidates plus only its 32-byte minimized FAIL',
                       'structural_fragment': 'all 1 PASS and 7 FAIL structural DDMIN candidates, including its 63-byte minimized FAIL'},
    'shared_docker_image_id': campaigns['character']['docker_image_id'],
    'shared_model_sha256': campaigns['character']['model_sha256'],
    'verified_shared_file_sha256': {key: shared_hashes[key] for key in expected_shared},
    'same_seed_corpus': False, 'same_baseline_suite': False, 'same_mutation_rng_state': False,
    'same_run_date': False, 'same_compiled_afl_target': True,
    'one_trial_per_mode_per_pipeline': True,
    'source_reports': {name: str(path / 'README.md') for name, path in SOURCES.items()}}
save_json(OUT / 'provenance.json', provenance)
shutil.copyfile(SOURCES['character'] / 'comparison.csv', OUT / 'character_source_comparison.csv')
shutil.copyfile(SOURCES['structural_fragment'] / 'comparison.csv', OUT / 'structural_source_comparison.csv')
print(json.dumps({'seed_overlap': len(seed_overlap), 'tie_overlap': {key: {k: v for k, v in value.items() if k != 'character_only' and k != 'structural_only'} for key, value in overlap.items()},
                  'rows': len(rows)}, indent=2))
