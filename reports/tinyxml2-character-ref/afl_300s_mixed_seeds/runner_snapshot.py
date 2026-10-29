#!/usr/bin/env python3
"""One exploratory AFL smoke run plus baseline/augmented TinyXML SBFL."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import collect_coverage as collector
import oracle_tinyxml2_character_ref as oracle
import sbfl

BASELINE = ROOT / 'results/tinyxml2_character_ref/character_ddmin_exploratory/20261029_145029_5923'
SOURCE = ROOT / 'subjects/tinyxml2-character-ref/buggy/tinyxml2.cpp'
COVERAGE_BINARY = ROOT / 'build/tinyxml2_character_ref_cov/tinyxml_cov'
COVERAGE_OBJECT = COVERAGE_BINARY.with_name('tinyxml2.o')
FUZZ_DRIVER = ROOT / 'subjects/tinyxml2-character-ref/fuzz_driver.cpp'
TARGET = ROOT / 'build/aflsmart/tinyxml2_character_ref/tinyxml_buggy'
IMAGE = 'ddmin-aflsmart'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

def write_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(record, sort_keys=True) + '\n' for record in records))

def docker_prefix():
    return ['docker', 'run', '--rm', '--network', 'none',
            '--user', f'{os.getuid()}:{os.getgid()}',
            '-e', 'HOME=/tmp', '-e', 'TMPDIR=/tmp', '-e', 'AFL_PATH=/aflsmart',
            '-e', 'AFL_SKIP_CPUFREQ=1', '-e', 'AFL_NO_AFFINITY=1', '-e', 'AFL_NO_UI=1',
            '-e', 'AFL_DONT_OPTIMIZE=1', '-v', f'{ROOT}:/work', '-w', '/work', IMAGE]

def container_path(path):
    return '/work/' + str(Path(path).relative_to(ROOT))

def rank(directory, records):
    write_records(directory / 'coverage/coverage.jsonl', records)
    with (directory / 'sbfl.log').open('w') as log:
        subprocess.run([sys.executable, str(ROOT / 'scripts/sbfl.py'), str(directory),
                        '--source', str(SOURCE), '--fault-line', '550'], cwd=ROOT,
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    return json.loads((directory / 'sbfl/summary.json').read_text())

def diversity(records):
    return {label: len({tuple(record['covered_lines']) for record in records
                       if record['classification'] == label}) for label in ('PASS', 'FAIL')}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=int, default=30)
    parser.add_argument('--seed-mode', choices=('ddmin-mixed', 'fail-only'), default='ddmin-mixed',
                        help='Use all DDMIN PASS seeds plus the minimal FAIL, or only the minimal FAIL.')
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error('--duration must be positive')
    run_id = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime('%Y%m%d_%H%M%S_%f')
    seed_tag = args.seed_mode.replace('-', '_')
    run = ROOT / 'results/tinyxml2_character_ref' / f'smoke_afl_{args.duration}s_{seed_tag}_{run_id}'
    run.mkdir(parents=True)
    seeds = run / 'seeds'
    seeds.mkdir()
    baseline_file = BASELINE / 'coverage/coverage.jsonl'
    original_hash = sha(baseline_file)
    original_source_hash = sha(SOURCE)
    baseline_records = sbfl.load_coverage_records(baseline_file)
    expected_lines = sbfl.validate_records(baseline_records)
    assert Counter(record['classification'] for record in baseline_records) == {'PASS': 6, 'FAIL': 29}
    baseline_hashes = {sha(record['candidate_file']) for record in baseline_records}
    if args.seed_mode == 'ddmin-mixed':
        for record in baseline_records:
            if record['classification'] == 'PASS':
                shutil.copyfile(record['candidate_file'], seeds / Path(record['candidate_file']).name)
    shutil.copyfile(BASELINE / 'minimal_failure.xml', seeds / 'minimal_failure.xml')
    seed_count = 1 if args.seed_mode == 'fail-only' else 7
    assert len(list(seeds.iterdir())) == seed_count
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    build_command = docker_prefix() + [
        '/aflsmart/afl-g++', '-std=c++11', '-O0', '-g', '-DTINYXML2_DEBUG',
        '-I', 'subjects/tinyxml2-character-ref/buggy',
        'subjects/tinyxml2-character-ref/buggy/tinyxml2.cpp',
        'subjects/tinyxml2-character-ref/fuzz_driver.cpp', '-o', str(TARGET.relative_to(ROOT))]
    print(f'Run: {run}\nBuilding AFL target...', flush=True)
    with (run / 'build.log').open('w') as log:
        subprocess.run(build_command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
    for seed in seeds.iterdir():
        label = oracle.classify(seed)
        if args.seed_mode == 'fail-only':
            assert label == 'FAIL' and sha(seed) == sha(BASELINE / 'minimal_failure.xml')
        execution = oracle.run(TARGET, seed)
        if label == 'FAIL':
            assert execution.returncode == 134
            assert all(marker in execution.stderr for marker in oracle.ASSERTION_MARKERS)
        else:
            assert label == 'PASS' and execution.returncode == 0 and execution.stdout.strip() == 'PARSE_OK'
    raw = run / 'raw'
    fuzz_command = docker_prefix() + [
        'timeout', '-s', 'INT', '-k', '5s', f'{args.duration}s', '/aflsmart/afl-fuzz',
        '-m', '200', '-t', '1000', '-d', '-i', container_path(seeds),
        '-o', container_path(raw), '--', container_path(TARGET), '@@']
    print(f'Starting one {args.duration}-second AFL 2.52b run ({args.seed_mode}, {seed_count} seeds)...', flush=True)
    started = time.monotonic()
    with (run / 'fuzzer.log').open('w') as log:
        fuzz = subprocess.run(fuzz_command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - started
    if fuzz.returncode not in (0, 124):
        raise RuntimeError(f'Fuzzer exited {fuzz.returncode}; inspect {run / "fuzzer.log"}')
    stats = {}
    for line in (raw / 'fuzzer_stats').read_text().splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            stats[key.strip()] = value.strip()
    assert int(stats['execs_done']) > 0
    print(f'Fuzzing finished: {stats["execs_done"]} executions. Classifying retained inputs...', flush=True)
    retained = [(kind, path) for kind in ('queue', 'crashes', 'hangs')
                if (raw / kind).is_dir() for path in sorted((raw / kind).iterdir())
                if path.is_file() and path.name.startswith('id:')]
    evaluated = run / 'generated_eval'
    for label in ('pass', 'fail', 'unresolved'):
        (evaluated / label).mkdir(parents=True)
    classifications = []
    seen = set()
    counts = Counter()
    for kind, path in retained:
        digest = sha(path)
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
            row['classification'] = label
            fixed = oracle.run(oracle.FIXED_PROGRAM, path)
            row['fixed_exit_code'] = fixed.returncode
            row['fixed_stdout'] = fixed.stdout.strip()
            counts[label] += 1
            shutil.copyfile(path, evaluated / label.lower() / f'{digest}.xml')
        classifications.append(row)
    write_records(run / 'classification.jsonl', classifications)
    novel_records = []
    try:
        for label in ('PASS', 'FAIL'):
            for candidate in sorted((evaluated / label.lower()).iterdir()):
                record = collector.collect_candidate_coverage(candidate, label, oracle.classify,
                    SOURCE, COVERAGE_BINARY, COVERAGE_OBJECT, COVERAGE_OBJECT.with_suffix('.gcda'))
                assert set(record['executable_lines']) == expected_lines
                if label == 'FAIL':
                    assert record['program_exit_code'] == 134 and 550 in record['covered_lines']
                    assert all(marker in record['program_stderr'] for marker in oracle.ASSERTION_MARKERS)
                else:
                    assert record['program_exit_code'] == 0
                record['candidate_sha256'] = sha(candidate)
                novel_records.append(record)
    finally:
        collector.reset_coverage_data(COVERAGE_OBJECT.with_suffix('.gcda'))
    write_records(evaluated / 'coverage/coverage.jsonl', novel_records)
    augmented_records = baseline_records + novel_records
    assert len({sha(record['candidate_file']) for record in augmented_records}) == len(augmented_records)
    baseline = rank(run / 'baseline_eval', baseline_records)
    augmented = rank(run / 'augmented_eval', augmented_records)
    assert sha(baseline_file) == original_hash and sha(SOURCE) == original_source_hash
    prior = json.loads((BASELINE / 'sbfl/summary.json').read_text())
    for metric in ('jaccard', 'ochiai'):
        assert baseline[metric] == prior[metric]
    summary = {
        'status': 'EXPLORATORY_SINGLE_RUN_SMOKE', 'subject': 'TinyXML-2 #997',
        'run_directory': str(run), 'baseline_run': str(BASELINE),
        'fuzzer': 'AFL 2.52b from ddmin-aflsmart, plain byte mutation, -d',
        'duration_budget_seconds': args.duration, 'docker_fuzz_elapsed_seconds': elapsed,
        'fuzzer_returncode': fuzz.returncode, 'fuzzer_stats': stats,
        'seed_inputs': seed_count, 'seed_mode': args.seed_mode,
        'seed_method': ('only the 32-byte minimized DDMIN FAIL' if args.seed_mode == 'fail-only'
                        else 'six original DDMIN PASS candidates plus minimized DDMIN FAIL'),
        'seed_manifest': [{'file': seed.name, 'sha256': sha(seed), 'size_bytes': seed.stat().st_size}
                          for seed in sorted(seeds.iterdir())],
        'handwritten_probe_inputs_used': False,
        'classification_scope': 'retained queue, crash, and hang inputs; original seeds and byte duplicates excluded',
        'classification_counts': {label: counts[label] for label in ('PASS', 'FAIL', 'UNRESOLVED')},
        'retained_entries': len(retained),
        'excluded_counts': dict(Counter(row['excluded'] for row in classifications if 'excluded' in row)),
        'novel_usable_tests': len(novel_records),
        'baseline_profiles': diversity(baseline_records), 'generated_profiles': diversity(novel_records),
        'augmented_profiles': diversity(augmented_records),
        'generated_fail_fixed_accept_count': sum(row.get('classification') == 'FAIL' and row.get('fixed_exit_code') == 0 for row in classifications),
        'generated_fail_fixed_reject_count': sum(row.get('classification') == 'FAIL' and row.get('fixed_exit_code') == 2 for row in classifications),
        'baseline': baseline, 'augmented': augmented,
        'build_command': build_command, 'fuzz_command': fuzz_command,
        'fuzz_build_flags': '-std=c++11 -O0 -g -DTINYXML2_DEBUG, AFL_DONT_OPTIMIZE=1',
        'fuzz_abort_handling': 'Fuzz-only SIGABRT handler exits 134; original buggy/fixed oracle determines outcomes, target assertion checked in coverage',
        'coverage_build_unchanged': True, 'baseline_records_unchanged': True,
        'sha256': {str(path.relative_to(ROOT)): sha(path) for path in [SOURCE, FUZZ_DRIVER, TARGET, COVERAGE_BINARY, baseline_file, Path(__file__), ROOT / 'scripts/oracle_tinyxml2_character_ref.py', oracle.BUGGY_PROGRAM, oracle.FIXED_PROGRAM]},
        'docker_image_id': subprocess.check_output(['docker', 'image', 'inspect', IMAGE, '--format', '{{.Id}}'], text=True).strip(),
    }
    save_json(run / 'summary.json', summary)
    with (run / 'comparison.csv').open('w', newline='') as handle:
        fields = ['suite', 'metric', 'passing_tests', 'failing_tests', 'score', 'best_rank', 'average_rank', 'worst_rank', 'exam_percentage', 'executable_lines']
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for suite, result in [('baseline', baseline), ('augmented', augmented)]:
            for metric in ('jaccard', 'ochiai'):
                row = result[metric]
                writer.writerow({'suite': suite, 'metric': metric, 'passing_tests': result['passing_tests'],
                    'failing_tests': result['failing_tests'], 'score': row['first_fault_score'],
                    'best_rank': row['best_rank'], 'average_rank': row['average_rank'],
                    'worst_rank': row['worst_rank'], 'exam_percentage': row['exam_percentage_average'],
                    'executable_lines': result['executable_line_count']})
    with zipfile.ZipFile(run / 'retained_inputs.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(seeds.iterdir()):
            archive.write(path, str(path.relative_to(run)))
        for _, path in retained:
            archive.write(path, str(path.relative_to(run)))
    print(json.dumps({key: summary[key] for key in ('run_directory', 'duration_budget_seconds', 'docker_fuzz_elapsed_seconds', 'classification_counts', 'excluded_counts', 'novel_usable_tests', 'generated_profiles', 'augmented_profiles', 'generated_fail_fixed_accept_count')}, indent=2))
    print((run / 'comparison.csv').read_text())

if __name__ == '__main__':
    main()
