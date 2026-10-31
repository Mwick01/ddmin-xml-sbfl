"""One mutable XML envelope describes namespace declarations and fragment.

The same Python stdlib XML decoder is used for both target versions.
Root namespace declarations configure the HTML context. Serialized root
children form the fragment. Root name and ordinary root attributes do not
configure the context. Empty namespace undeclarations attach no namespace.
Only fragment characters and root namespace declarations affect the probe.
PASS compares acceptance and result/list summaries, not serialized trees.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import resource
import signal
import subprocess
from xml.dom import minidom
from xml.parsers.expat import ExpatError

ROOT = Path(__file__).resolve().parents[2]
BUILD_ROOT = Path(os.environ.get('MUTABLE_NAMESPACE_BUILD_ROOT', ROOT/'work/node_context_mutable'))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
XMLNS_URI = 'http://www.w3.org/2000/xmlns/'

def decode_input(data):
    doc = minidom.parseString(data)
    try:
        root = doc.documentElement
        namespaces = []
        for i in range(root.attributes.length):
            attribute = root.attributes.item(i)
            if attribute.namespaceURI == XMLNS_URI and attribute.value:
                prefix = '' if attribute.name == 'xmlns' else attribute.localName
                namespaces.append({'prefix': prefix, 'uri': attribute.value})
        fragment = ''.join(child.toxml() for child in root.childNodes)
        return {'namespaces': namespaces, 'fragment': fragment,
                'envelope_name': root.tagName}
    finally:
        doc.unlink()

def run_probe(version, decoded):
    program = BUILD_ROOT/f'build-{version}'/'probe_mutable'
    args = [str(program), decoded['fragment']]
    for namespace in decoded['namespaces']:
        args.extend([namespace['prefix'], namespace['uri']])
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                errors='replace', timeout=2.0)
        match = re.fullmatch(r'result=(\d+) list=(non-null|null)\n?', result.stdout)
        return {'returncode': result.returncode, 'stdout': result.stdout,
                'stderr': result.stderr, 'timed_out': False,
                'parse_result': int(match[1]) if match else None,
                'list': match[2] if match else None}
    except subprocess.TimeoutExpired:
        return {'returncode': None, 'stdout': '', 'stderr': '',
                'timed_out': True, 'parse_result': None, 'list': None}

def evaluate(data):
    record = {'candidate_id': hashlib.sha256(data).hexdigest(),
              'input': data.decode('utf-8', errors='replace')}
    try:
        decoded = decode_input(data)
    except (ExpatError, ValueError, UnicodeError) as error:
        return {**record, 'classification': 'UNRESOLVED', 'stage': 'input_decode',
                'decode_error': str(error), 'buggy': None, 'fixed': None}
    record['decoded'] = decoded
    fixed = run_probe('2.12.5', decoded)
    buggy = run_probe('2.12.4', decoded)
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
    return {**record, 'classification': outcome, 'stage': 'probe',
            'buggy': buggy, 'fixed': fixed}

def classify(candidate):
    record = evaluate(Path(candidate).read_bytes())
    if os.environ.get('MUTABLE_NAMESPACE_ORACLE_LOG'):
        with Path(os.environ['MUTABLE_NAMESPACE_ORACLE_LOG']).open('a') as f:
            f.write(json.dumps(record, sort_keys=True)+'\n')
    return record['classification']
