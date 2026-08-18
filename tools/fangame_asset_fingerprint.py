#!/usr/bin/env python3
import argparse, hashlib, json
from collections import Counter, defaultdict
from pathlib import Path

IMAGE_EXTS={'.png','.jpg','.jpeg','.bmp','.gif','.webp'}
AUDIO_EXTS={'.ogg','.mp3','.wav','.wma','.mid','.midi','.m4a','.opus'}

def sha256_file(p, chunk=1024*1024):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while True:
            b=f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def classify_path(p: Path):
    low='/'.join(x.lower() for x in p.parts)
    if any(x in low for x in ('graphics/characters','graphics/tilesets','graphics/autotiles','graphics/system','graphics/windowskins','graphics/icons')):
        return 'engine_asset_like'
    if 'graphics/pictures' in low or 'graphics/battlers' in low or 'graphics/faces' in low or 'graphics/parallaxes' in low:
        return 'content_art_like'
    if 'audio/' in low:
        return 'audio'
    return 'other'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('game_root'); ap.add_argument('--out',default='asset_fingerprint.json'); a=ap.parse_args()
    root=Path(a.game_root).resolve(); rows=[]; by_hash=defaultdict(list); ext_counts=Counter(); class_counts=Counter(); total_bytes=0
    for p in root.rglob('*'):
        if not p.is_file(): continue
        ext=p.suffix.lower()
        if ext not in IMAGE_EXTS|AUDIO_EXTS: continue
        try:
            size=p.stat().st_size; digest=sha256_file(p)
        except OSError:
            continue
        rel=str(p.relative_to(root)).replace('\\','/')
        kind='image' if ext in IMAGE_EXTS else 'audio'; cls=classify_path(Path(rel))
        row={'path':rel,'kind':kind,'ext':ext,'bytes':size,'sha256':digest,'path_class':cls}
        rows.append(row); by_hash[digest].append(rel); ext_counts[ext]+=1; class_counts[cls]+=1; total_bytes+=size
    dup_groups=[{'sha256':h,'count':len(paths),'paths':paths} for h,paths in by_hash.items() if len(paths)>1]
    duplicate_member_files=sum(g['count'] for g in dup_groups)
    unique=len(by_hash); files=len(rows); duplicate_extra_copies=max(0,files-unique)
    summary={
        'asset_files':files,'asset_bytes':total_bytes,'unique_content_hashes':unique,
        'exact_duplicate_groups':len(dup_groups),'exact_duplicate_member_files':duplicate_member_files,
        'exact_duplicate_extra_copies':duplicate_extra_copies,
        'exact_reuse_ratio':round(duplicate_extra_copies/files,4) if files else 0.0,
        'extension_counts':dict(ext_counts),'path_class_counts':dict(class_counts),
        'originality_note':'This stage measures exact in-package reuse and path classes only. It does NOT claim true originality without an external RTP/reference corpus or perceptual-near-duplicate pass.'
    }
    out={'schema':'fangame-asset-fingerprint-v2','summary':summary,'duplicate_groups':dup_groups,'assets':rows}
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
