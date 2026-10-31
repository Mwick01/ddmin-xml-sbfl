"""Historical #672 acceptance/crash oracle, with explicit namespace mode.

PASS: fixed and buggy probes accept, with equal result/list summaries.
FAIL: fixed probe accepts, buggy probe dies with SIGSEGV.
UNRESOLVED: all other outcomes, including invalid fragments and timeouts.
This compares probe summaries, not full serialized output trees.
"""
from pathlib import Path
import json
import os
import re
import resource
import signal
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = Path(os.environ.get('NODE_CONTEXT_BUILD_ROOT', ROOT/'work/node_context'))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

def run_probe(version, mode, fragment):
    binary = BUILD_ROOT / f'build-{version}' / f'probe_{mode}'
    try:
        result = subprocess.run([str(binary), fragment], capture_output=True,
                                text=True, errors='replace', timeout=2.0)
        match = re.fullmatch(r'result=(\d+) list=(non-null|null)\n?', result.stdout)
        return {'returncode': result.returncode, 'stdout': result.stdout,
                'stderr': result.stderr, 'timed_out': False,
                'parse_result': int(match[1]) if match else None,
                'list': match[2] if match else None}
    except subprocess.TimeoutExpired:
        return {'returncode': None, 'stdout': '', 'stderr': '',
                'timed_out': True, 'parse_result': None, 'list': None}

def evaluate(fragment, mode):
    assert mode in ('original', 'no_namespace')
    fixed = run_probe('2.12.5', mode, fragment)
    buggy = run_probe('2.12.4', mode, fragment)
    fixed_valid = (not fixed['timed_out'] and fixed['returncode'] == 0
                   and fixed['parse_result'] == 0)
    if not fixed_valid or buggy['timed_out']:
        outcome = 'UNRESOLVED'
    elif buggy['returncode'] == -signal.SIGSEGV:
        outcome = 'FAIL'
    elif (buggy['returncode'] == 0 and buggy['parse_result'] == 0
          and buggy['stdout'] == fixed['stdout']):
        outcome = 'PASS'
    else:
        outcome = 'UNRESOLVED'
    return {'fragment': fragment, 'mode': mode, 'classification': outcome,
            'buggy': buggy, 'fixed': fixed}

def classify(candidate):
    fragment = Path(candidate).read_bytes().decode('utf-8')
    result = evaluate(fragment, os.environ['NODE_CONTEXT_MODE'])
    if os.environ.get('NODE_CONTEXT_ORACLE_LOG'):
        with Path(os.environ['NODE_CONTEXT_ORACLE_LOG']).open('a') as f:
            f.write(json.dumps(result, sort_keys=True)+'\n')
    return result['classification']
