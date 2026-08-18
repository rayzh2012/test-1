#!/usr/bin/env python3
import argparse,json
from pathlib import Path

QUEUE_VERSION='fangame.calibration.acquisition.queue.v0.7'
ACTIONS=['BACKFILL_VECTOR','ADJUDICATE_CONFLICT','ADD_FIRST_LABEL','ADD_INDEPENDENT_LABEL','FILL_UNKNOWN_DIMENSIONS','NO_ACTION']

def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def choose(g,req):
    vector_ready=g.get('feature_record_present') and g.get('grind_vector_status')=='VECTOR_READY'
    if req['vector_required_before_labeling'] and not vector_ready:
        return 'BACKFILL_VECTOR',['VECTOR_NOT_READY']
    if req['conflict_adjudication_enabled'] and int(g.get('conflicting_dimension_count') or 0)>0:
        return 'ADJUDICATE_CONFLICT',['ACTIVE_LABEL_CONFLICT']
    if int(g.get('active_label_count') or 0)==0:
        return 'ADD_FIRST_LABEL',['NO_ACTIVE_LABELS']
    if int(g.get('independence_group_count') or 0)<int(req['min_independence_groups_per_game']):
        return 'ADD_INDEPENDENT_LABEL',['INSUFFICIENT_INDEPENDENT_EVIDENCE']
    if float(g.get('known_dimension_coverage') or 0)<float(req['min_known_dimension_coverage']):
        return 'FILL_UNKNOWN_DIMENSIONS',['DIMENSION_COVERAGE_BELOW_POLICY']
    return 'NO_ACTION',['POLICY_COVERAGE_SATISFIED']

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--inventory',required=True); ap.add_argument('--policy',required=True); ap.add_argument('--policy-schema',default='schemas/fangame_calibration_acquisition_policy_v07.schema.json'); ap.add_argument('--out',default='fangame_calibration_acquisition_queue.json'); a=ap.parse_args()
    inv=load(a.inventory); policy=load(a.policy)
    try:
      import jsonschema; jsonschema.validate(policy,load(a.policy_schema))
    except ImportError: pass
    req=policy['requirements']; order={name:i for i,name in enumerate(policy['action_order'])}
    rows=[]
    for g in inv.get('games',[]):
      action,reasons=choose(g,req)
      rows.append({
        'game_id':g.get('game_id'),'title':g.get('title'),'action':action,'reason_codes':reasons,
        'facts':{
          'grind_vector_status':g.get('grind_vector_status'),'grind_vector_coverage':g.get('grind_vector_coverage'),
          'active_label_count':g.get('active_label_count'),'independence_group_count':g.get('independence_group_count'),
          'known_dimension_coverage':g.get('known_dimension_coverage'),'unknown_dimensions':g.get('unknown_dimensions'),
          'conflicting_dimensions':g.get('conflicting_dimensions')}
      })
    rows.sort(key=lambda x:(order[x['action']],-int(x['facts'].get('active_label_count') or 0) if x['action']=='ADJUDICATE_CONFLICT' else 0,float(x['facts'].get('known_dimension_coverage') or 0),x.get('title') or x['game_id']))
    for i,row in enumerate(rows,1): row['queue_rank']=i
    result={
      'queue_version':QUEUE_VERSION,'source_inventory_version':inv.get('inventory_version'),'policy_id':policy['policy_id'],'policy_version':policy['audit']['policy_version'],
      'queue':rows,'action_counts':{a:sum(1 for x in rows if x['action']==a) for a in ACTIONS},
      'decision_policy':'Queue actions are policy decisions over inventory facts. The queue never creates labels, changes features, or authorizes model outputs.'}
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
