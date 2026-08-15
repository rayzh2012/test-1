#!/usr/bin/env python3
import argparse, hashlib, html, json, os, re, shutil, subprocess, sys, time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
ARCHIVE_EXTS = ('.zip','.rar','.7z','.exe','.tar','.gz','.xz')

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def archive_head_ok(path):
    with open(path,'rb') as f: h=f.read(16)
    return h.startswith(b'Rar!\x1a\x07') or h.startswith(b'PK\x03\x04') or h.startswith(b'7z\xbc\xaf\x27\x1c') or h.startswith(b'MZ')

def _norm(s):
    return re.sub(r'\s+',' ', html.unescape(re.sub(r'<[^>]+>',' ',s or ''))).strip().lower()

def _looks_downloadish(u):
    p=urlparse(u)
    sig=(p.path+'?'+p.query).lower()
    if any(sig.endswith(x) or x+'?' in sig for x in ARCHIVE_EXTS): return True
    return any(x in sig for x in ('download','downurl','down_url','fileurl','file_url','getfile','attach','attachment','/file/','/files/','down.php','download.php')) or any(x in (p.netloc or '').lower() for x in ('mediafire','115.com','rayfile','dropboxusercontent'))

def extract_links(base, text, terms=None):
    terms=[_norm(x) for x in (terms or []) if _norm(x)]
    found=[]
    for href,label in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',text,re.I|re.S):
        found.append((href,_norm(label),'anchor'))
    for attr,val in re.findall(r'\b(data-url|data-href|data-download|download-url|file-url|url)\s*=\s*["\']([^"\']+)["\']',text,re.I):
        found.append((val,'',attr.lower()))
    js_patterns=[
        r'(?:location(?:\.href)?|window\.location(?:\.href)?)\s*=\s*["\']([^"\']+)["\']',
        r'(?:window\.)?open\(\s*["\']([^"\']+)["\']',
        r'(?:url|downurl|downloadurl|fileurl)\s*[:=]\s*["\']([^"\']+)["\']',
    ]
    for p in js_patterns:
        for val in re.findall(p,text,re.I): found.append((val,'','js'))
    for p in (r'src=["\']([^"\']+)["\']',r'https?://[^\s"\'<>]+'):
        for m in re.findall(p,text,re.I):
            if isinstance(m,tuple): m=m[0]
            found.append((m,'','raw'))
    for val in re.findall(r'["\']([^"\']{3,500})["\']',text):
        lv=val.lower()
        if any(x in lv for x in ('download','downurl','down.php','fileurl','getfile','.rar','.zip','.7z','.exe')):
            found.append((val,'','quoted'))
    scored=[]; emitted=set()
    for raw,label,kind in found:
        raw=html.unescape(raw).replace('\\/','/').strip()
        if raw.startswith('//'): raw='https:'+raw
        if raw.startswith(('javascript:','data:','#')): continue
        if kind=='quoted' and (' ' in raw[:30] or raw.startswith(('{','['))): continue
        u=urljoin(base,raw)
        if u in emitted: continue
        emitted.add(u)
        score=0
        if _looks_downloadish(u): score+=7
        if any(x in urlparse(u).path.lower() for x in ARCHIVE_EXTS): score+=6
        if terms and any(t in label or t in _norm(u) for t in terms): score+=10
        if kind in ('data-url','data-href','data-download','download-url','file-url','js'): score+=4
        if urlparse(u).path.lower().endswith(('.js','.css','.jpg','.jpeg','.png','.gif','.webp','.ico')): score-=12
        if score>0: scored.append((score,u))
    return [u for _,u in sorted(scored,key=lambda x:x[0],reverse=True)]

def probe_snippets(text, probe_terms):
    """Small bounded raw-HTML contexts for debugging dynamic legacy download pages."""
    out=[]; low=text.lower()
    for term in probe_terms or []:
        t=str(term).lower(); start=0; hits=0
        while t and hits<2:
            i=low.find(t,start)
            if i<0: break
            a=max(0,i-350); b=min(len(text),i+len(t)+650)
            out.append({'term':term,'context':text[a:b]})
            start=i+len(t); hits+=1
        if len(out)>=10: break
    return out[:10]

def _size_ok(n,min_mb,max_mb=None):
    if n < min_mb*1024*1024: return False
    if max_mb is not None and n > max_mb*1024*1024: return False
    return True

def fetch_http(session,url,outdir,min_mb,report,link_terms=None,max_mb=None,probe_terms=None):
    q=[url]; seen=set()
    while q and len(seen)<120:
        u=q.pop(0)
        if u in seen: continue
        seen.add(u)
        try:
            r=session.get(u,timeout=45,allow_redirects=True,stream=True)
            ct=(r.headers.get('content-type') or '').lower()
            cl=int(r.headers.get('content-length') or 0)
            report['attempts'].append({'url':u,'status':r.status_code,'final_url':r.url,'content_type':ct,'content_length':cl})
            if r.status_code!=200: continue
            if 'text/html' in ct or cl==0 and r.url.lower().endswith(('.html','.htm','.php','.page','/')):
                enc=r.encoding
                if not enc or enc.lower() in ('iso-8859-1','ascii'):
                    enc=r.apparent_encoding or 'utf-8'
                text=r.content.decode(enc,'ignore')
                links=extract_links(r.url,text,link_terms)
                report['attempts'][-1]['candidate_links']=links[:20]
                snippets=probe_snippets(text,probe_terms)
                if snippets: report['attempts'][-1]['probe_snippets']=snippets
                q.extend(x for x in links if x not in seen)
                continue
            cd=r.headers.get('content-disposition') or ''
            name=None
            m=re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)',cd,re.I)
            if m: name=m.group(1)
            if not name:
                name=os.path.basename(urlparse(r.url).path) or 'download.bin'
            path=Path(outdir)/name
            n=0
            with open(path,'wb') as f:
                for chunk in r.iter_content(1024*1024):
                    if chunk: f.write(chunk); n+=len(chunk)
            if not _size_ok(n,min_mb,max_mb) or not archive_head_ok(path):
                report['attempts'].append({'url':u,'rejected_file':name,'downloaded_bytes':n,'reason':'size_or_archive_magic'})
                path.unlink(missing_ok=True)
                continue
            return path
        except Exception as e:
            report['attempts'].append({'url':u,'error':repr(e)})
    return None

def fetch_ftp(url,outdir,min_mb,report,max_mb=None):
    name=os.path.basename(urlparse(url).path) or 'download.rar'
    path=Path(outdir)/name
    for cmd in (["curl","-L","--fail","--connect-timeout","20","--max-time","900","-o",str(path),url],
                ["wget","-O",str(path),url]):
        try:
            p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=950)
            report['attempts'].append({'url':url,'transport':cmd[0],'returncode':p.returncode,'log_tail':p.stdout[-1200:]})
            if p.returncode==0 and path.exists() and _size_ok(path.stat().st_size,min_mb,max_mb) and archive_head_ok(path): return path
        except Exception as e:
            report['attempts'].append({'url':url,'transport':cmd[0],'error':repr(e)})
    path.unlink(missing_ok=True); return None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('target'); ap.add_argument('-o','--out',default='out'); args=ap.parse_args()
    spec=json.load(open(args.target,encoding='utf-8'))
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    report={'name':spec['name'],'version':spec.get('version'),'engine':spec.get('engine'),'sources':spec['sources'],'attempts':[],'success':False}
    s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept':'*/*'})
    min_mb=int(spec.get('min_mb',10)); max_mb=spec.get('max_mb'); max_mb=float(max_mb) if max_mb is not None else None
    link_terms=spec.get('link_terms') or []; probes=spec.get('probe_terms') or []
    result=None
    for u in spec['sources']:
        result=fetch_ftp(u,out,min_mb,report,max_mb) if u.startswith('ftp://') else fetch_http(s,u,out,min_mb,report,link_terms,max_mb,probes)
        if result: break
    if not result:
        json.dump(report,open(out/'fetch_report.json','w'),ensure_ascii=False,indent=2); raise SystemExit(2)
    report.update({'success':True,'file':result.name,'bytes':result.stat().st_size,'sha256':sha256(result)})
    json.dump(report,open(out/'fetch_report.json','w'),ensure_ascii=False,indent=2)
    open(out/'SHA256.txt','w').write(f"{report['sha256']}  {result.name}\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
