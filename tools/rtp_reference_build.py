#!/usr/bin/env python3
"""Build a hash-only RPG Maker RTP reference index from official downloads.

The RTP binaries/assets are temporary inputs only. This tool does NOT redistribute RTP
content. It emits package provenance plus hashes/relative paths for reference matching.
Use only official URLs and comply with the publisher's RTP terms.
"""
import argparse, hashlib, json, os, shutil, subprocess, tempfile, urllib.request
from pathlib import Path

ASSET_EXTS={'.png','.jpg','.jpeg','.bmp','.gif','.ogg','.mp3','.wav','.wma','.mid','.midi'}
OFFICIAL={
 'vxace': {'engine':'RPG Maker VX Ace','url':'https://cdn.tkool.jp/updata/rtp/vxace_rtp100.zip','version':'1.00'},
 'vx': {'engine':'RPG Maker VX','url':'https://cdn.tkool.jp/updata/rtp/vx_rtp202.zip','version':'2.02'},
 'xp': {'engine':'RPG Maker XP','url':'https://cdn.tkool.jp/updata/rtp/xp_rtp103.zip','version':'1.03'},
}

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def fetch(url,dst):
    req=urllib.request.Request(url,headers={'User-Agent':'FangameGenome/1.0'})
    with urllib.request.urlopen(req,timeout=120) as r, open(dst,'wb') as f:
        shutil.copyfileobj(r,f)

def run7z(src,out):
    Path(out).mkdir(parents=True,exist_ok=True)
    p=subprocess.run(['7z','x','-y',f'-o{out}',str(src)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    return p.returncode,p.stdout[-4000:]

def recursive_extract(root, max_depth=2):
    logs=[]
    for depth in range(max_depth):
        candidates=[]
        for p in Path(root).rglob('*'):
            if not p.is_file(): continue
            if p.suffix.lower() in {'.exe','.msi','.cab','.zip','.7z'}:
                candidates.append(p)
        new=0
        for p in candidates:
            marker=p.with_name(p.name+'.__extracted__')
            if marker.exists(): continue
            out=p.with_name(p.name+'.contents')
            rc,log=run7z(p,out)
            marker.write_text(str(rc),encoding='utf-8')
            logs.append({'file':str(p.relative_to(root)),'rc':rc,'log_tail':log})
            if rc==0: new+=1
        if new==0: break
    return logs

def build(engine_key,out_path):
    src=OFFICIAL[engine_key]
    with tempfile.TemporaryDirectory(prefix='rtp-ref-') as td:
        td=Path(td); pkg=td/'rtp.zip'; ext=td/'extract'
        fetch(src['url'],pkg)
        magic=pkg.read_bytes()[:4]
        if magic[:2] != b'PK': raise RuntimeError('official download is not ZIP')
        pkg_hash=sha256_file(pkg); pkg_size=pkg.stat().st_size
        rc,log=run7z(pkg,ext)
        if rc: raise RuntimeError('outer ZIP extract failed: '+log)
        nested=recursive_extract(ext)
        assets=[]
        for p in ext.rglob('*'):
            if p.is_file() and p.suffix.lower() in ASSET_EXTS:
                try:
                    rel=str(p.relative_to(ext)).replace('\\','/')
                    assets.append({'relative_path':rel,'bytes':p.stat().st_size,'sha256':sha256_file(p),'ext':p.suffix.lower()})
                except OSError: pass
        hashes={}
        for a in assets: hashes.setdefault(a['sha256'],[]).append(a['relative_path'])
        out={
          'schema':'rpgmaker-rtp-reference-v1',
          'engine_key':engine_key,'engine':src['engine'],'rtp_version':src['version'],
          'official_url':src['url'],'official_terms_url':'https://rpgmakerofficial.com/support/rtp/',
          'package_bytes':pkg_size,'package_sha256':pkg_hash,
          'asset_files':len(assets),'unique_asset_hashes':len(hashes),
          'assets':assets,
          'nested_extract_log':nested,
          'redistribution_policy':'HASH_ONLY_OUTPUT; RTP binary/assets are not stored or redistributed by this tool.'
        }
        Path(out_path).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:out[k] for k in ['engine','rtp_version','package_bytes','package_sha256','asset_files','unique_asset_hashes']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('engine',choices=OFFICIAL); ap.add_argument('--out',required=True)
    a=ap.parse_args(); build(a.engine,a.out)
