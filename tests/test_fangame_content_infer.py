import json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run(cmd): return subprocess.run(cmd,cwd=ROOT,check=True,text=True,capture_output=True)

def write_inputs(tmp_path,d,g,n):
    for name,obj in [('d.json',d),('g.json',g),('n.json',n)]:
        (tmp_path/name).write_text(json.dumps(obj,ensure_ascii=False),encoding='utf-8')
    out=tmp_path/'out.json'
    run([sys.executable,'tools/fangame_content_infer.py',str(tmp_path/'d.json'),str(tmp_path/'g.json'),str(tmp_path/'n.json'),'--out',str(out)])
    return json.loads(out.read_text())

def row(mid,eid,pid,text,conditions=None):
    return {'scope':'map','map_id':mid,'event_id':eid,'page_id':pid,'kind':'dialogue','conditions':conditions or {},'text':text}

def test_sidequest_and_ending_candidates(tmp_path):
    d={'rows':[
      row(2,1,1,'请你帮我寻找三朵花，完成后我会给你奖励。'),
      row(9,3,1,'终章：故事终于结束。THE END'),
    ]}
    g={'switch_reads':{'5':[{'map_id':2}]},'switch_writes':{'5':[{'map_id':2}]},'variable_reads':{},'variable_writes':{}}
    n={'leaf_maps':[2,9],'isolated_maps':[],'branching_maps':[]}
    x=write_inputs(tmp_path,d,g,n)
    assert x['summary']['sidequest_candidate_maps']==1
    assert x['sidequest_candidates'][0]['map_id']==2
    assert x['summary']['ending_candidate_maps']==1
    assert x['ending_candidates'][0]['map_id']==9
    assert 'not official' in x['summary']['interpretation']

def test_semantics_alone_weak_signal_does_not_overclaim(tmp_path):
    d={'rows':[row(1,1,1,'今天的任务很多。')]}
    g={'switch_reads':{},'switch_writes':{},'variable_reads':{},'variable_writes':{}}
    n={'leaf_maps':[],'isolated_maps':[],'branching_maps':[]}
    x=write_inputs(tmp_path,d,g,n)
    assert x['summary']['sidequest_candidate_maps']==0

def test_factorizes_explicit_mainline_optional_and_unfinished_endpoint(tmp_path):
    d={'rows':[
      row(8,1,1,'罗宾：帮我找找约翰。'),
      row(8,1,1,'接受任务 寻找约翰'),
      row(8,1,2,'罗宾：快去帮我找找他啊。',{'self_switch_ch':'A'}),
      row(8,1,3,'寻找约翰任务完成 奖励经验300 金钱1000',{'switch1_id':6}),
      row(27,8,1,'怒龙：约翰，赶紧回去吧。',{'switch1_id':5}),
      row(35,3,1,'镇长：请你帮我寻找并消灭地下敌人，成功后给你宠物，希望对你救国王有帮助。'),
      row(31,25,1,'传说神兽大地精灵隐藏在沙漠，运气好就可能找到它的宠物蛋。'),
      row(42,16,1,'传说凤凰的羽毛散落在沙漠，我要努力寻找。'),
      row(122,2,1,'作者留言：这部游戏到这里还没有结束，寒假的时候还会继续更新。'),
    ]}
    g={
      'switch_reads':{
        '6':[{'map_id':8,'event_id':1,'page_id':3,'source':'page_condition'}],
        '5':[{'map_id':27,'event_id':8,'page_id':1,'source':'page_condition'}],
        '11':[{'map_id':35,'event_id':3,'page_id':2,'source':'page_condition'}],
        '22':[{'map_id':31,'event_id':25,'page_id':1,'source':'page_condition'}],
        '23':[{'map_id':42,'event_id':16,'page_id':1,'source':'page_condition'}],
      },
      'switch_writes':{
        '5':[{'map_id':8,'event_id':1,'page_id':1,'command_index':7,'value':0}],
        '6':[{'map_id':27,'event_id':8,'page_id':1,'command_index':5,'value':0}],
        '11':[{'map_id':7,'event_id':1,'page_id':1,'command_index':2,'value':0}],
        '22':[{'map_id':15,'event_id':8,'page_id':1,'command_index':2,'value':0}],
        '23':[{'map_id':68,'event_id':2,'page_id':1,'command_index':2,'value':0}],
      },
      'variable_reads':{},'variable_writes':{}
    }
    n={'leaf_maps':[8,35],'isolated_maps':[],'branching_maps':[31,42]}
    x=write_inputs(tmp_path,d,g,n)
    classes={c['map_id']:c['semantic_class'] for c in x['sidequest_candidates']}
    assert classes[8]=='SIDEQUEST_EXPLICIT'
    assert classes[35]=='MAINLINE_GATE'
    assert classes[31]=='OPTIONAL_CONTENT'
    assert classes[42]=='OPTIONAL_CONTENT'
    assert x['summary']['explicit_sidequest_maps']==1
    assert x['summary']['mainline_gate_maps']==1
    assert x['summary']['optional_content_maps']==2
    assert x['summary']['content_endpoint_maps']==1
    assert x['summary']['release_completion_status']=='UNFINISHED_CONTENT_ENDPOINT'
    assert x['summary']['ending_candidate_maps']==0
    assert x['explicit_sidequest_candidates'][0]['completion_switches']['6'][0]['map_id']==27
