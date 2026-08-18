#!/usr/bin/env python3
import argparse, json
from collections import defaultdict
from pathlib import Path


def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def hamming_hex(a,b): return (int(a,16)^int(b,16)).bit_count()
def aspect_close(a,b,tol=0.03):
    aw,ah=a; bw,bh=b
    if not ah or not bh: return False
    ar=aw/ah; br=bw/bh
    return abs(ar-br) <= tol*max(ar,br,1e-9)
def category_from_path(path):
    parts=[x.lower() for x in Path(path or '').parts]
    for root in ('graphics','audio'):
        idxs=[i for i,x in enumerate(parts) if x==root]
        if idxs:
            i=idxs[-1]; return root + ('/'+parts[i+1] if i+1<len(parts) else '')
    return 'other'
def basename(path): return Path(path or '').name.lower()


def main():
    ap=argparse.ArgumentParser(description='Fuse exact reference hashes with conservative perceptual RTP-like evidence')
    ap.add_argument('asset_fingerprint'); ap.add_argument('perceptual_hash'); ap.add_argument('reference',nargs='+')
    ap.add_argument('--threshold',type=int,default=4); ap.add_argument('--aspect-tolerance',type=float,default=0.03); ap.add_argument('--out',required=True)
    a=ap.parse_args(); game=load(a.asset_fingerprint); ph=load(a.perceptual_hash)
    game_ph={x['path']:x for x in ph.get('images',[]) if x.get('dhash64')}
    by_sha=defaultdict(list); ref_images=defaultdict(list); refs=[]
    for rp in a.reference:
        r=load(rp); refs.append(r)
        for x in r.get('assets',[]):
            hit={'engine':r.get('engine'),'rtp_version':r.get('rtp_version'),'reference_path':x.get('relative_path')}
            by_sha[x.get('sha256')].append(hit)
            if x.get('dhash64'):
                cat=x.get('asset_category') or category_from_path(x.get('relative_path'))
                ref_images[cat].append({**hit,'dhash64':x['dhash64'],'width':x.get('width'),'height':x.get('height')})

    rows=[]; exact=exact_bytes=near=near_bytes=near_high=near_medium=0; unmatched=unmatched_bytes=0; image_nonexact=0
    for x in game.get('assets',[]):
        path=x.get('path'); size=int(x.get('bytes') or 0); sha=x.get('sha256'); hits=by_sha.get(sha,[])
        if hits:
            exact+=1; exact_bytes+=size
            rows.append({'path':path,'bytes':size,'sha256':sha,'classification':'REFERENCE_EXACT_MATCH','confidence':'HIGH','reference_hits':hits}); continue
        gp=game_ph.get(path); best=None
        if gp:
            image_nonexact+=1; cat=category_from_path(path); gs=(int(gp.get('width') or 0),int(gp.get('height') or 0))
            for rr in ref_images.get(cat,[]):
                rs=(int(rr.get('width') or 0),int(rr.get('height') or 0))
                if not aspect_close(gs,rs,a.aspect_tolerance): continue
                d=hamming_hex(gp['dhash64'],rr['dhash64']); same_name=basename(path)==basename(rr['reference_path'])
                candidate={**rr,'hamming':d,'same_dimensions':gs==rs,'same_basename':same_name,'asset_category':cat}
                if best is None or (same_name,d)>(best['same_basename'],-best['hamming']): best=candidate
        if best is not None and best['hamming']<=a.threshold:
            near+=1; near_bytes+=size; conf='HIGH' if best['same_basename'] else 'MEDIUM'
            near_high += conf=='HIGH'; near_medium += conf=='MEDIUM'
            rows.append({'path':path,'bytes':size,'sha256':sha,'classification':'MODIFIED_RTP_LIKE','confidence':conf,'perceptual_reference_hit':best,
                         'warning':'Same-category perceptual similarity supports RTP-like derivation. Same basename strengthens the evidence; neither level proves authorship.'})
        else:
            unmatched+=1; unmatched_bytes+=size
            rows.append({'path':path,'bytes':size,'sha256':sha,'classification':'NO_REFERENCE_SIMILARITY_FOUND','confidence':'UNKNOWN','warning':'No exact or thresholded perceptual reference match does not prove originality.'})

    n=len(rows); total_bytes=sum(int(x.get('bytes') or 0) for x in game.get('assets',[]))
    out={'schema':'fangame-asset-reference-fusion-v2','references':[{'engine':r.get('engine'),'rtp_version':r.get('rtp_version'),'package_sha256':r.get('package_sha256'),'asset_files':r.get('asset_files'),'image_perceptual_signatures':r.get('image_perceptual_signatures')} for r in refs],
      'parameters':{'perceptual_hash':'dHash64','hamming_threshold':a.threshold,'aspect_tolerance':a.aspect_tolerance,'category_gate':True,'same_basename_strengthens_confidence':True},
      'summary':{'game_asset_files':n,'game_asset_bytes':total_bytes,'exact_reference_match_files':exact,'exact_reference_match_ratio_files':round(exact/n,4) if n else 0.0,'exact_reference_match_bytes':exact_bytes,'exact_reference_match_ratio_bytes':round(exact_bytes/total_bytes,4) if total_bytes else 0.0,'nonexact_game_images_with_dhash':image_nonexact,'modified_rtp_like_files':near,'modified_rtp_like_high_confidence_files':near_high,'modified_rtp_like_medium_confidence_files':near_medium,'modified_rtp_like_ratio_files':round(near/n,4) if n else 0.0,'modified_rtp_like_bytes':near_bytes,'modified_rtp_like_ratio_bytes':round(near_bytes/total_bytes,4) if total_bytes else 0.0,'no_reference_similarity_files':unmatched,'no_reference_similarity_bytes':unmatched_bytes,'rtp_supported_files_union':exact+near,'rtp_supported_ratio_files_union':round((exact+near)/n,4) if n else 0.0,'warning':'Exact match is strong reference evidence. Same-category + same-basename + near-dHash MODIFIED_RTP_LIKE is HIGH similarity evidence; different-basename near matches are MEDIUM. Neither proves authorship. NO_REFERENCE_SIMILARITY_FOUND leaves originality UNKNOWN.'},'assets':rows}
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(out['summary'],ensure_ascii=False,indent=2))
if __name__=='__main__': main()
