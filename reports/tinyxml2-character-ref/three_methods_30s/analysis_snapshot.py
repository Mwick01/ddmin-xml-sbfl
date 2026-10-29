"""Classify, collect and independently validate SBFL for the three-method smoke test."""
from pathlib import Path
from collections import Counter
import csv
import json
import math
import shutil
import sys
import zipfile

ROOT = Path('/home/user/ddmin-xml-sbfl')
sys.path.insert(0, str(ROOT / 'scripts'))
import smoke_tinyxml2_character_ref as old
import oracle_tinyxml2_character_ref as oracle
import collect_coverage as collector
import sbfl

WORK = Path(__file__).parent
campaign = Path((WORK / 'campaign_path.txt').read_text().strip())
meta = json.loads((campaign / 'campaign.json').read_text())
assert meta['status'] == 'FUZZING_COMPLETE_AWAITING_SBFL'
baseline_records = sbfl.load_coverage_records(old.BASELINE / 'coverage/coverage.jsonl')
lines = sbfl.validate_records(baseline_records)
assert len(lines) == 1563
baseline_hashes = {old.sha(Path(row['candidate_file'])) for row in baseline_records}
baseline = old.rank(campaign / 'baseline_eval', baseline_records)
previous = json.loads((old.BASELINE / 'sbfl/summary.json').read_text())
for metric in ('jaccard', 'ochiai'):
    assert baseline[metric] == previous[metric]

def independently_check(records, summary):
    passing = [set(row['covered_lines']) for row in records if row['classification'] == 'PASS']
    failing = [set(row['covered_lines']) for row in records if row['classification'] == 'FAIL']
    spectra = {line: (sum(line in s for s in failing), sum(line in s for s in passing)) for line in lines}
    for metric in ('jaccard', 'ochiai'):
        scores = {}
        for line, (ef, ep) in spectra.items():
            scores[line] = ef / (len(failing) + ep) if metric == 'jaccard' else (ef / math.sqrt(len(failing) * (ef + ep)) if ef + ep else 0)
        fault_score = scores[550]
        best = 1 + sum(v > fault_score + 1e-12 for v in scores.values())
        worst = sum(v >= fault_score - 1e-12 for v in scores.values())
        average = (best + worst) / 2
        saved = summary[metric]
        assert abs(saved['first_fault_score'] - fault_score) < 1e-12
        assert (best, average, worst) == (saved['best_rank'], saved['average_rank'], saved['worst_rank'])
        assert abs(saved['exam_percentage_average'] - 100 * average / len(lines)) < 1e-12
    ef, ep = spectra[550]
    return {'ef': ef, 'ep': ep, 'nf': len(failing) - ef, 'np': len(passing) - ep}

independently_check(baseline_records, baseline)
base_tie = {int(row['line']) for row in csv.DictReader((campaign / 'baseline_eval/sbfl/jaccard_ranking.csv').open()) if row['best_rank'] == '1'}
summaries = {}
for mode in meta['methods']:
    directory = campaign / mode
    print('CLASSIFY ' + mode, flush=True)
    for label in ('pass', 'fail', 'unresolved'):
        (directory / 'generated_eval' / label).mkdir(parents=True)
    retained = [(kind, path) for kind in ('queue', 'crashes', 'hangs')
                if (directory / 'raw' / kind).exists()
                for path in sorted((directory / 'raw' / kind).glob('id:*')) if path.is_file()]
    seen = set()
    rows = []
    counts = Counter()
    for kind, path in retained:
        digest = old.sha(path)
        row = {'kind': kind, 'test_id': path.name, 'sha256': digest, 'size_bytes': path.stat().st_size}
        if ',orig:' in path.name:
            row['excluded'] = 'seed_entry'
        elif digest in baseline_hashes:
            row['excluded'] = 'duplicate_baseline'
        elif digest in seen:
            row['excluded'] = 'duplicate_generated'
        else:
            seen.add(digest)
            label = oracle.classify(path)
            fixed = oracle.run(oracle.FIXED_PROGRAM, path)
            row.update(classification=label, fixed_exit_code=fixed.returncode, fixed_stdout=fixed.stdout.strip())
            counts[label] += 1
            shutil.copyfile(path, directory / 'generated_eval' / label.lower() / (digest + '.xml'))
        rows.append(row)
    old.write_records(directory / 'classification.jsonl', rows)
    novel = []
    repeated_records = []
    validation = []
    try:
        for label in ('PASS', 'FAIL'):
            for candidate in sorted((directory / 'generated_eval' / label.lower()).iterdir()):
                record = collector.collect_candidate_coverage(candidate, label, oracle.classify,
                    old.SOURCE, old.COVERAGE_BINARY, old.COVERAGE_OBJECT, old.COVERAGE_OBJECT.with_suffix('.gcda'))
                assert set(record['executable_lines']) == lines
                assert old.sha(candidate) == candidate.stem
                buggy = oracle.run(oracle.BUGGY_PROGRAM, candidate)
                fixed = oracle.run(oracle.FIXED_PROGRAM, candidate)
                if label == 'FAIL':
                    assert buggy.returncode == -6 and record['program_exit_code'] == 134
                    assert 550 in record['covered_lines']
                    assert all(marker in buggy.stderr and marker in record['program_stderr'] for marker in oracle.ASSERTION_MARKERS)
                else:
                    assert buggy.returncode == fixed.returncode == record['program_exit_code'] == 0
                    assert buggy.stdout.strip() == fixed.stdout.strip() == record['program_stdout'].strip() == 'PARSE_OK'
                record['candidate_sha256'] = candidate.stem
                repeated = collector.collect_candidate_coverage(candidate, label, oracle.classify,
                    old.SOURCE, old.COVERAGE_BINARY, old.COVERAGE_OBJECT, old.COVERAGE_OBJECT.with_suffix('.gcda'))
                assert repeated['execution_counts'] == record['execution_counts']
                assert repeated['covered_lines'] == record['covered_lines']
                novel.append(record)
                repeated_records.append(repeated)
                validation.append({'sha256': candidate.stem, 'label': label, 'buggy_exit': buggy.returncode,
                    'fixed_exit': fixed.returncode, 'coverage_exit': record['program_exit_code'],
                    'line_550_covered': 550 in record['covered_lines'], 'repeated_counts_identical': True})
    finally:
        collector.reset_coverage_data(old.COVERAGE_OBJECT.with_suffix('.gcda'))
    old.write_records(directory / 'generated_eval/coverage/coverage.jsonl', novel)
    old.write_records(directory / 'repeated_coverage.jsonl', repeated_records)
    augmented_records = baseline_records + novel
    assert len({old.sha(Path(row['candidate_file'])) for row in augmented_records}) == len(augmented_records)
    augmented = old.rank(directory / 'augmented_eval', augmented_records)
    target = independently_check(augmented_records, augmented)
    new_tie = {int(row['line']) for row in csv.DictReader((directory / 'augmented_eval/sbfl/jaccard_ranking.csv').open()) if row['best_rank'] == '1'}
    pass_demotions = sorted(line for line in base_tie if any(row['classification'] == 'PASS' and line in row['covered_lines'] for row in novel))
    fail_demotions = sorted(line for line in base_tie if any(row['classification'] == 'FAIL' and line not in row['covered_lines'] for row in novel))
    summary = {'status': 'EXPLORATORY_SINGLE_RUN_SMOKE', 'method': mode, 'run_directory': str(directory),
        'classification_counts': {label: counts[label] for label in ('PASS', 'FAIL', 'UNRESOLVED')},
        'retained_entries': len(retained), 'exclusions': dict(Counter(row['excluded'] for row in rows if 'excluded' in row)),
        'usable_generated_tests': len(novel), 'generated_profiles': old.diversity(novel),
        'augmented_profiles': old.diversity(augmented_records),
        'generated_fail_fixed_accept_count': sum(row.get('classification') == 'FAIL' and row.get('fixed_exit_code') == 0 for row in rows),
        'generated_fail_fixed_reject_count': sum(row.get('classification') == 'FAIL' and row.get('fixed_exit_code') == 2 for row in rows),
        'fuzz': meta['runs'][mode], 'baseline': baseline, 'augmented': augmented,
        'validation': {'repeated_counts_identical': len(validation), 'independent_ranks_verified': True,
            'target_spectrum': target, 'original_top_tie': sorted(base_tie), 'augmented_top_tie': sorted(new_tie),
            'pass_demoted_original_tie_lines': pass_demotions, 'fail_demoted_original_tie_lines': fail_demotions}}
    assert summary['exclusions'].get('seed_entry') == 7
    old.save_json(directory / 'summary.json', summary)
    with (directory / 'validation.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['sha256', 'label', 'buggy_exit', 'fixed_exit', 'coverage_exit', 'line_550_covered', 'repeated_counts_identical'])
        writer.writeheader()
        writer.writerows(validation)
    with zipfile.ZipFile(directory / 'retained_inputs_and_chunks.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for kind, path in retained:
            archive.write(path, str(path.relative_to(directory)))
        for path in sorted((directory / 'raw/chunks').glob('*')):
            if path.is_file():
                archive.write(path, str(path.relative_to(directory)))
    summaries[mode] = summary
    print(f'DONE {mode}: {dict(counts)}, rank {augmented["jaccard"]["average_rank"]}, EXAM {augmented["jaccard"]["exam_percentage_average"]:.6f}%, validated {len(validation)} spectra', flush=True)

for relative, digest in meta['sha256'].items():
    assert old.sha(ROOT / relative) == digest
assert old.sha(ROOT / 'aflsmart/tinyxml2_character_ref_fragments.xml') == meta['model_sha256']
meta['status'] = 'COMPLETE_EXPLORATORY'
meta['results'] = {mode: {'counts': value['classification_counts'], 'rank': value['augmented']['jaccard']['average_rank'],
    'exam_percentage': value['augmented']['jaccard']['exam_percentage_average']} for mode, value in summaries.items()}
old.save_json(campaign / 'campaign.json', meta)
shutil.copyfile(Path(__file__), campaign / 'analysis_snapshot.py')
print('SBFL VALIDATION COMPLETE', flush=True)
