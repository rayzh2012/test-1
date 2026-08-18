import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run(cmd):
    return subprocess.run(cmd,cwd=ROOT,check=True,text=True,capture_output=True)

def test_reference_manifest_and_match(tmp_path):
    ref=tmp_path/'ref'; game=tmp_path/'game'; ref.mkdir(); game.mkdir()
    (ref/'Graphics').mkdir(); (game/'Graphics').mkdir()
    (ref/'Graphics'/'same.png').write_bytes(b'abc123')
    (ref/'Graphics'/'onlyref.png').write_bytes(b'ref-only')
    (game/'Graphics'/'same.png').write_bytes(b'abc123')
    (game/'Graphics'/'custom.png').write_bytes(b'custom')
    manifest=tmp_path/'ref.json'; fp=tmp_path/'fp.json'; match=tmp_path/'match.json'
    run([sys.executable,'tools/fangame_reference_manifest.py',str(ref),'--engine','TEST','--source-label','synthetic','--out',str(manifest)])
    run([sys.executable,'tools/fangame_asset_fingerprint.py',str(game),'--out',str(fp)])
    run([sys.executable,'tools/fangame_reference_match.py',str(fp),str(manifest),'--out',str(match)])
    m=json.loads(match.read_text())['summary']
    assert m['exact_reference_match_files']==1
    assert m['exact_reference_match_ratio_files']==0.5
    assert m['nonreference_or_modified_files']==1

def test_nonmatch_never_claims_originality(tmp_path):
    ref=tmp_path/'ref'; game=tmp_path/'game'; ref.mkdir(); game.mkdir()
    (ref/'a.png').write_bytes(b'a'); (game/'b.png').write_bytes(b'b')
    manifest=tmp_path/'ref.json'; fp=tmp_path/'fp.json'; match=tmp_path/'match.json'
    run([sys.executable,'tools/fangame_reference_manifest.py',str(ref),'--engine','TEST','--source-label','synthetic','--out',str(manifest)])
    run([sys.executable,'tools/fangame_asset_fingerprint.py',str(game),'--out',str(fp)])
    run([sys.executable,'tools/fangame_reference_match.py',str(fp),str(manifest),'--out',str(match)])
    text=match.read_text()
    assert 'does NOT prove originality' in text
