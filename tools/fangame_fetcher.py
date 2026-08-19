#!/usr/bin/env python3
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time, zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
ARCHIVE_EXTS = ('.zip','.rar','.7z','.exe','.tar','.gz','.xz','.torrent')

def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def archive_head_ok(path):
    try:
        with open(path,'rb') as f: h=f.read(16)
    except OSError:
        return False
    return h.startswith(b'Rar!\x1a\x07') or h.startswith(b'PK\x03\x04') or h.startswith(b'7z\xbc\xaf\x27\x1c') or h.startswith(b'MZ')

def torrent_head_ok(path, content_type=''):
    if 'bittorrent' in content_type.lower(): return True
    try:
        with open(path,'rb') as f: h=f.read(4096)
    except OSError:
        return False
    return h.startswith(b'd') and (b'4:info' in h or b'8:announce' in h or b'13:announce-list' in h)

def extract_links(base, text):
    out=[]
    pats=[r'href=["\']([^"\']+)["\']',r'src=["\']([^"\']+)["\']',r'https?://[^\s"\'<>]+']
    for p in pats:
        for m in re.findall(p,text,re.I):
            if isinstance(m,tuple): m=m[0]
            m=m.replace('&amp;','&').replace('\\/','/')
            if m.startswith('//'): m='https:'+m
            out.append(urljoin(base,m))
    scored=[]
    for u in out:
        lu=u.lower()
        score=0
        if any(x in lu for x in ARCHIVE_EXTS): score+=6
        if any(x in lu for x in ('download','down','file','attach','mediafire','qiannao','115.com')): score+=3
        if any(x in lu for x in ('javascript:','#')): score-=10
        if score>0: scored.append((score,u))
    return [u for _,u in sorted(scored,reverse=True)]

def fetch_torrent(torrent_path,outdir,min_mb,report):
    aria2=shutil.which('aria2c')
    if not aria2 and shutil.which('sudo') and shutil.which('apt-get'):
        try:
            p=subprocess.run(['sudo','apt-get','update'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=240)
            report['attempts'].append({'url':str(torrent_path),'transport':'torrent/apt-update','returncode':p.returncode,'log_tail':p.stdout[-1200:]})
            p=subprocess.run(['sudo','apt-get','install','-y','aria2'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=240)
            report['attempts'].append({'url':str(torrent_path),'transport':'torrent/apt-install','returncode':p.returncode,'log_tail':p.stdout[-1200:]})
            aria2=shutil.which('aria2c')
        except Exception as e:
            report['attempts'].append({'url':str(torrent_path),'transport':'torrent/apt-install','error':repr(e)})
    if not aria2:
        report['attempts'].append({'url':str(torrent_path),'transport':'torrent','error':'aria2c unavailable'})
        return None
    work=Path(outdir)/'.torrent_payload'
    shutil.rmtree(work,ignore_errors=True); work.mkdir(parents=True,exist_ok=True)
    cmd=[aria2,'--seed-time=0','--bt-stop-timeout=180','--timeout=30','--connect-timeout=30','--max-tries=3','--retry-wait=5','--file-allocation=none','--summary-interval=10','--dir',str(work),str(torrent_path)]
    try:
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1200)
        report['attempts'].append({'url':str(torrent_path),'transport':'torrent/aria2c','returncode':p.returncode,'log_tail':p.stdout[-4000:]})
    except Exception as e:
        report['attempts'].append({'url':str(torrent_path),'transport':'torrent/aria2c','error':repr(e)})
        return None
    files=[p for p in work.rglob('*') if p.is_file() and not p.name.endswith('.aria2')]
    total=sum(p.stat().st_size for p in files)
    report['torrent_payload']={'file_count':len(files),'total_bytes':total,'files':[{'path':str(p.relative_to(work)),'bytes':p.stat().st_size} for p in files[:500]]}
    threshold=min_mb*1024*1024
    good=[p for p in files if p.stat().st_size>=threshold and archive_head_ok(p)]
    if good:
        src=max(good,key=lambda p:p.stat().st_size)
        dst=Path(outdir)/src.name
        if src.resolve()!=dst.resolve(): shutil.copy2(src,dst)
        return dst
    if total < threshold or not files:
        return None
    # Reversible container for public multi-file torrent payloads when the distribution is a directory rather than one archive.
    dst=Path(outdir)/'torrent_payload.zip'
    manifest=[]
    with zipfile.ZipFile(dst,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for p in sorted(files,key=lambda x:str(x.relative_to(work)).lower()):
            rel=str(p.relative_to(work))
            z.write(p,rel)
            manifest.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha256(p)})
    report['torrent_payload']['manifest']=manifest
    report['torrent_payload']['repacked_as']=dst.name
    return dst if dst.stat().st_size>=threshold else None

def fetch_http(session,url,outdir,min_mb,report):
    q=[url]; seen=set()
    while q and len(seen)<80:
        u=q.pop(0)
        if u in seen: continue
        seen.add(u)
        try:
            r=session.get(u,timeout=45,allow_redirects=True,stream=True)
            ct=(r.headers.get('content-type') or '').lower()
            cl=int(r.headers.get('content-length') or 0)
            report['attempts'].append({'url':u,'status':r.status_code,'final_url':r.url,'content_type':ct,'content_length':cl})
            if r.status_code!=200: continue
            html_suffix=r.url.lower().endswith(('.html','.htm','.php','.page','/'))
            htmlish='text/html' in ct or (cl==0 and html_suffix and (not ct or ct.startswith('text/')))
            if htmlish:
                text=r.content.decode(r.encoding or 'utf-8','ignore')
                q.extend(x for x in extract_links(r.url,text) if x not in seen)
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
            if torrent_head_ok(path,ct):
                torrent_path=Path(outdir)/'source.torrent'
                if path!=torrent_path:
                    torrent_path.unlink(missing_ok=True); path.replace(torrent_path)
                report['attempts'].append({'url':u,'transport':'torrent-metadata','bytes':torrent_path.stat().st_size,'sha256':sha256(torrent_path)})
                result=fetch_torrent(torrent_path,outdir,min_mb,report)
                if result: return result
                continue
            if n < min_mb*1024*1024 or not archive_head_ok(path):
                path.unlink(missing_ok=True)
                continue
            return path
        except Exception as e:
            report['attempts'].append({'url':u,'error':repr(e)})
    return None

def fetch_ftp(url,outdir,min_mb,report):
    name=os.path.basename(urlparse(url).path) or 'download.rar'
    path=Path(outdir)/name
    for cmd in (["curl","-L","--fail","--connect-timeout","20","--max-time","900","-o",str(path),url],
                ["wget","-O",str(path),url]):
        try:
            p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=950)
            report['attempts'].append({'url':url,'transport':cmd[0],'returncode':p.returncode,'log_tail':p.stdout[-1200:]})
            if p.returncode==0 and path.exists() and path.stat().st_size>=min_mb*1024*1024 and archive_head_ok(path): return path
        except Exception as e:
            report['attempts'].append({'url':url,'transport':cmd[0],'error':repr(e)})
    path.unlink(missing_ok=True); return None

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('target'); ap.add_argument('-o','--out',default='out'); args=ap.parse_args()
    spec=json.load(open(args.target,encoding='utf-8'))
    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    report={'name':spec['name'],'version':spec.get('version'),'engine':spec.get('engine'),'sources':spec['sources'],'attempts':[],'success':False}
    s=requests.Session(); s.headers.update({'User-Agent':UA,'Accept':'*/*'})
    min_mb=int(spec.get('min_mb',10))
    result=None
    for u in spec['sources']:
        result=fetch_ftp(u,out,min_mb,report) if u.startswith('ftp://') else fetch_http(s,u,out,min_mb,report)
        if result: break
    if not result:
        json.dump(report,open(out/'fetch_report.json','w'),ensure_ascii=False,indent=2); raise SystemExit(2)
    report.update({'success':True,'file':result.name,'bytes':result.stat().st_size,'sha256':sha256(result)})
    json.dump(report,open(out/'fetch_report.json','w'),ensure_ascii=False,indent=2)
    open(out/'SHA256.txt','w').write(f"{report['sha256']}  {result.name}\n")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
