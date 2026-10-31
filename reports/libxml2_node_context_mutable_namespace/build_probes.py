"""Compile the mutable-namespace driver using the previous verified libraries."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
PREVIOUS = ROOT/'outputs/libxml2_node_context_namespace_removed'
MANIFEST = json.loads((PREVIOUS/'build_manifest.json').read_text())
BUILD = ROOT/'work/node_context_mutable'
manifest = {'experiment_commit':MANIFEST['experiment_commit'],
            'input_model':'mutable XML envelope: root xmlns declarations + serialized children',
            'versions':{}, 'commands':[]}
for version in ('2.12.4','2.12.5'):
    previous = Path(MANIFEST['versions'][version]['build'])
    source = previous.parent/f'src-{version}'
    dest = BUILD/f'build-{version}'
    dest.mkdir(parents=True, exist_ok=True)
    library = previous/'libxml2.a'
    digest = hashlib.sha256(library.read_bytes()).hexdigest()
    assert digest == MANIFEST['versions'][version]['static_library_sha256']
    args = ['gcc','-g','-O0','-DLIBXML_STATIC','-I'+str(previous),
            '-I'+str(source/'include'),str(OUT/'probe_mutable.c'),str(library),
            '-lm','-ldl','-lpthread','-o',str(dest/'probe_mutable')]
    with (dest/'compile.log').open('w') as f:
        completed = subprocess.run(args,stdout=f,stderr=subprocess.STDOUT)
    if completed.returncode:
        raise RuntimeError((dest/'compile.log').read_text())
    manifest['commands'].append(args)
    manifest['versions'][version] = {
        'commit':MANIFEST['versions'][version]['commit'],
        'cmake_options':MANIFEST['versions'][version]['cmake_options'],
        'static_library_sha256':digest,
        'binary':str(dest/'probe_mutable'),
        'binary_sha256':hashlib.sha256((dest/'probe_mutable').read_bytes()).hexdigest()}
    print(f'Built mutable-namespace probe for {version}', flush=True)
shutil.copy2(PREVIOUS/'ddmin.py',OUT/'ddmin.py')
manifest['source_sha256'] = {name:hashlib.sha256((OUT/name).read_bytes()).hexdigest()
                             for name in ('probe_mutable.c','ddmin.py','oracle_mutable_namespace.py')}
assert manifest['source_sha256']['ddmin.py'] == MANIFEST['source_sha256']['ddmin.py']
manifest['tool_versions'] = {name:subprocess.check_output(args,text=True).splitlines()[0]
                            for name,args in [('gcc',['gcc','--version']),('python',['python3','--version'])]}
(OUT/'build_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
