#!/usr/bin/env python3
import argparse, hashlib, json, shutil, time
from pathlib import Path

from playwright.sync_api import sync_playwright


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() if Path(path).exists() else None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--static', required=True)
    ap.add_argument('--extract-root', required=True)
    ap.add_argument('--outdir', required=True)
    args=ap.parse_args()

    st=json.loads(Path(args.static).read_text(encoding='utf-8'))
    extract=Path(args.extract_root).resolve()
    root=(extract/st.get('game_root','.')).resolve()
    out=Path(args.outdir).resolve(); out.mkdir(parents=True,exist_ok=True)
    candidates=[root/'www'/'index.html',root/'index.html']
    index=next((p for p in candidates if p.exists()),None)
    result={'schema':'fangame.mv_browser_probe.v0.1','engine':st.get('engine'),'game_root':str(root),'index_html':str(index) if index else None,'status':'NOT_RUN','console':[],'page_errors':[]}
    if not index:
        result['status']='NO_INDEX_HTML'; result['playability_class']='PLAYABILITY_UNKNOWN'
        (out/'mv_browser_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return 0

    try:
        with sync_playwright() as p:
            kwargs={'headless':True,'args':['--allow-file-access-from-files','--autoplay-policy=no-user-gesture-required','--disable-web-security','--no-sandbox','--disable-gpu']}
            chrome=shutil.which('google-chrome') or shutil.which('google-chrome-stable') or shutil.which('chromium')
            if chrome: kwargs['executable_path']=chrome
            browser=p.chromium.launch(**kwargs)
            page=browser.new_page(viewport={'width':1280,'height':720})
            page.on('console',lambda m: result['console'].append({'type':m.type,'text':m.text[:2000]}))
            page.on('pageerror',lambda e: result['page_errors'].append(str(e)[:4000]))
            page.goto(index.as_uri(),wait_until='domcontentloaded',timeout=30000)
            result['document_title']=page.title()
            result['url']=page.url
            time.sleep(15)
            p15=out/'01_browser_15s.png'; page.screenshot(path=str(p15))
            result['body_text_15s']=page.locator('body').inner_text(timeout=5000)[:2000]
            result['canvas_15s']=page.locator('canvas').count()
            result['shot_15s_sha256']=sha(p15)
            time.sleep(45)
            p60=out/'02_browser_60s.png'; page.screenshot(path=str(p60))
            result['body_text_60s']=page.locator('body').inner_text(timeout=5000)[:2000]
            result['canvas_60s']=page.locator('canvas').count()
            result['shot_60s_sha256']=sha(p60)
            page.keyboard.press('Enter'); time.sleep(8)
            pe=out/'03_browser_after_enter.png'; page.screenshot(path=str(pe))
            result['body_text_after_enter']=page.locator('body').inner_text(timeout=5000)[:2000]
            result['shot_enter_sha256']=sha(pe)
            for k in ('ArrowDown','ArrowRight','ArrowLeft','ArrowUp'):
                page.keyboard.press(k); time.sleep(1)
            time.sleep(5)
            pa=out/'04_browser_after_arrows.png'; page.screenshot(path=str(pa))
            result['body_text_after_arrows']=page.locator('body').inner_text(timeout=5000)[:2000]
            result['shot_arrows_sha256']=sha(pa)
            result['page_still_open']=not page.is_closed()
            browser.close()

        h15=result.get('shot_15s_sha256'); h60=result.get('shot_60s_sha256'); he=result.get('shot_enter_sha256'); ha=result.get('shot_arrows_sha256')
        result['visual_change_15_to_60']=bool(h15 and h60 and h15!=h60)
        result['visual_change_60_to_enter']=bool(h60 and he and h60!=he)
        result['visual_change_enter_to_arrows']=bool(he and ha and he!=ha)
        if result.get('page_still_open') and result['visual_change_60_to_enter'] and result['visual_change_enter_to_arrows']:
            result['status']='BROWSER_INPUT_FLOW_VISUALLY_RESPONSIVE'; result['playability_class']='PLAYABILITY_VERIFIED_INPUT_FLOW'
        elif result.get('page_still_open') and result['visual_change_60_to_enter']:
            result['status']='BROWSER_POST_ENTER_VISUALLY_RESPONSIVE'; result['playability_class']='PLAYABILITY_VERIFIED_BOOT'
        elif result.get('page_still_open') and result['visual_change_15_to_60']:
            result['status']='BROWSER_VISUAL_PROGRESS_DURING_BOOT'; result['playability_class']='PLAYABILITY_RECOVERABLE_RUNTIME_ALIVE'
        elif result.get('page_still_open'):
            result['status']='BROWSER_STATIC_AFTER_60S'; result['playability_class']='PLAYABILITY_RECOVERABLE_RUNTIME_ALIVE'
        else:
            result['status']='BROWSER_RUNTIME_FAILED'; result['playability_class']='PLAYABILITY_UNKNOWN'
    except Exception as e:
        result['status']='BROWSER_PROBE_ERROR'; result['playability_class']='PLAYABILITY_UNKNOWN'; result['error']=repr(e)

    (out/'mv_browser_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
