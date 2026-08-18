#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path

IMAGE_EXTS={'.png','.jpg','.jpeg','.bmp','.gif','.webp'}
AUDIO_EXTS={'.ogg','.mp3','.wav','.wma','.mid','.midi','.m4a','.opus'}

def sha256_file(p, chunk=1024*1024):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(chunk), b''):
            h.update(b)
    return h.hexdigest()

def build(root, engine, source_label, provenance):
    root=Path(root).resolve(); rows=[]; total=0
    for p in sorted(root.rglob('*')):
        if not p.is_file(): continue
        ext=p.suffix.lower()
        if ext not in IMAGE_EXTS|AUDIO_EXTS: continue
        rel=str(p.relative_to(root)).replace('\\','/')
        size=p.stat().st_size; total += size
        rows.append({'path':rel,'filename':p.name,'ext':ext,'bytes':size,'sha256':sha256_file(p),
                     'kind':'image' if ext in IMAGE_EXTS else 'audio'})
    return {
      'schema':'fangame-reference-manifest-v1',
      'engine':engine,
      'source_label':source_label,
      'provenance':provenance,
      'summary':{'reference_files':len(rows),'reference_bytes':total},
      'files':rows,
      'policy_note':'Manifest contains fingerprints/metadata only. Do not publish or archive proprietary reference binaries unless separately permitted.'
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('reference_root')
    ap.add_argument('--engine',required=True)
    ap.add_argument('--source-label',required=True)
    ap.add_argument('--provenance',default='local lawful reference installation')
    ap.add_argument('--out',required=True)
    a=ap.parse_args()
    out=build(a.reference_root,a.engine,a.source_label,a.provenance)
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out['summary'],ensure_ascii=False))
if __name__=='__main__': main()
