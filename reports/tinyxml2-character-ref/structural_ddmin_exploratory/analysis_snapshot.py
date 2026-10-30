from pathlib import Path
from collections import Counter
import csv
import importlib.util
import json
import math
import shutil
import sys
import zipfile
from xml.dom import minidom

ROOT = Path('/home/user/ddmin-xml-sbfl')
WORK = Path(__file__).parent
sys.path.insert(0, str(ROOT / 'scripts'))
import smoke_tinyxml2_character_ref as old
import oracle_tinyxml2_character_ref as oracle
import collect_coverage as collector
import sbfl

run = sorted((ROOT / 'results/tinyxml2_character_ref').glob('structural_ddmin_exploratory_*'))[-1]
(WORK / 'structural_run_path.txt').write_text(str(run) + '\n')
summary = json.loads((run / 'summary.json').read_text())
assert summary['original_bytes'] == 341
assert summary['counts'] == {'PASS': 1, 'FAIL': 7, 'UNRESOLVED': 12}
hashes = {str(path.relative_to(ROOT)): old.sha(path) for path in (
    old.SOURCE, old.COVERAGE_BINARY, old.COVERAGE_OBJECT, old.COVERAGE_OBJECT.with_suffix('.gcno'),
    oracle.BUGGY_PROGRAM, oracle.FIXED_PROGRAM, ROOT / 'scripts/oracle_tinyxml2_character_ref.py',
    old.BASELINE / 'coverage/coverage.jsonl')}
original = (run / 'original.xml').read_bytes()
try:
    original.decode('utf-8')
    utf8 = True
except UnicodeDecodeError:
    utf8 = False
try:
    minidom.parseString(original)
    strict_xml = True
    strict_error = None
except Exception as error:
    strict_xml = False
    strict_error = str(error)
assert not utf8 and not strict_xml

def subsequence(parent, child):
    cursor = 0
    for value in child:
        index = parent.find(bytes([value]), cursor)
        if index < 0:
            return False
        cursor = index + 1
    return True

classifications = []
for row in [json.loads(line) for line in (run / 'unique_candidates.jsonl').read_text().splitlines()]:
    path = run / row['saved_path']
    assert old.sha(path) == row['candidate_id']
    assert subsequence(original, path.read_bytes())
    assert oracle.classify(path) == row['classification']
    fixed = oracle.run(oracle.FIXED_PROGRAM, path)
    buggy = oracle.run(oracle.BUGGY_PROGRAM, path)
    classifications.append({**row, 'buggy_exit_code': buggy.returncode, 'fixed_exit_code': fixed.returncode,
                            'fixed_stdout': fixed.stdout.strip(), 'deletion_only_verified': True})
old.write_records(run / 'classification_validation.jsonl', classifications)
records = []
repeated_records = []
validation = []
expected = sbfl.validate_records(sbfl.load_coverage_records(old.BASELINE / 'coverage/coverage.jsonl'))
try:
    for label in ('PASS', 'FAIL'):
        for path in sorted((run / label.lower()).glob('*.xml')):
            row = collector.collect_candidate_coverage(path, label, oracle.classify,
                old.SOURCE, old.COVERAGE_BINARY, old.COVERAGE_OBJECT, old.COVERAGE_OBJECT.with_suffix('.gcda'))
            assert set(row['executable_lines']) == expected
            assert row['program_exit_code'] == (134 if label == 'FAIL' else 0)
            if label == 'FAIL':
                assert 550 in row['covered_lines']
                assert all(marker in row['program_stderr'] for marker in oracle.ASSERTION_MARKERS)
            row['candidate_sha256'] = old.sha(path)
            repeated = collector.collect_candidate_coverage(path, label, oracle.classify,
                old.SOURCE, old.COVERAGE_BINARY, old.COVERAGE_OBJECT, old.COVERAGE_OBJECT.with_suffix('.gcda'))
            assert repeated['covered_lines'] == row['covered_lines']
            assert repeated['execution_counts'] == row['execution_counts']
            records.append(row)
            repeated_records.append(repeated)
            validation.append({'sha256': path.stem, 'classification': label,
                'coverage_exit': row['program_exit_code'], 'fault_line_covered': 550 in row['covered_lines'],
                'repeat_counts_identical': True})
finally:
    collector.reset_coverage_data(old.COVERAGE_OBJECT.with_suffix('.gcda'))
old.write_records(run / 'repeated_coverage.jsonl', repeated_records)
result = old.rank(run, records)
assert result['passing_tests'] == 1 and result['failing_tests'] == 7
passing = [set(row['covered_lines']) for row in records if row['classification'] == 'PASS']
failing = [set(row['covered_lines']) for row in records if row['classification'] == 'FAIL']
for metric in ('jaccard', 'ochiai'):
    scores = {}
    for line in expected:
        ef = sum(line in cov for cov in failing)
        ep = sum(line in cov for cov in passing)
        scores[line] = ef / (len(failing) + ep) if metric == 'jaccard' else (ef / math.sqrt(len(failing) * (ef + ep)) if ef + ep else 0)
    fault = scores[550]
    best = 1 + sum(value > fault + 1e-12 for value in scores.values())
    worst = sum(value >= fault - 1e-12 for value in scores.values())
    saved = result[metric]
    assert abs(saved['first_fault_score'] - fault) < 1e-12
    assert (best, (best + worst) / 2, worst) == (saved['best_rank'], saved['average_rank'], saved['worst_rank'])
    assert abs(saved['exam_percentage_average'] - 100 * (best + worst) / 2 / len(expected)) < 1e-12

minimal = run / 'minimal_failure.xml'
repeat_labels = [oracle.classify(minimal) for _ in range(10)]
assert repeat_labels == ['FAIL'] * 10
fixed_fail_counts = Counter(row['fixed_exit_code'] for row in classifications if row['classification'] == 'FAIL')
checks = {'usable_spectra': len(records), 'repeat_counts_identical': len(records),
    'all_unique_candidates_reclassified': len(classifications), 'all_candidates_are_original_byte_subsequences': True,
    'minimal_failure_repeat_labels': repeat_labels, 'original_is_utf8': utf8,
    'original_is_strict_well_formed_xml': strict_xml, 'strict_xml_preflight_error': strict_error,
    'fixed_fail_exit_counts': dict(fixed_fail_counts), 'independent_sbfl_verified': True,
    'one_unit_minimality_deletions_checked': len(summary['minimality_audit']),
    'coverage_profiles': old.diversity(records), 'sha256': hashes}
for relative, digest in hashes.items():
    assert old.sha(ROOT / relative) == digest
old.save_json(run / 'validation_summary.json', checks)
with (run / 'coverage_validation.csv').open('w', newline='') as handle:
    writer = csv.DictWriter(handle, fieldnames=['sha256', 'classification', 'coverage_exit', 'fault_line_covered', 'repeat_counts_identical'])
    writer.writeheader()
    writer.writerows(validation)
with zipfile.ZipFile(run / 'all_candidates.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
    for label in ('pass', 'fail', 'unresolved'):
        for path in sorted((run / label).glob('*.xml')):
            archive.write(path, str(path.relative_to(run)))
    assert len(archive.namelist()) == 20
shutil.copyfile(WORK / 'tinyxml2_structural_ddmin.py', ROOT / 'scripts/tinyxml2_structural_ddmin.py')
shutil.copyfile(WORK / 'tinyxml2_structural_ddmin.py', run / 'reducer_snapshot.py')
shutil.copyfile(Path(__file__), run / 'analysis_snapshot.py')
print(json.dumps({'run_directory': str(run), 'minimal_repr': repr(minimal.read_bytes()), 'ddmin': summary['counts'],
    'profiles': checks['coverage_profiles'], 'sbfl': {metric: result[metric] for metric in ('jaccard', 'ochiai')},
    'validation': checks}, indent=2))
