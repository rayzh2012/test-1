import json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_mapinfos_is_not_a_map(tmp_path):
    data=tmp_path/'Data'; data.mkdir()
    for name in ('Map001.rvdata','Map139.rvdata','MapInfos.rvdata','Map001.rvdata2.bak'):
        (data/name).write_bytes(b'')
    ruby=r'''require 'json'
require_relative 'tools/rpgmaker_marshal_lib'
root=ARGV[0]
files=map_files_for(root)
puts JSON.generate({'names'=>files.map{|p| File.basename(p)},'ids'=>files.map{|p| map_id_from_file(p)},'mapinfos_id'=>map_id_from_file(File.join(root,'Data','MapInfos.rvdata'))})
'''
    p=subprocess.run(['ruby','-e',ruby,str(tmp_path)],cwd=ROOT,check=True,text=True,capture_output=True)
    out=json.loads(p.stdout)
    assert out['names']==['Map001.rvdata','Map139.rvdata']
    assert out['ids']==[1,139]
    assert out['mapinfos_id'] is None
