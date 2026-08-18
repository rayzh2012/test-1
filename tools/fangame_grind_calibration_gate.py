#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

GATE_VERSION="fangame.grind.calibration.gate.v0.5d"
DIMS=['required_repetition','level_pressure','economy_pressure','encounter_intrusion','recovery_penalty','overall_grind_burden']

def load(path): return json.loads(Path(path).read_text(encoding='utf-8'))

def rule(name,actual,required,op='>='):
    if op=='>=': passed=actual>=required
    elif op=='<=': passed=actual<=required
    else: raise ValueError(op)
    return {'rule':name,'actual':actual,'operator':op,'required':required,'passed':passed}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--audit',required=True)
    ap.add_argument('--policy',required=True)
    ap.add_argument('--policy-schema',default='schemas/fangame_grind_calibration_policy_v05d.schema.json')
    ap.add_argument('--out',default='fangame_grind_calibration_gate.json')
    a=ap.parse_args()
    audit=load(a.audit); policy=load(a.policy); schema=load(a.policy_schema)
    try:
        import jsonschema
        jsonschema.validate(policy,schema)
    except ImportError:
        pass

    req=policy['requirements']; profiles=audit.get('game_profiles') or []
    distinct_games=int(audit.get('distinct_games') or 0)
    active=int(audit.get('active_label_records') or 0)
    groups=int(audit.get('distinct_independence_groups') or 0)
    multi_source=sum(1 for x in profiles if int(x.get('independent_evidence_groups') or 0)>=2)
    conflicts=int(audit.get('games_with_conflicting_active_labels') or 0)
    conflict_ratio=(conflicts/distinct_games) if distinct_games else 0.0
    source_types=sum(1 for _,n in (audit.get('source_type_counts') or {}).items() if n)
    coverage=audit.get('annotation_coverage_counts') or {}
    mixed_full=int(coverage.get('MIXED') or 0)+int(coverage.get('FULL_PLAYTHROUGH') or 0)
    counts=audit.get('dimension_value_counts') or {}

    rules=[
      rule('min_distinct_games',distinct_games,req['min_distinct_games']),
      rule('min_active_labels',active,req['min_active_labels']),
      rule('min_distinct_independence_groups',groups,req['min_distinct_independence_groups']),
      rule('min_games_with_multiple_independent_groups',multi_source,req['min_games_with_multiple_independent_groups']),
      rule('max_conflicting_game_ratio',round(conflict_ratio,6),req['max_conflicting_game_ratio'],'<='),
      rule('min_mixed_or_full_coverage_labels',mixed_full,req.get('min_mixed_or_full_coverage_labels',0)),
      rule('min_distinct_source_types',source_types,req.get('min_distinct_source_types',1)),
    ]
    for dim in DIMS:
        known=sum(int(n) for value,n in (counts.get(dim) or {}).items() if value!='UNKNOWN')
        rules.append(rule(f'min_known_labels:{dim}',known,req['min_known_labels_per_dimension'][dim]))
    overall_values=sum(1 for value,n in (counts.get('overall_grind_burden') or {}).items() if value!='UNKNOWN' and int(n)>0)
    rules.append(rule('min_distinct_overall_burden_values',overall_values,req['min_distinct_overall_burden_values']))

    corpus_valid=audit.get('corpus_status')=='CORPUS_VALID_UNGATED'
    passed=corpus_valid and all(x['passed'] for x in rules)
    out={
      'gate_version':GATE_VERSION,
      'policy_id':policy['policy_id'],
      'policy_version':policy['audit']['policy_version'],
      'source_corpus_audit_version':audit.get('audit_version'),
      'source_corpus_status':audit.get('corpus_status'),
      'status':'POLICY_GATE_PASSED' if passed else 'POLICY_GATE_FAILED',
      'rules':rules,
      'failed_rules':[x['rule'] for x in rules if not x['passed']],
      'permissions':{
        'fit_experiment_permitted':passed,
        'production_grind_score_authorized':False,
        'playtime_model_authorized':False
      },
      'next_stage':(
        'MODEL_FIT_AND_HELD_OUT_EVALUATION_ONLY' if passed else 'COLLECT_OR_REVIEW_CALIBRATION_EVIDENCE'
      ),
      'note':'Passing this gate permits model-fitting experiments only. It never authorizes production scores; model evaluation/deployment requires a later independent policy gate.'
    }
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
    return 0 if passed else 3

if __name__=='__main__': raise SystemExit(main())
