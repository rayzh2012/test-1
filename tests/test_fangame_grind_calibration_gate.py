#!/usr/bin/env python3
import json, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
GATE=ROOT/'tools/fangame_grind_calibration_gate.py'
SCHEMA=ROOT/'schemas/fangame_grind_calibration_policy_v05d.schema.json'

def audit():
    counts={d:{'LOW':4,'MEDIUM':3,'HIGH':3,'UNKNOWN':1} for d in ['required_repetition','level_pressure','economy_pressure','encounter_intrusion','recovery_penalty','overall_grind_burden']}
    return {
      'audit_version':'fangame.grind.corpus.audit.v0.5c','corpus_status':'CORPUS_VALID_UNGATED',
      'active_label_records':11,'distinct_games':8,'distinct_independence_groups':10,
      'source_type_counts':{'HUMAN_PLAYTEST':4,'HISTORICAL_PLAYER_REVIEW':5,'WALKTHROUGH_GUIDE':2},
      'annotation_coverage_counts':{'MIXED':4,'FULL_PLAYTHROUGH':3,'EARLY_GAME':4},
      'dimension_value_counts':counts,'games_with_conflicting_active_labels':1,
      'game_profiles':[{'game_id':f'g{i}','independent_evidence_groups':2 if i<3 else 1} for i in range(8)]}

def policy(**overrides):
    req={
      'min_distinct_games':8,'min_active_labels':10,'min_distinct_independence_groups':8,
      'min_games_with_multiple_independent_groups':2,
      'min_known_labels_per_dimension':{d:8 for d in ['required_repetition','level_pressure','economy_pressure','encounter_intrusion','recovery_penalty','overall_grind_burden']},
      'min_distinct_overall_burden_values':3,'max_conflicting_game_ratio':0.2,
      'min_mixed_or_full_coverage_labels':6,'min_distinct_source_types':3}
    req.update(overrides)
    return {'schema_version':'fangame.grind.calibration.policy.v0.5d','policy_id':'synthetic-policy','target_label_schema':'fangame.grind.label.v0.5c','target_vector_version':'fangame.grind.vector.v0.5b','requirements':req,'audit':{'policy_version':'test-1','rationale':'synthetic regression policy','approved_by':None,'approved_at_utc':None}}

def run(a,p,out,rc):
    ap=out.parent/'audit.json'; pp=out.parent/'policy.json'
    ap.write_text(json.dumps(a),encoding='utf-8'); pp.write_text(json.dumps(p),encoding='utf-8')
    x=subprocess.run([sys.executable,str(GATE),'--audit',str(ap),'--policy',str(pp),'--policy-schema',str(SCHEMA),'--out',str(out)],cwd=ROOT)
    assert x.returncode==rc,(x.returncode,rc)
    return json.loads(out.read_text(encoding='utf-8'))

def main():
  with tempfile.TemporaryDirectory() as td:
    td=Path(td)
    good=run(audit(),policy(),td/'good.json',0)
    assert good['status']=='POLICY_GATE_PASSED'
    assert good['failed_rules']==[]
    assert good['permissions']['fit_experiment_permitted'] is True
    assert good['permissions']['production_grind_score_authorized'] is False
    assert good['permissions']['playtime_model_authorized'] is False
    assert good['next_stage']=='MODEL_FIT_AND_HELD_OUT_EVALUATION_ONLY'

    strict=run(audit(),policy(min_distinct_games=20),td/'strict.json',3)
    assert strict['status']=='POLICY_GATE_FAILED'
    assert strict['failed_rules']==['min_distinct_games']
    assert strict['permissions']['fit_experiment_permitted'] is False

    invalid=audit(); invalid['corpus_status']='CORPUS_INVALID'
    blocked=run(invalid,policy(),td/'blocked.json',3)
    assert blocked['status']=='POLICY_GATE_FAILED'
    assert blocked['failed_rules']==[]
    assert blocked['permissions']['fit_experiment_permitted'] is False
  print('fangame grind calibration readiness v0.5d: PASS')

if __name__=='__main__': main()
