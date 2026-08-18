#!/usr/bin/env python3
import json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/'tools/fangame_grind_corpus_audit.py'
SCHEMA=ROOT/'schemas/fangame_grind_label_v05c.schema.json'

def score(v,c=.8,n='evidence'):
    return {'value':v,'confidence':c,'evidence_summary':n}

def row(lid,gid,src,group,overall='LOW',enc='LOW',sup=None,stype='HISTORICAL_PLAYER_REVIEW'):
    return {
      'schema_version':'fangame.grind.label.v0.5c','label_id':lid,'game_id':gid,'game_title':gid,
      'feature_vector_version':'fangame.grind.vector.v0.5b',
      'evidence_source':{'source_id':src,'source_type':stype,'independence_group':group,'source_url':None,'source_date':None,'evidence_summary':'synthetic regression evidence'},
      'annotation':{'annotator_type':'SOURCE_EXTRACTION','coverage':'MIXED','direct_play_observation':False,'notes':'synthetic'},
      'dimensions':{
        'required_repetition':score('LOW'),'level_pressure':score('LOW'),'economy_pressure':score('VERY_LOW'),
        'encounter_intrusion':score(enc),'recovery_penalty':score('UNKNOWN',0,'not observed')},
      'overall_grind_burden':score(overall),
      'audit':{'created_at_utc':'2026-08-18T00:00:00Z','label_contract_version':'0.5c.0','supersedes_label_id':sup}}

def write(path,rows):
    path.write_text('\n'.join(json.dumps(x) for x in rows)+('\n' if rows else ''),encoding='utf-8')

def run(src,out,rc=0):
    p=subprocess.run([sys.executable,str(AUDIT),'--labels',str(src),'--schema',str(SCHEMA),'--out',str(out)],cwd=ROOT)
    assert p.returncode==rc,(p.returncode,rc)
    return json.loads(out.read_text(encoding='utf-8'))

def main():
  with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    rows=[
      row('a-old','game-a','review-old','pub-a',overall='MEDIUM',enc='MEDIUM'),
      row('a-new','game-a','review-new','pub-a',overall='LOW',enc='LOW',sup='a-old'),
      row('a-guide','game-a','guide-a','guide-a',overall='LOW',enc='MEDIUM',stype='WALKTHROUGH_GUIDE'),
      row('b-review','game-b','review-b','pub-b',overall='HIGH',enc='HIGH')]
    src=td/'labels.ndjson'; out=td/'audit.json'; write(src,rows); a=run(src,out)
    assert a['corpus_status']=='CORPUS_VALID_UNGATED'
    assert a['records_seen']==4 and a['active_label_records']==3
    assert a['superseded_label_ids']==['a-old']
    assert a['distinct_games']==2 and a['distinct_independence_groups']==3
    assert a['dimension_value_counts']['overall_grind_burden']=={'HIGH':1,'LOW':2}
    assert a['games_with_conflicting_active_labels']==1
    pa={x['game_id']:x for x in a['game_profiles']}['game-a']
    assert pa['active_label_count']==2 and pa['independent_evidence_groups']==2
    assert pa['conflicting_dimensions']['encounter_intrusion']==['LOW','MEDIUM']
    assert a['training_gate']['status']=='NOT_EVALUATED'
    assert a['model_outputs']=={'weights_emitted':False,'grind_score_emitted':False,'playtime_estimate_emitted':False}

    empty=td/'empty.ndjson'; write(empty,[]); e=run(empty,td/'empty.json')
    assert e['corpus_status']=='CORPUS_EMPTY' and e['active_label_records']==0

    dup=td/'dup.ndjson'; write(dup,[rows[1],rows[1]]); d=run(dup,td/'dup.json',2)
    assert d['corpus_status']=='CORPUS_INVALID' and d['duplicate_label_ids']==['a-new']

    cross=td/'cross.ndjson'; write(cross,[row('x','x','x','x'),row('y','y','y','y',sup='x')])
    c=run(cross,td/'cross.json',2)
    assert c['supersession_errors'][0]['error']=='SUPERSESSION_CROSSES_GAME_ID'
  print('fangame grind calibration corpus v0.5c governance: PASS')

if __name__=='__main__': main()
