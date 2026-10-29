"""Run one 30-second trial per existing repository AFL method."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
import os
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path('/home/user/ddmin-xml-sbfl')
sys.path.insert(0, str(ROOT / 'scripts'))
import smoke_tinyxml2_character_ref as old
import oracle_tinyxml2_character_ref as oracle

def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')

stamp = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime('%Y%m%d_%H%M%S_%f')
campaign = ROOT / 'results/tinyxml2_character_ref' / ('three_methods_30s_' + stamp)
campaign.mkdir()
Path(__file__).with_name('campaign_path.txt').write_text(str(campaign) + '\n')
previous = ROOT / 'reports/tinyxml2-character-ref/afl_300s_mixed_seeds/summary.json'
prior = json.loads(previous.read_text())
old30 = Path(json.loads((ROOT / 'reports/tinyxml2-character-ref/smoke_afl_30s/summary.json').read_text())['run_directory'])
seeds = campaign / 'seeds'
shutil.copytree(old30 / 'seeds', seeds)
assert len(list(seeds.iterdir())) == 7
assert Counter(oracle.classify(seed) for seed in seeds.iterdir()) == {'PASS': 6, 'FAIL': 1}
tracked = [old.SOURCE, old.FUZZ_DRIVER, old.TARGET, old.COVERAGE_BINARY,
           old.COVERAGE_OBJECT, old.COVERAGE_OBJECT.with_suffix('.gcno'),
           old.BASELINE / 'coverage/coverage.jsonl', ROOT / 'scripts/oracle_tinyxml2_character_ref.py',
           oracle.BUGGY_PROGRAM, oracle.FIXED_PROGRAM]
hashes = {str(path.relative_to(ROOT)): old.sha(path) for path in tracked}
for path in (old.SOURCE, old.FUZZ_DRIVER, old.TARGET, old.COVERAGE_BINARY):
    assert hashes[str(path.relative_to(ROOT))] == prior['sha256'][str(path.relative_to(ROOT))]
model = ROOT / 'aflsmart/tinyxml2_character_ref_fragments.xml'
shutil.copyfile(model, campaign / model.name)
shutil.copyfile(Path(__file__), campaign / 'run_three_methods_snapshot.py')
shutil.copyfile(old.FUZZ_DRIVER, campaign / 'fuzz_driver_snapshot.cpp')
shutil.copytree(ROOT / 'results/tinyxml2_character_ref/three_methods_model_preflight_v3', campaign / 'model_preflight')
metadata = {'status': 'RUNNING', 'subject': 'TinyXML-2 #997', 'campaign_directory': str(campaign),
            'created_at': datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(),
            'duration_seconds_each': 30, 'methods': ['afl', 'aflsmart-nonstack', 'aflsmart-mixed'],
            'seed_origin': str(old30 / 'seeds'),
            'seed_manifest': {seed.name: old.sha(seed) for seed in sorted(seeds.iterdir())},
            'seed_labels': {'PASS': 6, 'FAIL': 1}, 'baseline_run': str(old.BASELINE),
            'sha256': hashes, 'model_sha256': old.sha(model),
            'shared_target_rebuilt': False, 'shared_target_binary': str(old.TARGET),
            'docker_image_id': subprocess.check_output(['docker', 'image', 'inspect', old.IMAGE, '--format', '{{.Id}}'], text=True).strip(),
            'randomness': 'AFL runtime RNG is uncontrolled; one trial per method; instrumentation binary held fixed',
            'method_definition': {'afl': 'plain byte mutation, -d',
                'aflsmart-nonstack': '-d -w peach -g MODEL; structural mutations without mixed stacking',
                'aflsmart-mixed': '-d -w peach -g MODEL -h; byte and structural stacking'},
            'runs': {}}
save(campaign / 'campaign.json', metadata)
print('CAMPAIGN ' + str(campaign), flush=True)
for mode in metadata['methods']:
    directory = campaign / mode
    directory.mkdir()
    args = ['/aflsmart/afl-fuzz', '-m', '200', '-t', '1000', '-d',
            '-i', old.container_path(seeds), '-o', old.container_path(directory / 'raw')]
    if mode.startswith('aflsmart'):
        args += ['-w', 'peach', '-g', old.container_path(model)]
    if mode == 'aflsmart-mixed':
        args += ['-h']
    args += ['--', old.container_path(old.TARGET), '@@']
    inner = ['timeout', '-s', 'INT', '-k', '5s', '30s'] + args
    command = old.docker_prefix() + ['bash', '-c',
        'export PATH=/aflsmart/peach-3.0.202-source/output/linux_x86_64_release/bin:/aflsmart:$PATH\nexec ' + shlex.join(inner)]
    print('START ' + mode, flush=True)
    started = time.monotonic()
    with (directory / 'fuzzer.log').open('w') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    elapsed = time.monotonic() - started
    assert result.returncode in (0, 124), (mode, result.returncode)
    stats = {}
    for line in (directory / 'raw/fuzzer_stats').read_text().splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            stats[key.strip()] = value.strip()
    assert int(stats['execs_done']) > 0
    chunks = list((directory / 'raw/chunks').glob('*.chunks'))
    queue = list((directory / 'raw/queue').glob('id:*'))
    smart_retained = [p.name for p in queue if 'smart' in p.name]
    run = {'returncode': result.returncode, 'elapsed_seconds': elapsed, 'command': command,
           'stats': stats, 'chunk_files': len(chunks), 'retained_smart_names': smart_retained,
           'target_sha256': old.sha(old.TARGET)}
    assert run['target_sha256'] == hashes[str(old.TARGET.relative_to(ROOT))]
    if mode.startswith('aflsmart'):
        assert len(chunks) > 0, 'AFLSmart never produced structural chunks'
    metadata['runs'][mode] = run
    save(directory / 'fuzz_summary.json', run)
    save(campaign / 'campaign.json', metadata)
    print(f'DONE {mode}: {stats["execs_done"]} execs, {len(chunks)} chunk files, {len(smart_retained)} retained smart mutations', flush=True)
for relative, digest in hashes.items():
    assert old.sha(ROOT / relative) == digest
metadata['status'] = 'FUZZING_COMPLETE_AWAITING_SBFL'
save(campaign / 'campaign.json', metadata)
print('FUZZING COMPLETE', flush=True)
