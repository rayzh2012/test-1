#!/usr/bin/env python3
import argparse, json, os, shutil, signal, subprocess, time
from pathlib import Path


def run(cmd, env=None, cwd=None, timeout=30):
    try:
        p=subprocess.run(cmd,env=env,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
        return p.returncode,p.stdout[-6000:]
    except Exception as e:
        return 999,repr(e)

def screenshot(env, path):
    if shutil.which('scrot'):
        rc,log=run(['scrot','-o',str(path)],env=env,timeout=10)
        return rc==0 and path.exists(),log
    if shutil.which('import'):
        rc,log=run(['import','-window','root',str(path)],env=env,timeout=10)
        return rc==0 and path.exists(),log
    return False,'no screenshot tool'

def diff_pixels(a,b):
    if not (a.exists() and b.exists()) or not shutil.which('compare'): return None
    p=subprocess.run(['compare','-metric','AE',str(a),str(b),'null:'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    raw=(p.stderr or p.stdout).strip().splitlines()
    try: return int(float(raw[-1])) if raw else None
    except Exception: return None

def key(env,key):
    if not shutil.which('xdotool'): return False
    subprocess.run(['xdotool','key','--clearmodifiers',key],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    return True

def windows(env):
    if not shutil.which('xdotool'): return []
    p=subprocess.run(['xdotool','search','--onlyvisible','--name','.'],env=env,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
    return [x for x in p.stdout.split() if x.strip()]

def choose_command(root: Path, engine: str):
    if engine == 'RPG Maker 2000/2003' and shutil.which('easyrpg-player'):
        return ['easyrpg-player','--window'], 'EasyRPG Player'
    exe=root/'Game.exe'
    if not exe.exists(): exe=root/'RPG_RT.exe'
    if exe.exists() and shutil.which('wine'):
        return ['wine',exe.name], 'Wine/original Windows launcher'
    if engine in ('RPG Maker XP','RPG Maker VX','RPG Maker VX Ace'):
        for c in ('mkxp-z','mkxp'):
            if shutil.which(c): return [c],c
    return None,None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--static',required=True,help='playability_static.json')
    ap.add_argument('--extract-root',required=True,help='directory containing extracted archive')
    ap.add_argument('--outdir',default='playability_smoke')
    args=ap.parse_args()
    st=json.loads(Path(args.static).read_text(encoding='utf-8'))
    extract=Path(args.extract_root).resolve()
    game_root=(extract/st.get('game_root','.')).resolve()
    out=Path(args.outdir); out.mkdir(parents=True,exist_ok=True)
    result={'engine':st.get('engine'),'game_root':str(game_root),'status':'NOT_RUN','runtime':None,'process_alive_boot':False,'visible_windows_boot':0,'title_to_after_input_changed_pixels':None,'after_input_to_movement_changed_pixels':None,'notes':[]}
    cmd,runtime=choose_command(game_root,st.get('engine','UNKNOWN'))
    result['runtime']=runtime
    if not cmd:
        result['status']='NO_CURRENT_RUNTIME_PATH_IN_CI'
        (out/'playability_smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return 0
    display=':99'
    env=os.environ.copy(); env.update({'DISPLAY':display,'WINEDEBUG':'-all','WINEDLLOVERRIDES':'winemenubuilder.exe=d','SDL_AUDIODRIVER':'dummy'})
    xvfb=subprocess.Popen(['Xvfb',display,'-screen','0','1280x720x24','-nolisten','tcp'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    proc=None
    logf=open(out/'runtime.log','w',encoding='utf-8',errors='ignore')
    try:
        time.sleep(1.5)
        proc=subprocess.Popen(cmd,cwd=game_root,env=env,stdout=logf,stderr=subprocess.STDOUT,text=True)
        time.sleep(12)
        alive=proc.poll() is None
        wins=windows(env)
        result['process_alive_boot']=alive; result['visible_windows_boot']=len(wins)
        s1=out/'01_boot.png'; screenshot(env,s1)
        if not alive:
            result['status']='BOOT_FAILED'
            result['notes'].append(f'process exited rc={proc.returncode}')
        else:
            result['status']='BOOT_VERIFIED' if wins else 'PROCESS_ALIVE_NO_VISIBLE_WINDOW'
            # Default RPG Maker title screens normally select New Game first. Multiple confirms also advance splash/intro text.
            for _ in range(3): key(env,'Return'); time.sleep(2)
            time.sleep(5)
            s2=out/'02_after_confirm.png'; screenshot(env,s2)
            result['title_to_after_input_changed_pixels']=diff_pixels(s1,s2)
            # Movement/interaction probe. This is intentionally short and non-destructive.
            for k in ('Down','Right','Up','Left','z','Return'):
                key(env,k); time.sleep(0.8)
            time.sleep(3)
            s3=out/'03_after_movement.png'; screenshot(env,s3)
            result['after_input_to_movement_changed_pixels']=diff_pixels(s2,s3)
            still=proc.poll() is None
            result['process_alive_after_inputs']=still
            d1=result['title_to_after_input_changed_pixels'] or 0
            d2=result['after_input_to_movement_changed_pixels'] or 0
            if still and wins and d1>1000 and d2>300:
                result['status']='GAMEPLAY_LIKELY'
            elif still and wins and d1>1000:
                result['status']='INPUT_RESPONSE_VERIFIED'
            elif still and wins:
                result['status']='BOOT_VERIFIED'
    except Exception as e:
        result['status']='SMOKE_ERROR'; result['notes'].append(repr(e))
    finally:
        if proc and proc.poll() is None:
            try: proc.terminate(); proc.wait(timeout=3)
            except Exception:
                try: proc.kill()
                except Exception: pass
        try: xvfb.terminate(); xvfb.wait(timeout=3)
        except Exception:
            try: xvfb.kill()
            except Exception: pass
        logf.close()
    # Conservative external classification: only a live GUI boot is directly verified. Gameplay is 'likely' until image/behavior evidence is reviewed.
    if result['status'] in ('GAMEPLAY_LIKELY','INPUT_RESPONSE_VERIFIED','BOOT_VERIFIED'):
        result['playability_class']='PLAYABILITY_VERIFIED_BOOT'
    elif result['status']=='BOOT_FAILED':
        result['playability_class']='PLAYABILITY_UNKNOWN_OR_BROKEN_ON_CI'
    else:
        result['playability_class']='PLAYABILITY_UNKNOWN'
    (out/'playability_smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
