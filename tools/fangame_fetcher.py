#!/usr/bin/env python3
import argparse, hashlib, json, os, re, subprocess
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
ARCHIVE_EXTS = ('.zip','.rar','.7z','.exe','.tar','.gz','.xz')


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def archive_head_ok(path):
    with open(path, 'rb') as f:
        h = f.read(16)
    return (
        h.startswith(b'Rar!\x1a\x07')
        or h.startswith(b'PK\x03\x04')
        or h.startswith(b'7z\xbc\xaf\x27\x1c')
        or h.startswith(b'MZ')
    )


def extract_links(base, text):
    out = []
    pats = [
        r'href=["\']([^"\']+)["\']',
        r'src=["\']([^"\']+)["\']',
        r'(?:https?|ftp)://[^\s"\'<>]+'
    ]
    for p in pats:
        for m in re.findall(p, text, re.I):
            if isinstance(m, tuple):
                m = m[0]
            m = m.replace('&amp;', '&').replace('\\/', '/')
            if m.startswith('//'):
                m = 'https:' + m
            out.append(urljoin(base, m))
    scored = []
    for u in out:
        lu = u.lower()
        score = 0
        if any(x in lu for x in ARCHIVE_EXTS):
            score += 6
        if any(x in lu for x in ('download','down','file','attach','mediafire','qiannao','115.com')):
            score += 3
        if any(x in lu for x in ('javascript:','#')):
            score -= 10
        if score > 0:
            scored.append((score, u))
    return [u for _, u in sorted(scored, reverse=True)]


def _content_length(headers):
    try:
        return int(headers.get('content-length') or 0)
    except Exception:
        return 0


def _content_range_total(headers):
    value = headers.get('content-range') or ''
    m = re.search(r'/([0-9]+)\s*$', value)
    return int(m.group(1)) if m else 0


def stream_binary_resumable(session, response, path, report, max_attempts=6):
    """Stream a large public binary with bounded HTTP Range resume."""
    active = response
    expected_total = _content_range_total(active.headers) or _content_length(active.headers)
    request_url = active.url

    for attempt in range(1, max_attempts + 1):
        existing = path.stat().st_size if path.exists() else 0
        status = active.status_code
        range_total = _content_range_total(active.headers)
        if range_total:
            expected_total = range_total
        elif status == 200 and _content_length(active.headers):
            expected_total = _content_length(active.headers)

        append = status == 206 and existing > 0
        if status == 200 and existing > 0:
            report['attempts'].append({
                'url': request_url, 'transport': 'http-range-reset',
                'resume_from': existing, 'reason': 'server_returned_200_for_resume'
            })
            path.unlink(missing_ok=True)
            existing = 0
            append = False

        before = existing if append else 0
        try:
            with open(path, 'ab' if append else 'wb') as f:
                for chunk in active.iter_content(1024 * 1024):
                    if chunk:
                        f.write(chunk)
            size = path.stat().st_size if path.exists() else 0
            report['attempts'].append({
                'url': request_url, 'transport': 'http-stream',
                'stream_attempt': attempt, 'status': status,
                'resume_from': before, 'bytes_after': size,
                'expected_total': expected_total or None,
                'complete': bool(expected_total and size >= expected_total) if expected_total else True
            })
            if not expected_total or size >= expected_total:
                return size
        except Exception as e:
            size = path.stat().st_size if path.exists() else 0
            report['attempts'].append({
                'url': request_url, 'transport': 'http-stream',
                'stream_attempt': attempt, 'status': status,
                'resume_from': before, 'bytes_after': size,
                'expected_total': expected_total or None,
                'error': repr(e)
            })

        if attempt >= max_attempts:
            break
        current = path.stat().st_size if path.exists() else 0
        headers = {'Range': f'bytes={current}-'} if current > 0 else {}
        try:
            active = session.get(
                request_url, headers=headers, timeout=(15, 120),
                allow_redirects=True, stream=True
            )
            report['attempts'].append({
                'url': request_url, 'transport': 'http-range-resume',
                'resume_attempt': attempt + 1, 'resume_from': current,
                'status': active.status_code, 'final_url': active.url,
                'content_length': _content_length(active.headers),
                'content_range': active.headers.get('content-range')
            })
            if active.status_code not in (200, 206):
                break
            request_url = active.url
        except Exception as e:
            report['attempts'].append({
                'url': request_url, 'transport': 'http-range-resume',
                'resume_attempt': attempt + 1, 'resume_from': current,
                'error': repr(e)
            })
            continue

    return path.stat().st_size if path.exists() else 0


def fetch_http(session, url, outdir, min_mb, report):
    q = [url]
    seen = set()
    while q and len(seen) < 80:
        u = q.pop(0)
        if u in seen:
            continue
        seen.add(u)
        if u.lower().startswith('ftp://'):
            result = fetch_ftp(u, outdir, min_mb, report)
            if result:
                return result
            continue
        try:
            r = session.get(u, timeout=(15, 120), allow_redirects=True, stream=True)
            ct = (r.headers.get('content-type') or '').lower()
            cl = _content_length(r.headers)
            report['attempts'].append({
                'url': u, 'status': r.status_code, 'final_url': r.url,
                'content_type': ct, 'content_length': cl
            })
            if r.status_code != 200:
                continue
            if 'text/html' in ct or (cl == 0 and r.url.lower().endswith(('.html','.htm','.php','.page','/'))):
                text = r.content.decode(r.encoding or 'utf-8', 'ignore')
                q.extend(x for x in extract_links(r.url, text) if x not in seen)
                continue
            cd = r.headers.get('content-disposition') or ''
            name = None
            m = re.search(r'filename\*?=(?:UTF-8\'\')?["\']?([^"\';]+)', cd, re.I)
            if m:
                name = m.group(1)
            if not name:
                name = os.path.basename(urlparse(r.url).path) or 'download.bin'
            path = Path(outdir) / name
            n = stream_binary_resumable(session, r, path, report)
            if n < min_mb * 1024 * 1024 or (cl and n < cl) or not archive_head_ok(path):
                report['attempts'].append({
                    'url': u, 'transport': 'http-validation',
                    'bytes': n, 'initial_content_length': cl,
                    'min_bytes': min_mb * 1024 * 1024,
                    'archive_head_ok': archive_head_ok(path) if path.exists() and n else False,
                    'accepted': False
                })
                path.unlink(missing_ok=True)
                continue
            return path
        except Exception as e:
            report['attempts'].append({'url': u, 'error': repr(e)})
    return None


def fetch_itch(session, url, outdir, min_mb, report, desired_upload_id=None):
    """Resolve itch.io public free downloads; optionally lock to one upload ID."""
    page = url.rstrip('/')
    headers = {'Referer': url, 'X-Requested-With': 'XMLHttpRequest'}
    try:
        r = session.get(page, timeout=45, allow_redirects=True)
        report['attempts'].append({
            'url': page, 'transport': 'itch-page', 'status': r.status_code,
            'content_type': (r.headers.get('content-type') or '').lower()
        })
        if r.status_code != 200:
            return None
        text = r.text
        upload_ids = re.findall(r'data-upload_id=["\'](\d+)["\']', text, re.I)
        if not upload_ids:
            d = session.post(page + '/download_url', headers=headers, timeout=45, allow_redirects=True)
            report['attempts'].append({
                'url': page + '/download_url', 'transport': 'itch-download-page',
                'status': d.status_code,
                'content_type': (d.headers.get('content-type') or '').lower()
            })
            if d.status_code == 200:
                try:
                    temp = d.json().get('url')
                except Exception:
                    temp = None
                if temp:
                    rr = session.get(temp, timeout=45, allow_redirects=True)
                    report['attempts'].append({
                        'url': temp, 'transport': 'itch-temp-page',
                        'status': rr.status_code, 'final_url': rr.url
                    })
                    if rr.status_code == 200:
                        text = rr.text
                        page = rr.url.split('?')[0].rstrip('/')
                        upload_ids = re.findall(r'data-upload_id=["\'](\d+)["\']', text, re.I)

        upload_ids = list(dict.fromkeys(upload_ids))
        report['attempts'].append({
            'url': url, 'transport': 'itch-upload-discovery',
            'upload_ids': upload_ids, 'desired_upload_id': str(desired_upload_id) if desired_upload_id else None
        })

        if desired_upload_id is not None:
            desired = str(desired_upload_id)
            if desired not in upload_ids:
                report['attempts'].append({
                    'url': url, 'transport': 'itch-upload-select',
                    'desired_upload_id': desired, 'found': False
                })
                return None
            upload_ids = [desired]
            report['attempts'].append({
                'url': url, 'transport': 'itch-upload-select',
                'desired_upload_id': desired, 'found': True
            })

        for uid in upload_ids:
            endpoint = page + '/file/' + uid + '?source=view_game&as_props=1&after_download_lightbox=true'
            p = session.post(
                endpoint,
                headers={'Referer': page, 'X-Requested-With': 'XMLHttpRequest'},
                timeout=45,
                allow_redirects=True
            )
            rec = {
                'url': endpoint, 'transport': 'itch-file-resolve',
                'upload_id': uid, 'status': p.status_code,
                'content_type': (p.headers.get('content-type') or '').lower()
            }
            dl = None
            if p.status_code == 200:
                try:
                    dl = p.json().get('url')
                except Exception:
                    pass
            if dl:
                rec['resolved_url'] = dl
            report['attempts'].append(rec)
            if dl:
                result = fetch_http(session, dl, outdir, min_mb, report)
                if result:
                    return result
    except Exception as e:
        report['attempts'].append({'url': url, 'transport': 'itch', 'error': repr(e)})
    return None


def fetch_ftp(url, outdir, min_mb, report):
    """Bound old FTP probes so dead hosts cannot occupy a rescue lane for ~15 minutes."""
    name = os.path.basename(urlparse(url).path) or 'download.rar'
    path = Path(outdir) / name
    commands = [
        ['curl','-L','--fail','--connect-timeout','15','--max-time','90','-o',str(path),url],
        ['wget','--timeout=20','--tries=1','-O',str(path),url],
    ]
    for cmd in commands:
        try:
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            report['attempts'].append({
                'url': url, 'transport': cmd[0], 'returncode': p.returncode,
                'log_tail': p.stdout[-1200:]
            })
            if p.returncode == 0 and path.exists() and path.stat().st_size >= min_mb * 1024 * 1024 and archive_head_ok(path):
                return path
        except Exception as e:
            report['attempts'].append({'url': url, 'transport': cmd[0], 'error': repr(e)})
    path.unlink(missing_ok=True)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target')
    ap.add_argument('-o', '--out', default='out')
    args = ap.parse_args()

    spec = json.load(open(args.target, encoding='utf-8'))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        'name': spec['name'], 'version': spec.get('version'),
        'engine': spec.get('engine'), 'sources': spec['sources'],
        'itch_upload_id': spec.get('itch_upload_id'),
        'attempts': [], 'success': False
    }
    s = requests.Session()
    s.headers.update({'User-Agent': UA, 'Accept': '*/*'})
    min_mb = int(spec.get('min_mb', 10))
    result = None
    for u in spec['sources']:
        host = urlparse(u).netloc.lower()
        if u.startswith('ftp://'):
            result = fetch_ftp(u, out, min_mb, report)
        elif host.endswith('.itch.io') or host == 'itch.io':
            result = fetch_itch(s, u, out, min_mb, report, spec.get('itch_upload_id'))
        else:
            result = fetch_http(s, u, out, min_mb, report)
        if result:
            break

    if not result:
        json.dump(report, open(out / 'fetch_report.json', 'w'), ensure_ascii=False, indent=2)
        raise SystemExit(2)

    report.update({
        'success': True, 'file': result.name,
        'bytes': result.stat().st_size, 'sha256': sha256(result)
    })
    json.dump(report, open(out / 'fetch_report.json', 'w'), ensure_ascii=False, indent=2)
    open(out / 'SHA256.txt', 'w').write(f"{report['sha256']}  {result.name}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
