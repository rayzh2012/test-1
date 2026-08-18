#!/usr/bin/env python3
import argparse, json
from collections import defaultdict
from pathlib import Path

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('asset_fingerprint')
    ap.add_argument('reference_manifest')
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    assets=load(a.asset_fingerprint)
    ref=load(a.reference_manifest)
    by_hash=defaultdict(list)
    for r in ref.get('files',[]): by_hash[r['sha256']].append(r)
    matches=[]; matched_files=0; matched_bytes=0
    for x in assets.get('assets',[]):
        rr=by_hash.get(x.get('sha256'),[])
        if not rr: continue
        matched_files += 1; matched_bytes += int(x.get('bytes',0) or 0)
        matches.append({'game_path':x.get('path'),'sha256':x.get('sha256'),'bytes':x.get('bytes'),
                        'reference_paths':[r.get('path') for r in rr]})
    total_files=assets.get('summary',{}).get('asset_files',len(assets.get('assets',[]))) or 0
    total_bytes=assets.get('summary',{}).get('asset_bytes',sum(int(x.get('bytes',0) or 0) for x in assets.get('assets',[]))) or 0
    summary={
      'reference_engine':ref.get('engine'),'reference_source_label':ref.get('source_label'),
      'exact_reference_match_files':matched_files,
      'exact_reference_match_ratio_files':round(matched_files/total_files,4) if total_files else 0.0,
      'exact_reference_match_bytes':matched_bytes,
      'exact_reference_match_ratio_bytes':round(matched_bytes/total_bytes,4) if total_bytes else 0.0,
      'nonreference_or_modified_files':max(0,total_files-matched_files),
      'interpretation':'Exact hash match means byte-identical to the supplied reference corpus. Non-match does NOT prove originality; it may be modified RTP/default material or unrelated reused content.'
    }
    out={'schema':'fangame-reference-match-v1','summary':summary,'matches':matches}
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
