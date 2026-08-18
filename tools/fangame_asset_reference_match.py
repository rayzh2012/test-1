#!/usr/bin/env python3
import argparse, json
from collections import Counter, defaultdict


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('asset_fingerprint')
    ap.add_argument('reference', nargs='+')
    ap.add_argument('--out', required=True)
    a=ap.parse_args()
    game=json.load(open(a.asset_fingerprint,encoding='utf-8'))
    refs=[]; by_hash=defaultdict(list)
    for rp in a.reference:
        r=json.load(open(rp,encoding='utf-8')); refs.append(r)
        for x in r.get('assets',[]):
            by_hash[x['sha256']].append({'engine':r.get('engine'),'rtp_version':r.get('rtp_version'),'reference_path':x.get('relative_path')})
    rows=[]; matched=0; matched_bytes=0; total_bytes=0; class_counts=Counter()
    for x in game.get('assets',[]):
        total_bytes += int(x.get('bytes') or 0)
        hits=by_hash.get(x.get('sha256'),[])
        cls='REFERENCE_EXACT_MATCH' if hits else 'NO_EXACT_REFERENCE_MATCH'
        class_counts[cls]+=1
        if hits:
            matched+=1; matched_bytes+=int(x.get('bytes') or 0)
        rows.append({'path':x.get('path'),'sha256':x.get('sha256'),'bytes':x.get('bytes'),'classification':cls,'reference_hits':hits})
    n=len(rows)
    out={
      'schema':'fangame-asset-reference-match-v1',
      'references':[{'engine':r.get('engine'),'rtp_version':r.get('rtp_version'),'package_sha256':r.get('package_sha256'),'asset_files':r.get('asset_files')} for r in refs],
      'summary':{
        'game_asset_files':n,'game_asset_bytes':total_bytes,
        'exact_reference_match_files':matched,
        'exact_reference_match_ratio_files':round(matched/n,4) if n else 0.0,
        'exact_reference_match_bytes':matched_bytes,
        'exact_reference_match_ratio_bytes':round(matched_bytes/total_bytes,4) if total_bytes else 0.0,
        'no_exact_reference_match_files':n-matched,
        'warning':'NO_EXACT_REFERENCE_MATCH means only absent from the supplied exact-hash reference corpus. It does not prove originality.'
      },
      'assets':rows
    }
    json.dump(out,open(a.out,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps(out['summary'],ensure_ascii=False,indent=2))

if __name__=='__main__': main()
