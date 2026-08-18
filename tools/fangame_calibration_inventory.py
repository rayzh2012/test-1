#!/usr/bin/env python3
import argparse, json
from collections import defaultdict
from pathlib import Path

INVENTORY_VERSION='fangame.calibration.inventory.v0.7'
DIMS=['required_repetition','level_pressure','economy_pressure','encounter_intrusion','recovery_penalty','overall_grind_burden']
KNOWN={'VERY_LOW','LOW','MEDIUM','HIGH','VERY_HIGH'}

def read_ndjson(path):
    if not path or not Path(path).exists(): return []
    out=[]
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if line and not line.startswith('#'): out.append(json.loads(line))
    return out

def game_id(rec):
    ident=rec.get('identity') or {}
    return ident.get('game_id') or (f"sha256:{ident.get('sha256')}" if ident.get('sha256') else None)

def label_value(rec,dim):
    obj=rec.get('overall_grind_burden') if dim=='overall_grind_burden' else (rec.get('dimensions') or {}).get(dim)
    return obj.get('value') if isinstance(obj,dict) else None

def active_labels(labels):
    by_id={x.get('label_id'):x for x in labels if x.get('label_id')}
    superseded={((x.get('audit') or {}).get('supersedes_label_id')) for x in labels}
    superseded.discard(None)
    return [x for x in by_id.values() if x.get('label_id') not in superseded]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--features',required=True,help='Flattened source is NOT accepted; use canonical Feature Store NDJSON records.')
    ap.add_argument('--labels',required=False)
    ap.add_argument('--out',default='fangame_calibration_inventory.json')
    a=ap.parse_args()
    features=read_ndjson(a.features); labels=active_labels(read_ndjson(a.labels))

    f_by={}
    for rec in features:
        gid=game_id(rec)
        if gid: f_by[gid]=rec
    l_by=defaultdict(list)
    for lab in labels:
        if lab.get('game_id'): l_by[lab['game_id']].append(lab)

    rows=[]
    for gid in sorted(set(f_by)|set(l_by)):
        f=f_by.get(gid); labs=l_by.get(gid,[])
        ident=(f or {}).get('identity') or {}
        gv=(f or {}).get('grind_vector') or {}
        groups=sorted({(x.get('evidence_source') or {}).get('independence_group') for x in labs if (x.get('evidence_source') or {}).get('independence_group')})
        source_types=sorted({(x.get('evidence_source') or {}).get('source_type') for x in labs if (x.get('evidence_source') or {}).get('source_type')})
        known_dims=[]; unknown_dims=[]; conflicts={}
        for d in DIMS:
            vals=sorted({label_value(x,d) for x in labs if label_value(x,d) in KNOWN})
            if vals: known_dims.append(d)
            else: unknown_dims.append(d)
            if len(vals)>1: conflicts[d]=vals
        rows.append({
          'game_id':gid,
          'title':ident.get('title') or (labs[0].get('game_title') if labs else None),
          'feature_record_present':f is not None,
          'feature_schema':(f or {}).get('schema_version'),
          'grind_vector_status':gv.get('status') if f else 'VECTOR_RECORD_MISSING',
          'grind_vector_version':gv.get('vector_version') if f else None,
          'grind_vector_coverage':gv.get('coverage') if f else None,
          'active_label_count':len(labs),
          'independence_group_count':len(groups),
          'independence_groups':groups,
          'source_types':source_types,
          'known_dimension_count':len(known_dims),
          'known_dimension_coverage':round(len(known_dims)/len(DIMS),4),
          'unknown_dimensions':unknown_dims,
          'conflicting_dimensions':conflicts,
          'conflicting_dimension_count':len(conflicts),
        })
    result={
      'inventory_version':INVENTORY_VERSION,
      'feature_records_seen':len(features),'active_labels_seen':len(labels),'games':rows,
      'fact_policy':'This file contains acquisition facts only. It does not choose what to review next and contains no priority weights.'
    }
    Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
