#!/usr/bin/env python3
"""Reproduce node-context character DDMIN without changing archived reports.

Requires Linux/WSL, Python 3.12+, GCC, CMake and Make. Sources are read from a
local libxml2 Git repository; libraries, binaries and new results are ignored.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
COMMITS = {'2.12.4':'8292f361458fcffe0bff515a385be02e9d35582c',
           '2.12.5':'e189e9945317ad4c8603fa2300d11d11f5e2e335'}
OPTIONS = ['-DCMAKE_BUILD_TYPE=Debug','-DBUILD_SHARED_LIBS=OFF',
           '-DLIBXML2_WITH_PYTHON=OFF','-DLIBXML2_WITH_PROGRAMS=OFF',
           '-DLIBXML2_WITH_TESTS=OFF','-DLIBXML2_WITH_ICONV=OFF',
           '-DLIBXML2_WITH_LZMA=OFF','-DLIBXML2_WITH_ZLIB=OFF',
           '-DLIBXML2_WITH_HTTP=OFF','-DLIBXML2_WITH_ICU=OFF']

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def logged(command: list[str], log: Path) -> None:
    with log.open('w') as stream:
        result = subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Command failed; see {log}\n{log.read_text()[-4000:]}')

def prepare_library(version: str, library_root: Path, source_repo: Path, jobs: int) -> dict:
    source = library_root/f'src-{version}'
    build = library_root/f'build-{version}'
    library = build/'libxml2.a'
    if not library.is_file():
        if not source_repo.is_dir():
            raise RuntimeError('Provide --source-repo pointing to a libxml2 Git checkout with tags v2.12.4 and v2.12.5.')
        commit = subprocess.check_output(['git','rev-parse',f'v{version}^{{commit}}'],cwd=source_repo,text=True).strip()
        if commit != COMMITS[version]:
            raise RuntimeError(f'Unexpected source commit for v{version}: {commit}')
        if not (source/'CMakeLists.txt').is_file():
            paths = subprocess.check_output(['git','ls-tree','-r','--name-only',commit],cwd=source_repo,text=True).splitlines()
            selected = [p for p in paths if '/' not in p or p.startswith('include/') or
                        p in ('doc/xml2-config.1','doc/xmlcatalog.1','doc/xmllint.1')]
            archive = subprocess.check_output(['git','archive','--format=tar',commit,'--',*selected],cwd=source_repo)
            source.mkdir(parents=True,exist_ok=True)
            with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
                tf.extractall(source,filter='data')
        build.mkdir(parents=True,exist_ok=True)
        print(f'Building libxml2 {version}',flush=True)
        logged(['cmake','-S',str(source),'-B',str(build),*OPTIONS],build/'configure.log')
        logged(['cmake','--build',str(build),'--target','LibXml2','--parallel',str(jobs)],build/'build.log')
    header = build/'libxml/xmlversion.h'
    match = re.search(r'#define\s+LIBXML_DOTTED_VERSION\s+"([^"]+)"',header.read_text())
    if not match or match[1] != version or not (source/'include/libxml/parser.h').is_file():
        raise RuntimeError(f'Headers do not match requested version {version}: {library_root}')
    return {'version':version,'library':str(library),'sha256':sha(library),
            'generated_headers':str(build),'source_headers':str(source/'include')}

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['mutable','original','namespace-removed'],default='mutable')
    parser.add_argument('--source-repo',type=Path,default=ROOT/'temporary/libxml2-467-source')
    parser.add_argument('--library-root',type=Path,default=ROOT/'build/libxml2_node_context_libraries',
                        help='Optional existing build-VERSION/libxml2.a and src-VERSION/include directories.')
    parser.add_argument('--jobs',type=int,default=4)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error('--jobs must be positive')
    mutable = args.mode=='mutable'
    report = ROOT/'reports'/('libxml2_node_context_mutable_namespace' if mutable else 'libxml2_node_context_namespace_removed')
    archived_reducer = report/'ddmin.py'
    if sha(archived_reducer) != sha(ROOT/'scripts/ddmin.py'):
        raise RuntimeError('Archived reducer differs from this branch scripts/ddmin.py; inspect before comparing runs.')
    binaries = ROOT/'build/libxml2_node_context_probes'
    kind = 'mutable' if mutable else ('original' if args.mode=='original' else 'no_namespace')
    source = report/f'probe_{kind}.c'
    libraries = []
    for version in COMMITS:
        info = prepare_library(version,args.library_root.resolve(),args.source_repo.resolve(),args.jobs)
        build = binaries/f'build-{version}'
        build.mkdir(parents=True,exist_ok=True)
        binary = build/f'probe_{kind}'
        command = ['gcc','-g','-O0','-DLIBXML_STATIC','-I'+info['generated_headers'],
                   '-I'+info['source_headers'],str(source),info['library'],
                   '-lm','-ldl','-lpthread','-o',str(binary)]
        logged(command,build/f'compile_{kind}.log')
        libraries.append({**info,'binary':str(binary),'binary_sha256':sha(binary),'compile_command':command})
    run_id = datetime.now(ZoneInfo('Asia/Colombo')).strftime('%Y%m%d_%H%M%S')+f'_{os.getpid()}'
    output = ROOT/'results/libxml2_node_context'/args.mode/run_id
    output.mkdir(parents=True,exist_ok=False)
    seed = '<case xmlns:p="urn:probe"><span>probe</span></case>' if mutable else '<span>probe</span>'
    (output/'seed.xml').write_text(seed)
    module = 'oracle_mutable_namespace' if mutable else 'oracle_node_context'
    env = dict(os.environ,TZ='Asia/Colombo',PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=str(report)+os.pathsep+os.environ.get('PYTHONPATH',''))
    if mutable:
        env.update(MUTABLE_NAMESPACE_BUILD_ROOT=str(binaries),
                   MUTABLE_NAMESPACE_ORACLE_LOG=str(output/'oracle_results.jsonl'))
    else:
        env.update(NODE_CONTEXT_BUILD_ROOT=str(binaries),NODE_CONTEXT_MODE=kind,
                   NODE_CONTEXT_ORACLE_LOG=str(output/'oracle_results.jsonl'))
    command = [sys.executable,'-B',str(archived_reducer),str(output/'seed.xml'),
               '--oracle-module',module,'--results-root',str(output/'ddmin'),
               '--temporary-file',str(output/'candidate.xml')]
    before = subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    print(f'Running character DDMIN ({args.mode}); results: {output}',flush=True)
    with (output/'stdout.txt').open('w') as stdout, (output/'stderr.txt').open('w') as stderr:
        result = subprocess.run(command,env=env,stdout=stdout,stderr=stderr)
    records = [json.loads(line) for line in (output/'oracle_results.jsonl').read_text().splitlines()]
    counts = Counter(r['classification'] for r in records)
    summary = {'mode':args.mode,'seed':seed,'exit_code':result.returncode,
               'counts':{k:counts[k] for k in ('PASS','FAIL','UNRESOLVED')},
               'unique_candidates':len(records),'command':command,'libraries':libraries,
               'driver_sha256':sha(source),'reducer_sha256':sha(archived_reducer),
               'oracle_sha256':sha(report/f'{module}.py'),
               'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
               'git_status_before':before,
               'git_status_after':subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)}
    if args.mode=='namespace-removed':
        expected = result.returncode==1 and counts['PASS']==1 and 'classified as PASS' in (output/'stderr.txt').read_text()
        summary['status']='stopped_initial_input_PASS' if expected else 'unexpected_result'
    else:
        expected = result.returncode==0 and counts['FAIL']>0 and (counts['PASS']>0 if mutable else True)
        summary['status']='completed' if expected else 'unexpected_result'
    (output/'run_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({k:summary[k] for k in ('mode','status','counts','unique_candidates')},indent=2))
    if not expected:
        print((output/'stderr.txt').read_text(),file=sys.stderr)
    return 0 if expected else 1

if __name__=='__main__':
    raise SystemExit(main())
