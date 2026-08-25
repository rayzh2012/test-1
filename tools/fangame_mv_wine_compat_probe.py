#!/usr/bin/env python3
import argparse, json, os, shutil, subprocess, time
from pathlib import Path

from fangame_smoke import ensure_wine32, ensure_virtual_audio, screenshot, diff_pixels, key, windows, window_titles


def run(cmd, env=None, cwd=None, timeout=90):
    try:
        p = subprocess.run(cmd, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, errors='replace', timeout=timeout)
        return p.returncode, p.stdout[-12000:]
    except Exception as e:
        return 999, repr(e)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--static', required=True)
    ap.add_argument('--extract-root', required=True)
    ap.add_argument('--outdir', required=True)
    args=ap.parse_args()

    st=json.loads(Path(args.static).read_text(encoding='utf-8'))
    extract=Path(args.extract_root).resolve()
    game_root=(extract / st.get('game_root','.')).resolve()
    out=Path(args.outdir).resolve(); out.mkdir(parents=True, exist_ok=True)
    result={
        'schema':'fangame.mv_wine_compat_probe.v0.1',
        'engine':st.get('engine'), 'game_root':str(game_root),
        'runtime':'Wine/NW.js software-render compatibility profile',
        'status':'NOT_RUN', 'notes':[]
    }
    exe=game_root/'Game.exe'
    if st.get('engine') not in ('RPG Maker MV','RPG Maker MZ') or not exe.exists() or not shutil.which('wine'):
        result['status']='NO_COMPAT_PATH'; result['playability_class']='PLAYABILITY_UNKNOWN'
        (out/'mv_compat_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0

    result['wine32_ready']=ensure_wine32(result['notes'])
    ok,audio_env=ensure_virtual_audio(result['notes']); result['virtual_audio_ready']=ok
    if not result['wine32_ready'] or not ok:
        result['status']='CI_RUNTIME_SETUP_FAILED'; result['playability_class']='PLAYABILITY_UNKNOWN'
        (out/'mv_compat_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False,indent=2)); return 0

    display=':98'; prefix=(extract.parent/'wineprefix-mv-compat').resolve()
    if prefix.exists(): shutil.rmtree(prefix)
    env=os.environ.copy(); env.update(audio_env)
    env.update({
        'DISPLAY':display,
        'WINEDEBUG':'-all',
        'WINEDLLOVERRIDES':'winemenubuilder.exe=d',
        'WINEPREFIX':str(prefix),
        'LIBGL_ALWAYS_SOFTWARE':'1',
        'MESA_LOADER_DRIVER_OVERRIDE':'llvmpipe',
    })
    xvfb=proc=logf=None
    try:
        xvfb=subprocess.Popen(['Xvfb',display,'-screen','0','1280x720x24','-nolisten','tcp'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5)
        rc,bootlog=run(['wineboot','-u'],env=env,cwd=game_root,timeout=120)
        result['wineboot_rc']=rc
        if rc!=0: result['notes'].append('wineboot failed: '+bootlog[-2000:])
        # Force Pulse, but decode output safely; failure here is non-fatal.
        rc,reglog=run(['wine','reg','add',r'HKCU\\Software\\Wine\\Drivers','/v','Audio','/t','REG_SZ','/d','pulse','/f'],env=env,cwd=game_root,timeout=30)
        result['wine_force_pulse_rc']=rc
        if rc!=0: result['notes'].append(reglog[-2000:])
        logf=open(out/'runtime_compat.log','w',encoding='utf-8',errors='replace')
        cmd=['wine',exe.name,'--disable-gpu','--disable-gpu-compositing','--disable-gpu-sandbox','--no-sandbox']
        proc=subprocess.Popen(cmd,cwd=game_root,env=env,stdout=logf,stderr=subprocess.STDOUT,text=True,errors='replace')

        time.sleep(15)
        s15=out/'01_after_15s.png'; screenshot(env,s15)
        result['alive_15s']=proc.poll() is None
        result['windows_15s']=len(windows(env)); result['titles_15s']=window_titles(env,windows(env))

        time.sleep(45)
        s60=out/'02_after_60s.png'; screenshot(env,s60)
        result['alive_60s']=proc.poll() is None
        result['windows_60s']=len(windows(env)); result['titles_60s']=window_titles(env,windows(env))
        result['visual_change_15_to_60']=diff_pixels(s15,s60)

        if result['alive_60s']:
            key(env,'Return'); time.sleep(10)
            senter=out/'03_after_enter.png'; screenshot(env,senter)
            result['visual_change_60_to_enter']=diff_pixels(s60,senter)
            result['alive_after_enter']=proc.poll() is None
            for k in ('Down','Right','Left','Up'):
                key(env,k); time.sleep(1)
            time.sleep(6)
            smove=out/'04_after_arrows.png'; screenshot(env,smove)
            result['visual_change_enter_to_arrows']=diff_pixels(senter,smove)
            result['alive_after_arrows']=proc.poll() is None

        dload=result.get('visual_change_15_to_60') or 0
        denter=result.get('visual_change_60_to_enter') or 0
        darrow=result.get('visual_change_enter_to_arrows') or 0
        if result.get('alive_after_arrows') and denter > 1000 and darrow > 300:
            result['status']='INPUT_FLOW_VERIFIED_SOFTWARE_RENDER'
            result['playability_class']='PLAYABILITY_VERIFIED_INPUT_FLOW'
        elif result.get('alive_after_enter') and denter > 1000:
            result['status']='POST_ENTER_RESPONSE_VERIFIED_SOFTWARE_RENDER'
            result['playability_class']='PLAYABILITY_VERIFIED_BOOT'
        elif result.get('alive_60s') and dload > 1000:
            result['status']='VISUAL_PROGRESS_DURING_EXTENDED_BOOT'
            result['playability_class']='PLAYABILITY_RECOVERABLE_RUNTIME_ALIVE'
        elif result.get('alive_60s'):
            result['status']='STILL_VISUALLY_STATIC_AFTER_60S'
            result['playability_class']='PLAYABILITY_RECOVERABLE_RUNTIME_ALIVE'
        else:
            result['status']='PROCESS_EXITED_DURING_EXTENDED_BOOT'
            result['playability_class']='PLAYABILITY_UNKNOWN'
    except Exception as e:
        result['status']='COMPAT_PROBE_ERROR'; result['playability_class']='PLAYABILITY_UNKNOWN'; result['notes'].append(repr(e))
    finally:
        if proc and proc.poll() is None:
            try: proc.terminate(); proc.wait(timeout=3)
            except Exception:
                try: proc.kill()
                except Exception: pass
        if xvfb:
            try: xvfb.terminate(); xvfb.wait(timeout=3)
            except Exception:
                try: xvfb.kill()
                except Exception: pass
        if logf:
            try: logf.close()
            except Exception: pass

    (out/'mv_compat_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
