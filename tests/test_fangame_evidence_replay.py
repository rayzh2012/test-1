#!/usr/bin/env python3
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUILDER=ROOT/'tests'/'build_minimal_rpgmaker_replay_fixture.rb'
REPLAY=ROOT/'tools'/'fangame_evidence_replay.py'


def sha256(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


def main():
  with tempfile.TemporaryDirectory() as td:
    td=Path(td); game=td/'game'; bundle=td/'bundle'; out=td/'replay'; game.mkdir(); bundle.mkdir()
    subprocess.run(['ruby',str(BUILDER),str(game)],cwd=ROOT,check=True)
    archive=bundle/'fixture.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
      for p in game.rglob('*'):
        if p.is_file(): z.write(p,p.relative_to(game))
    digest=sha256(archive)
    report={
      'name':'Replay Fixture','version':'1.0','file':'fixture.zip','bytes':archive.stat().st_size,'sha256':digest,
      'attempts':[{'url':'https://example.invalid/fixture.zip','final_url':'https://example.invalid/fixture.zip','status':200}],
      'sources':['https://example.invalid/fixture.zip']}
    (bundle/'fetch_report.json').write_text(json.dumps(report),encoding='utf-8')
    (bundle/'SHA256.txt').write_text(f'{digest}  fixture.zip\n',encoding='utf-8')

    subprocess.run([
      sys.executable,str(REPLAY),'--bundle',str(bundle),'--outdir',str(out),
      '--source-run-id','synthetic-run','--source-artifact-name','synthetic-full'
    ],cwd=ROOT,check=True)

    manifest=json.loads((out/'replay_manifest.json').read_text(encoding='utf-8'))
    feature=json.loads((out/'fangame_features.json').read_text(encoding='utf-8'))
    graph=json.loads((out/'rpgmaker_graph.json').read_text(encoding='utf-8'))
    prog=json.loads((out/'rpgmaker_progression.json').read_text(encoding='utf-8'))
    vector=json.loads((out/'fangame_grind_vector.json').read_text(encoding='utf-8'))

    assert manifest['replay_version']=='fangame.evidence.replay.v0.6'
    assert manifest['source']['archive_sha256']==digest
    assert manifest['source']['sha256_verified'] is True
    assert manifest['source']['github_actions_run_id']=='synthetic-run'
    assert manifest['source']['github_actions_artifact_name']=='synthetic-full'
    assert manifest['immutability']=={'raw_artifact_changed':False,'archive_repacked':False,'archive_executed':False}
    assert manifest['replay_scope']['static_structure_replayed'] is True
    assert manifest['replay_scope']['graph_replayed'] is True
    assert manifest['replay_scope']['progression_economy_replayed'] is True
    assert manifest['replay_scope']['runtime_replayed'] is False
    assert manifest['output']['feature_schema']=='fangame.features.v0.5b'
    assert manifest['output']['grind_pressure'] is None
    assert manifest['output']['estimated_hours_range'] is None
    assert len(manifest['toolchain'])>=10

    assert feature['schema_version']=='fangame.features.v0.5b'
    assert feature['identity']['sha256']==digest
    assert feature['identity']['title']=='Replay Fixture'
    assert feature['runtime']['mechanical_status'] is None
    assert feature['progression']['status']=='PROGRESSION_OBSERVED'
    assert feature['grind_vector']['calibration_status']=='UNLABELED_VECTOR_ONLY'
    assert feature['inferred']['grind_pressure'] is None
    assert feature['inferred']['estimated_hours_range'] is None

    assert graph['graph_version']=='rpgmaker.graph.v0.3'
    assert graph['summary']['maps_loaded']==2
    assert graph['summary']['direct_map_edges']>=2
    assert prog['evidence_version']=='rpgmaker.progression.v0.5a'
    assert prog['observed']['maps_loaded']==2
    assert prog['observed']['maps_with_random_encounters']==2
    assert prog['observed']['enemy_exp_stats']['median']==50.0
    assert vector['vector_version']=='fangame.grind.vector.v0.5b'
    assert vector['grind_pressure'] is None

    # Working extraction tree must not be retained as a durable replay product.
    assert not (out/'replay_work').exists()

    # Mutating the immutable archive after the historical hash was recorded must hard-fail replay.
    with archive.open('ab') as f: f.write(b'TAMPER')
    bad=subprocess.run([
      sys.executable,str(REPLAY),'--bundle',str(bundle),'--outdir',str(td/'bad')
    ],cwd=ROOT)
    assert bad.returncode!=0

  print('fangame immutable evidence replay v0.6: PASS')

if __name__=='__main__': main()
