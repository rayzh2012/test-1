import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run(cmd): return subprocess.run(cmd,cwd=ROOT,check=True,text=True,capture_output=True)

def test_sidequest_and_ending_candidates(tmp_path):
    d={'rows':[
      {'scope':'map','map_id':2,'event_id':1,'page_id':1,'kind':'dialogue','text':'请你帮我寻找三朵花，完成后我会给你奖励。'},
      {'scope':'map','map_id':9,'event_id':3,'page_id':1,'kind':'dialogue','text':'终章：故事终于结束。THE END'},
    ]}
    g={'switch_reads':{'5':[{'map_id':2}]},'switch_writes':{'5':[{'map_id':2}]},'variable_reads':{},'variable_writes':{}}
    n={'leaf_maps':[2,9],'isolated_maps':[],'branching_maps':[]}
    for name,obj in [('d.json',d),('g.json',g),('n.json',n)]: (tmp_path/name).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
    out=tmp_path/'out.json'
    run([sys.executable,'tools/fangame_content_infer.py',str(tmp_path/'d.json'),str(tmp_path/'g.json'),str(tmp_path/'n.json'),'--out',str(out)])
    x=json.loads(out.read_text())
    assert x['summary']['sidequest_candidate_maps']==1
    assert x['sidequest_candidates'][0]['map_id']==2
    assert x['summary']['ending_candidate_maps']==1
    assert x['ending_candidates'][0]['map_id']==9
    assert 'not official' in x['summary']['interpretation']

def test_semantics_alone_weak_signal_does_not_overclaim(tmp_path):
    d={'rows':[{'scope':'map','map_id':1,'event_id':1,'page_id':1,'kind':'dialogue','text':'今天的任务很多。'}]}
    g={'switch_reads':{},'switch_writes':{},'variable_reads':{},'variable_writes':{}}
    n={'leaf_maps':[],'isolated_maps':[],'branching_maps':[]}
    for name,obj in [('d.json',d),('g.json',g),('n.json',n)]: (tmp_path/name).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
    out=tmp_path/'out.json'
    run([sys.executable,'tools/fangame_content_infer.py',str(tmp_path/'d.json'),str(tmp_path/'g.json'),str(tmp_path/'n.json'),'--out',str(out)])
    x=json.loads(out.read_text())
    assert x['summary']['sidequest_candidate_maps']==0
