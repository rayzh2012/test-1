import json, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]

def run(cmd): return subprocess.run(cmd,cwd=ROOT,check=True,text=True,capture_output=True)

def mk(path,shift=0):
    im=Image.new('RGB',(64,64),'white'); d=ImageDraw.Draw(im)
    d.rectangle((8+shift,8,40+shift,40),fill='black'); im.save(path)

def test_near_duplicate_clusters(tmp_path):
    game=tmp_path/'game'; game.mkdir()
    mk(game/'a.png',0); mk(game/'b.png',1)
    Image.new('RGB',(64,64),'gray').save(game/'c.png')
    out=tmp_path/'out.json'
    run([sys.executable,'tools/fangame_perceptual_hash.py',str(game),'--out',str(out),'--threshold','8'])
    data=json.loads(out.read_text())
    pairs={(p['a'],p['b']) for p in data['near_pairs']}
    assert ('a.png','b.png') in pairs
    assert data['summary']['near_duplicate_clusters']>=1
    assert 'common authorship' in data['summary']['interpretation']
