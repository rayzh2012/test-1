#!/usr/bin/env python3
import argparse, json, shutil, time
from pathlib import Path
from playwright.sync_api import sync_playwright

STATE_JS = r'''() => {
  const out = {};
  try { out.scene = (window.SceneManager && SceneManager._scene && SceneManager._scene.constructor) ? SceneManager._scene.constructor.name : null; } catch(e) { out.scene_error=String(e); }
  try { out.map_id = window.$gameMap ? $gameMap.mapId() : null; } catch(e) { out.map_error=String(e); }
  try { out.player = window.$gamePlayer ? {x:$gamePlayer.x,y:$gamePlayer.y,direction:$gamePlayer.direction(),moving:$gamePlayer.isMoving(),transparent:$gamePlayer.isTransparent()} : null; } catch(e) { out.player_error=String(e); }
  try { out.message_busy = window.$gameMessage ? $gameMessage.isBusy() : null; } catch(e) { out.message_error=String(e); }
  try { out.event_running = window.$gameMap && $gameMap._interpreter ? $gameMap._interpreter.isRunning() : null; } catch(e) { out.event_error=String(e); }
  try { out.party_size = window.$gameParty ? $gameParty.members().length : null; } catch(e) { out.party_error=String(e); }
  return out;
}'''


def snap_state(page):
    try:
        return page.evaluate(STATE_JS)
    except Exception as e:
        return {'eval_error':repr(e)}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--static', required=True)
    ap.add_argument('--extract-root', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--max-confirms', type=int, default=260)
    args=ap.parse_args()

    st=json.loads(Path(args.static).read_text(encoding='utf-8'))
    extract=Path(args.extract_root).resolve(); root=(extract/st.get('game_root','.')).resolve()
    out=Path(args.outdir).resolve(); out.mkdir(parents=True,exist_ok=True)
    index=next((p for p in (root/'www'/'index.html', root/'index.html') if p.exists()),None)
    result={'schema':'fangame.mv_map_control_probe.v0.1','engine':st.get('engine'),'game_root':str(root),'index_html':str(index) if index else None,'checkpoints':[],'status':'NOT_RUN'}
    if not index:
        result['status']='NO_INDEX_HTML'; result['playability_class']='PLAYABILITY_UNKNOWN'
        (out/'mv_map_control_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return 0

    try:
        with sync_playwright() as p:
            kwargs={'headless':True,'args':['--allow-file-access-from-files','--autoplay-policy=no-user-gesture-required','--disable-web-security','--no-sandbox','--disable-gpu']}
            chrome=shutil.which('google-chrome') or shutil.which('google-chrome-stable') or shutil.which('chromium')
            if chrome: kwargs['executable_path']=chrome
            browser=p.chromium.launch(**kwargs)
            page=browser.new_page(viewport={'width':1280,'height':720})
            result['console']=[]; result['page_errors']=[]
            page.on('console',lambda m: result['console'].append({'type':m.type,'text':m.text[:1000]}))
            page.on('pageerror',lambda e: result['page_errors'].append(str(e)[:3000]))
            page.goto(index.as_uri(),wait_until='domcontentloaded',timeout=30000)
            time.sleep(15)
            page.screenshot(path=str(out/'00_title.png'))
            result['title_state']=snap_state(page)

            # Start New Game from the default title-menu selection.
            page.keyboard.press('Enter'); time.sleep(3)
            result['after_new_game_enter']=snap_state(page)
            page.screenshot(path=str(out/'01_after_new_game.png'))

            controllable=None
            stable_candidate_count=0
            last_candidate=None
            for i in range(args.max_confirms):
                state=snap_state(page)
                if i % 10 == 0:
                    result['checkpoints'].append({'confirm_index':i,'state':state})
                # A conservative controllable-map candidate: Scene_Map, valid map/player,
                # no active message and no autorun interpreter. Require it repeatedly.
                candidate=(state.get('scene')=='Scene_Map' and isinstance(state.get('map_id'),int) and state.get('map_id',0)>0 and isinstance(state.get('player'),dict) and state.get('message_busy') is False and state.get('event_running') is False)
                sig=(state.get('map_id'), (state.get('player') or {}).get('x'), (state.get('player') or {}).get('y'))
                if candidate:
                    if sig==last_candidate: stable_candidate_count += 1
                    else: stable_candidate_count=1; last_candidate=sig
                    if stable_candidate_count >= 2:
                        controllable={'confirm_index':i,'state':state}; break
                else:
                    stable_candidate_count=0; last_candidate=None
                page.keyboard.press('Enter')
                time.sleep(0.35)

            result['controllable_candidate']=controllable
            page.screenshot(path=str(out/'02_candidate_map.png'))

            movement=[]
            moved=False
            if controllable:
                before=snap_state(page); result['before_movement']=before
                for key in ('ArrowRight','ArrowDown','ArrowLeft','ArrowUp'):
                    b=snap_state(page)
                    page.keyboard.down(key); time.sleep(0.8); page.keyboard.up(key); time.sleep(0.8)
                    a=snap_state(page)
                    rec={'key':key,'before':b,'after':a}
                    movement.append(rec)
                    pb=b.get('player') or {}; pa=a.get('player') or {}
                    if isinstance(pb,dict) and isinstance(pa,dict) and (pb.get('x'),pb.get('y')) != (pa.get('x'),pa.get('y')):
                        moved=True; break
                result['movement_attempts']=movement
                result['player_coordinate_changed']=moved
                page.screenshot(path=str(out/'03_after_movement.png'))

            result['final_state']=snap_state(page)
            result['page_still_open']=not page.is_closed()
            browser.close()

        if controllable and moved:
            result['status']='MAP_GAMEPLAY_VERIFIED_BY_PLAYER_COORDINATE_CHANGE'
            result['playability_class']='PLAYABILITY_VERIFIED_MAP_GAMEPLAY'
            result['map_gameplay_verified']=True
        elif controllable:
            result['status']='CONTROLLABLE_MAP_STATE_REACHED_MOVEMENT_NOT_CONFIRMED'
            result['playability_class']='PLAYABILITY_VERIFIED_NEW_GAME'
            result['map_gameplay_verified']=False
        else:
            result['status']='INTRO_NOT_CLEARED_TO_IDLE_MAP_WITHIN_CONFIRM_BUDGET'
            result['playability_class']='PLAYABILITY_VERIFIED_NEW_GAME'
            result['map_gameplay_verified']=False
    except Exception as e:
        result['status']='MAP_CONTROL_PROBE_ERROR'; result['playability_class']='PLAYABILITY_UNKNOWN'; result['error']=repr(e)

    (out/'mv_map_control_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
