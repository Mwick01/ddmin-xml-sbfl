"""Run unmodified character DDMIN over one namespace-plus-fragment input."""
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import csv
import hashlib
import json
import os
import subprocess
import sys
from xml.dom import minidom
from oracle_mutable_namespace import evaluate, XMLNS_URI

OUT = Path(__file__).resolve().parent
REPO = Path('/home/user/ddmin-xml-sbfl')
run_id = datetime.now(ZoneInfo('Asia/Colombo')).strftime('%Y%m%d_%H%M%S')
RUN = OUT/'runs'/run_id
RUN.mkdir(parents=True,exist_ok=False)
seed = '<case xmlns:p="urn:probe"><span>probe</span></case>'
no_namespace_seed = '<case><span>probe</span></case>'
(RUN/'seed.xml').write_text(seed)
before = subprocess.check_output(['git','status','--porcelain'],cwd=REPO,text=True)
head_before = subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
controls = []
for label,data in [('namespace_present',seed),('namespace_absent',no_namespace_seed)]:
    for i in range(10):
        controls.append({'label':label,'repetition':i+1,**evaluate(data.encode())})
(RUN/'controls.json').write_text(json.dumps(controls,indent=2)+'\n')
assert all(x['classification']=='FAIL' for x in controls if x['label']=='namespace_present')
assert all(x['classification']=='PASS' for x in controls if x['label']=='namespace_absent')
print('Controls verified: namespace present FAIL 10/10; absent PASS 10/10',flush=True)

env = dict(os.environ,TZ='Asia/Colombo',PYTHONDONTWRITEBYTECODE='1',
           MUTABLE_NAMESPACE_ORACLE_LOG=str(RUN/'oracle_results.jsonl'))
command = [sys.executable,'-B',str(OUT/'ddmin.py'),str(RUN/'seed.xml'),
           '--oracle-module','oracle_mutable_namespace','--results-root',str(RUN/'character_ddmin'),
           '--temporary-file',str(RUN/'candidate.xml')]
with (RUN/'ddmin.stdout.txt').open('w') as stdout, (RUN/'ddmin.stderr.txt').open('w') as stderr:
    result = subprocess.run(command,env=env,stdout=stdout,stderr=stderr)
if result.returncode:
    raise RuntimeError((RUN/'ddmin.stderr.txt').read_text())
dirs = list((RUN/'character_ddmin').iterdir())
assert len(dirs)==1
actual = dirs[0]
ddmin = json.loads((actual/'summary.json').read_text())
candidates = [json.loads(line) for line in (actual/'unique_candidates.jsonl').read_text().splitlines()]
details = [json.loads(line) for line in (RUN/'oracle_results.jsonl').read_text().splitlines()]
assert len(details)==len(candidates)==ddmin['unique_candidates']
by_id = {r['candidate_id']:r for r in details}
counts = Counter(x['classification'] for x in candidates)
assert counts['PASS']==ddmin['passing_candidates']
assert counts['FAIL']==ddmin['failing_candidates']
assert counts['UNRESOLVED']==ddmin['unresolved_candidates']
assert counts['PASS']>0 and counts['FAIL']>0, dict(counts)
for item in candidates:
    data = (actual/item['saved_path']).read_bytes()
    assert hashlib.sha256(data).hexdigest()==item['candidate_id']
    assert by_id[item['candidate_id']]['classification']==item['classification']

with (RUN/'candidates.csv').open('w',newline='') as f:
    writer = csv.DictWriter(f,fieldnames=['candidate_id','classification','size_characters',
                                        'stage','namespace_count','fragment','input','saved_path'])
    writer.writeheader()
    for item in candidates:
        detail = by_id[item['candidate_id']]
        decoded = detail.get('decoded')
        writer.writerow({**{k:item[k] for k in ('candidate_id','classification','size_characters')},
                         'stage':detail['stage'],
                         'namespace_count':len(decoded['namespaces']) if decoded else '',
                         'fragment':decoded['fragment'] if decoded else '',
                         'input':detail['input'],
                         'saved_path':str((actual/item['saved_path']).relative_to(OUT))})

minimal_path = actual/'minimal_failure.xml'
minimal_data = minimal_path.read_bytes()
minimal = evaluate(minimal_data)
assert minimal['classification']=='FAIL'
(RUN/'minimal_failure.xml').write_bytes(minimal_data)
pass_record = min((x for x in details if x['classification']=='PASS'),key=lambda x:len(x['input']))
(RUN/'example_pass.xml').write_text(pass_record['input'])

# Find a matching fragment with both classifications among actual DDMIN cases.
groups = defaultdict(list)
for detail in details:
    if detail['classification'] in ('PASS','FAIL'):
        groups[detail['decoded']['fragment']].append(detail)
pairs = []
for fragment,items in groups.items():
    passing = [x for x in items if x['classification']=='PASS']
    failing = [x for x in items if x['classification']=='FAIL']
    if passing and failing:
        pairs.append({'fragment':fragment,
                      'pass':min(passing,key=lambda x:len(x['input'])),
                      'fail':min(failing,key=lambda x:len(x['input']))})
matching_pair = min(pairs,key=lambda p:len(p['pass']['input'])+len(p['fail']['input'])) if pairs else None
(RUN/'same_fragment_ddmin_pair.json').write_text(json.dumps(matching_pair,indent=2)+'\n')
if matching_pair:
    (RUN/'same_fragment_pass.xml').write_text(matching_pair['pass']['input'])
    (RUN/'same_fragment_fail.xml').write_text(matching_pair['fail']['input'])

# Independently remove declarations from the minimal FAIL. This targeted
# post-run check is kept separate from the character-DDMIN candidate counts.
doc = minidom.parseString(minimal_data)
root = doc.documentElement
names = [root.attributes.item(i).name for i in range(root.attributes.length)
         if root.attributes.item(i).namespaceURI==XMLNS_URI]
for name in names:
    root.removeAttribute(name)
counterfactual_data = root.toxml().encode()
doc.unlink()
counterfactual = evaluate(counterfactual_data)
assert counterfactual['classification']=='PASS'
assert counterfactual['decoded']['fragment']==minimal['decoded']['fragment']
(RUN/'minimal_without_namespace.xml').write_bytes(counterfactual_data)
(RUN/'minimal_counterfactual.json').write_text(json.dumps({
    'kind':'post-run targeted check; excluded from DDMIN counts',
    'minimal_fail':minimal,'namespace_removed_pass':counterfactual},indent=2)+'\n')

stability = [evaluate(data) for data in (minimal_data,pass_record['input'].encode()) for _ in range(10)]
assert all(x['classification']=='FAIL' for x in stability[:10])
assert all(x['classification']=='PASS' for x in stability[10:])
(RUN/'example_repeat_checks.json').write_text(json.dumps(stability,indent=2)+'\n')
summary = {'timestamp':datetime.now(ZoneInfo('Asia/Colombo')).isoformat(),
           'seed':seed,'ddmin':ddmin,'counts':{k:counts[k] for k in ('PASS','FAIL','UNRESOLVED')},
           'ddmin_exit_code':result.returncode,'command':command,
           'unresolved_by_stage':dict(Counter(x['stage'] for x in details if x['classification']=='UNRESOLVED')),
           'minimal_failure':minimal,'example_pass':pass_record,
           'same_fragment_ddmin_pair':matching_pair,
           'minimal_without_namespace':counterfactual,
           'stability':{'minimal_FAIL':'10/10','example_PASS':'10/10'},
           'checks':{'candidate_hashes_verified':True,'oracle_records_match_unique_candidates':True,
                     'reducer_algorithm_modified':False,'replay_or_control_cases_included_in_ddmin_counts':False},
           'checkout_head_before':head_before,
           'checkout_head_after':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
           'checkout_status_before':before,
           'checkout_status_after':subprocess.check_output(['git','status','--porcelain'],cwd=REPO,text=True)}
assert summary['checkout_head_after']==head_before
assert summary['checkout_status_after']==before
(RUN/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(OUT/'latest_run.txt').write_text(str(RUN.relative_to(OUT))+'\n')
print(json.dumps({'counts':summary['counts'],'minimal':minimal['input'],
                  'example_PASS':pass_record['input'],
                  'same_fragment_pair':None if not matching_pair else {
                      'PASS':matching_pair['pass']['input'],'FAIL':matching_pair['fail']['input']},
                  'unresolved_by_stage':summary['unresolved_by_stage']},indent=2),flush=True)
print(f'RESULTS: {RUN}',flush=True)
