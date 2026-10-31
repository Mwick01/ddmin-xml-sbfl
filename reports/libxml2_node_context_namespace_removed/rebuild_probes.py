from pathlib import Path
import difflib
import hashlib
import io
import json
import os
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work' / 'node_context'
OUT = ROOT / 'outputs' / 'libxml2_node_context_namespace_removed'
REPO = Path('/home/user/ddmin-xml-sbfl')
SOURCE = REPO / 'temporary/libxml2-467-source'
REF = '28b33554441e7fafe4a8f9f3b61f6b894b839c6c'
OUT.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)
commands = []

def capture(args, cwd=REPO):
    return subprocess.check_output(args, cwd=cwd)

def logged(args, path):
    commands.append(args)
    with path.open('wb') as log:
        result = subprocess.run(args, stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print(path.read_text(errors='replace')[-7000:], flush=True)
        raise RuntimeError(f'Command failed ({result.returncode}): {args}')

for p in [Path('/AGENTS.md'), Path('/home/AGENTS.md'), Path('/home/user/AGENTS.md'), REPO/'AGENTS.md']:
    if p.is_file():
        raise RuntimeError(f'Read instructions before proceeding: {p}\n{p.read_text()}')

probe = capture(['git', 'show', f'{REF}:reports/libxml2_node_context_suitability/probe.c']).decode()
start = probe.index('    /*\n     * Reproduce the upstream condition:')
end = probe.index('    result = xmlParseInNodeContext(', start)
removed = probe[:start] + '    /* Namespace-free control: keep the HTML document and fragment unchanged. */\n' + probe[end:]
removed = removed.replace('    xmlNsPtr ns = NULL;\n', '')
assert 'xmlNewNs' not in removed
(OUT/'probe_original.c').write_text(probe)
(OUT/'probe_no_namespace.c').write_text(removed)
(OUT/'namespace_removal.patch').write_text(''.join(difflib.unified_diff(
    probe.splitlines(keepends=True), removed.splitlines(keepends=True),
    fromfile='probe_original.c', tofile='probe_no_namespace.c')))
(OUT/'original_suitability_report.md').write_bytes(capture([
    'git', 'show', f'{REF}:reports/libxml2_node_context_suitability/README.md']))
(OUT/'ddmin.py').write_bytes(capture(['git', 'show', f'{REF}:scripts/ddmin.py']))

manifest = {'experiment_commit': REF,
            'checkout_head_before': capture(['git', 'rev-parse', 'HEAD']).decode().strip(),
            'checkout_status_before': capture(['git', 'status', '--porcelain']).decode(),
            'source_repository': str(SOURCE), 'versions': {}, 'commands': commands}
for version in ['2.12.4', '2.12.5']:
    tag = f'v{version}'
    src = WORK / f'src-{version}'
    build = WORK / f'build-{version}'
    print(f'Preparing {tag}', flush=True)
    if not (src/'CMakeLists.txt').exists():
        paths = capture(['git', 'ls-tree', '-r', '--name-only', tag], SOURCE).decode().splitlines()
        selected = [p for p in paths if '/' not in p or p.startswith('include/') or
                    p in ('doc/xml2-config.1', 'doc/xmlcatalog.1', 'doc/xmllint.1')]
        archive = capture(['git', 'archive', '--format=tar', tag, '--', *selected], SOURCE)
        src.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
            tf.extractall(src, filter='data')
    build.mkdir(parents=True, exist_ok=True)
    options = ['-DCMAKE_BUILD_TYPE=Debug', '-DBUILD_SHARED_LIBS=OFF',
               '-DLIBXML2_WITH_PYTHON=OFF', '-DLIBXML2_WITH_PROGRAMS=OFF',
               '-DLIBXML2_WITH_TESTS=OFF', '-DLIBXML2_WITH_ICONV=OFF',
               '-DLIBXML2_WITH_LZMA=OFF', '-DLIBXML2_WITH_ZLIB=OFF',
               '-DLIBXML2_WITH_HTTP=OFF', '-DLIBXML2_WITH_ICU=OFF']
    logged(['cmake', '-S', str(src), '-B', str(build), *options], build/'configure.log')
    print(f'Building {tag}', flush=True)
    logged(['cmake', '--build', str(build), '--target', 'LibXml2', '--parallel', '4'], build/'build.log')
    for kind in ['original', 'no_namespace']:
        binary = build / f'probe_{kind}'
        logged(['gcc', '-g', '-O0', '-DLIBXML_STATIC', '-I'+str(build),
                '-I'+str(src/'include'), str(OUT/f'probe_{kind}.c'),
                str(build/'libxml2.a'), '-lm', '-ldl', '-lpthread', '-o', str(binary)],
               build/f'compile_{kind}.log')
    manifest['versions'][version] = {
        'tag': tag, 'commit': capture(['git', 'rev-parse', tag+'^{commit}'], SOURCE).decode().strip(),
        'build': str(build), 'cmake_options': options,
        'static_library_sha256': hashlib.sha256((build/'libxml2.a').read_bytes()).hexdigest(),
        'probe_sha256': {kind: hashlib.sha256((build/f'probe_{kind}').read_bytes()).hexdigest()
                         for kind in ['original', 'no_namespace']}}
    print(f'Built both probes for {tag}', flush=True)
manifest['source_sha256'] = {name: hashlib.sha256((OUT/name).read_bytes()).hexdigest()
                             for name in ['probe_original.c', 'probe_no_namespace.c', 'ddmin.py']}
(OUT/'build_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(f'BUILD READY: {OUT}', flush=True)
