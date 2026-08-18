#!/usr/bin/env python3
import json,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
INV=ROOT/'tools/fangame_calibration_inventory.py'; QUEUE=ROOT/'tools/fangame_calibration_acquisition_queue.py'; SCHEMA=ROOT/'schemas/fangame_calibration_acquisition_policy_v07.schema.json'
DIMS=['required_repetition','level_pressure','economy_pressure','encounter_intrusion','recovery_penalty']

def feature(gid,status='VECTOR_READY',coverage=1.0):
 return {'schema_version':'fangame.features.v0.5b','identity':{'game_id':gid,'title':gid},'grind_vector':{'status':status,'vector_version':'fangame.grind.vector.v0.5b' if status=='VECTOR_READY' else None,'coverage':coverage}}
def score(v): return {'value':v,'confidence':.8,'evidence_summary':'test'}
def label(lid,gid,group,overall='LOW',unknown=(),level='LOW'):
 dims={d:score('UNKNOWN' if d in unknown else (level if d=='level_pressure' else 'LOW')) for d in DIMS}
 return {'label_id':lid,'game_id':gid,'game_title':gid,'evidence_source':{'independence_group':group,'source_type':'HUMAN_PLAYTEST'},'dimensions':dims,'overall_grind_burden':score(overall),'audit':{'supersedes_label_id':None}}
def ndjson(path,rows): path.write_text('\n'.join(json.dumps(x) for x in rows)+'\n',encoding='utf-8')
def policy(order=None,vector_required=True):
 return {'schema_version':'fangame.calibration.acquisition.policy.v0.7','policy_id':'test-policy','requirements':{'vector_required_before_labeling':vector_required,'min_independence_groups_per_game':2,'min_known_dimension_coverage':1.0,'conflict_adjudication_enabled':True},'action_order':order or ['BACKFILL_VECTOR','ADJUDICATE_CONFLICT','ADD_FIRST_LABEL','ADD_INDEPENDENT_LABEL','FILL_UNKNOWN_DIMENSIONS','NO_ACTION'],'audit':{'policy_version':'test-1','rationale':'regression'}}
def run(cmd): subprocess.run(cmd,cwd=ROOT,check=True)

def main():
 with tempfile.TemporaryDirectory() as td:
  td=Path(td); features=td/'features.ndjson'; labels=td/'labels.ndjson'; inv=td/'inventory.json'; pol=td/'policy.json'; q=td/'queue.json'
  ndjson(features,[feature('g-backfill','VECTOR_PARTIAL',.4),feature('g-conflict'),feature('g-first'),feature('g-independent'),feature('g-fill'),feature('g-done')])
  ndjson(labels,[
   label('c1','g-conflict','c-a',level='LOW'),label('c2','g-conflict','c-b',level='HIGH'),
   label('i1','g-independent','i-a'),
   label('f1','g-fill','f-a',unknown=('recovery_penalty',)),label('f2','g-fill','f-b',unknown=('recovery_penalty',)),
   label('d1','g-done','d-a'),label('d2','g-done','d-b')])
  run([sys.executable,str(INV),'--features',str(features),'--labels',str(labels),'--out',str(inv)])
  facts=json.loads(inv.read_text()); by={x['game_id']:x for x in facts['games']}
  assert facts['inventory_version']=='fangame.calibration.inventory.v0.7'
  assert by['g-conflict']['conflicting_dimensions']=={'level_pressure':['HIGH','LOW']}
  assert by['g-independent']['independence_group_count']==1
  assert by['g-fill']['unknown_dimensions']==['recovery_penalty'] and by['g-fill']['known_dimension_coverage']==0.8333
  assert by['g-done']['known_dimension_coverage']==1.0

  pol.write_text(json.dumps(policy()),encoding='utf-8')
  run([sys.executable,str(QUEUE),'--inventory',str(inv),'--policy',str(pol),'--policy-schema',str(SCHEMA),'--out',str(q)])
  dec=json.loads(q.read_text()); act={x['game_id']:x['action'] for x in dec['queue']}
  assert act=={'g-backfill':'BACKFILL_VECTOR','g-conflict':'ADJUDICATE_CONFLICT','g-first':'ADD_FIRST_LABEL','g-independent':'ADD_INDEPENDENT_LABEL','g-fill':'FILL_UNKNOWN_DIMENSIONS','g-done':'NO_ACTION'}
  assert dec['action_counts']=={'BACKFILL_VECTOR':1,'ADJUDICATE_CONFLICT':1,'ADD_FIRST_LABEL':1,'ADD_INDEPENDENT_LABEL':1,'FILL_UNKNOWN_DIMENSIONS':1,'NO_ACTION':1}
  assert dec['queue'][0]['game_id']=='g-backfill'

  # Policy changes decision without changing FACT inventory or queue code.
  alt=policy(order=['ADD_FIRST_LABEL','BACKFILL_VECTOR','ADJUDICATE_CONFLICT','ADD_INDEPENDENT_LABEL','FILL_UNKNOWN_DIMENSIONS','NO_ACTION'],vector_required=False)
  pol.write_text(json.dumps(alt),encoding='utf-8')
  run([sys.executable,str(QUEUE),'--inventory',str(inv),'--policy',str(pol),'--policy-schema',str(SCHEMA),'--out',str(q)])
  altq=json.loads(q.read_text()); altact={x['game_id']:x['action'] for x in altq['queue']}
  assert altact['g-backfill']=='ADD_FIRST_LABEL'
  assert altq['queue'][0]['action']=='ADD_FIRST_LABEL'
 print('fangame calibration acquisition v0.7 FACT/POLICY/DECISION: PASS')
if __name__=='__main__': main()
