#!/usr/bin/env python3
import argparse, hashlib, json, os, re
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests

UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'

def sha256(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def valid_head(path, allowed):
    h=open(path,'rb').read(16)
    kinds=[]
    if h.startswith(b'%PDF-'): kinds.append('pdf')
    if h.startswith(b'PK\x03\x04'): kinds.append('zip')
    if h.startswith(b'7z\xbc\xaf\x27\x1c'): kinds.append('7z')
    if h.startswith(b'Rar!\x1a\x07'): kinds.append('rar')
    return next((k for k in kinds if k in allowed),None)

def links(base,text):
    out=[]
    for pat in [r'href=["\']([^"\']+)["\']',r'https?://[^\s"\'<>]+']:
        for m in re.findall(pat,text,re.I):
            u=urljoin(base,m.replace('&amp;','&').replace('\\/','/'))
            if u.startswith('http'): out.append(u)
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('target'); ap.add_argument('-o','--out',default='out'); a=ap.parse_args()
    spec=json.load(open(a.target,encoding='utf-8')); out=Path(a.out); out.mkdir(parents=True,exist_ok=True)
    allowed=set(spec.get('allowed_types',['pdf','zip'])); min_bytes=int(spec.get('min_bytes',1024)); max_hops=int(spec.get('max_hops',40))
    report={'name':spec['name'],'citation':spec.get('citation'),'sources':spec['sources'],'attempts':[],'success':False}
    s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept':'*/*'})
    q=list(spec['sources']); seen=set(); result=None; kind=None
    while q and len(seen)<max_hops and not result:
        u=q.pop(0)
        if u in seen: continue
        seen.add(u)
        try:
            r=s.get(u,timeout=60,allow_redirects=True,stream=True)
            ct=(r.headers.get('content-type') or '').lower(); cl=int(r.headers.get('content-length') or 0)
            report['attempts'].append({'url':u,'status':r.status_code,'final_url':r.url,'content_type':ct,'content_length':cl})
            if r.status_code!=200: continue
            if 'text/html' in ct:
                text=r.content.decode(r.encoding or 'utf-8','ignore')
                cand=links(r.url,text)
                cand.sort(key=lambda x:(('.pdf' in x.lower()) or ('download' in x.lower()) or ('file' in x.lower())),reverse=True)
                q.extend(x for x in cand if x not in seen)
                continue
            name=spec.get('file_name') or os.path.basename(urlparse(r.url).path) or 'source.bin'
            p=out/name; n=0
            with open(p,'wb') as f:
                for chunk in r.iter_content(1024*1024):
                    if chunk: f.write(chunk); n+=len(chunk)
            kind=valid_head(p,allowed)
            if n<min_bytes or not kind:
                p.unlink(missing_ok=True); continue
            result=p
        except Exception as e:
            report['attempts'].append({'url':u,'error':repr(e)})
    if not result:
        json.dump(report,open(out/'fetch_report.json','w'),ensure_ascii=False,indent=2); raise SystemExit(2)
    report.update({'success':True,'file':result.name,'type':kind,'bytes':result.stat().st_size,'sha256':sha256(result)})
    json.dump(report,open(out/'fetch_report.json','w'),ensure_ascii=False,indent=2)
    open(out/'SHA256.txt','w').write(f"{report['sha256']}  {result.name}\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
