#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path
from PIL import Image

IMAGE_EXTS={'.png','.jpg','.jpeg','.bmp','.gif','.webp'}

def dhash(path, hash_size=8):
    with Image.open(path) as im:
        im=im.convert('L').resize((hash_size+1,hash_size))
        px=list(im.getdata())
        bits=0
        for y in range(hash_size):
            row=y*(hash_size+1)
            for x in range(hash_size):
                bits=(bits<<1) | (1 if px[row+x] > px[row+x+1] else 0)
        return bits, im.size

def hamming(a,b): return (a^b).bit_count()

def aspect_close(a,b,tol=0.03):
    aw,ah=a; bw,bh=b
    if not ah or not bh: return False
    return abs((aw/ah)-(bw/bh)) <= tol*max(aw/ah,bw/bh,1e-9)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('game_root'); ap.add_argument('--out',required=True)
    ap.add_argument('--threshold',type=int,default=6)
    a=ap.parse_args(); root=Path(a.game_root).resolve(); rows=[]; errors=[]
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.suffix.lower() not in IMAGE_EXTS: continue
        try:
            with Image.open(p) as src: orig_size=src.size
            hv,_=dhash(p)
            rows.append({'path':str(p.relative_to(root)).replace('\\','/'),'width':orig_size[0],'height':orig_size[1],'dhash64':f'{hv:016x}'})
        except Exception as e:
            errors.append({'path':str(p.relative_to(root)).replace('\\','/'),'error':type(e).__name__})
    parent=list(range(len(rows)))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]; x=parent[x]
        return x
    def union(a,b):
        ra,rb=find(a),find(b)
        if ra!=rb: parent[rb]=ra
    near_pairs=[]
    ints=[int(r['dhash64'],16) for r in rows]
    for i in range(len(rows)):
        si=(rows[i]['width'],rows[i]['height'])
        for j in range(i+1,len(rows)):
            sj=(rows[j]['width'],rows[j]['height'])
            if not aspect_close(si,sj): continue
            d=hamming(ints[i],ints[j])
            if d<=a.threshold:
                union(i,j); near_pairs.append({'a':rows[i]['path'],'b':rows[j]['path'],'hamming':d})
    groups={}
    for i,r in enumerate(rows): groups.setdefault(find(i),[]).append(r['path'])
    clusters=[{'count':len(v),'paths':v} for v in groups.values() if len(v)>1]
    clustered=sum(len(c['paths']) for c in clusters)
    summary={'image_files':len(rows),'near_duplicate_pairs':len(near_pairs),'near_duplicate_clusters':len(clusters),
             'cluster_member_files':clustered,'threshold_hamming':a.threshold,'decode_errors':len(errors),
             'interpretation':'Perceptual proximity indicates visual similarity, not common authorship or RTP identity. Exact reference matching remains a separate evidence layer.'}
    out={'schema':'fangame-perceptual-hash-v1','summary':summary,'clusters':clusters,'near_pairs':near_pairs,'images':rows,'errors':errors}
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
