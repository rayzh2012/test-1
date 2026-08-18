import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_reference_fusion_exact_near_and_unknown(tmp_path):
    game={'assets':[
      {'path':'Graphics/Characters/exact.png','sha256':'aaa','bytes':100},
      {'path':'Graphics/Characters/edited.png','sha256':'bbb','bytes':120},
      {'path':'Graphics/Faces/other.png','sha256':'ccc','bytes':80},
    ]}
    ph={'images':[
      {'path':'Graphics/Characters/exact.png','width':96,'height':128,'dhash64':'0000000000000000'},
      {'path':'Graphics/Characters/edited.png','width':96,'height':128,'dhash64':'0000000000000001'},
      {'path':'Graphics/Faces/other.png','width':96,'height':96,'dhash64':'0000000000000001'},
    ]}
    ref={'engine':'RPG Maker VX','rtp_version':'2.02','package_sha256':'p','asset_files':2,'image_perceptual_signatures':2,'assets':[
      {'relative_path':'app/Graphics/Characters/base.png','sha256':'aaa','asset_category':'graphics/characters','width':96,'height':128,'dhash64':'0000000000000000'},
      {'relative_path':'app/Graphics/Characters/base2.png','sha256':'ddd','asset_category':'graphics/characters','width':96,'height':128,'dhash64':'0000000000000000'},
    ]}
    for name,obj in [('game.json',game),('ph.json',ph),('ref.json',ref)]:
        (tmp_path/name).write_text(json.dumps(obj),encoding='utf-8')
    out=tmp_path/'out.json'
    subprocess.run([sys.executable,str(ROOT/'tools/fangame_asset_reference_fuse.py'),str(tmp_path/'game.json'),str(tmp_path/'ph.json'),str(tmp_path/'ref.json'),'--threshold','4','--out',str(out)],check=True,cwd=ROOT)
    x=json.loads(out.read_text())
    classes={r['path']:r['classification'] for r in x['assets']}
    assert classes['Graphics/Characters/exact.png']=='REFERENCE_EXACT_MATCH'
    assert classes['Graphics/Characters/edited.png']=='MODIFIED_RTP_LIKE'
    assert classes['Graphics/Faces/other.png']=='NO_REFERENCE_SIMILARITY_FOUND'
    assert x['summary']['rtp_supported_files_union']==2
