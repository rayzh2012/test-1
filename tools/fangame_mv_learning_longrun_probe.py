#!/usr/bin/env python3
import argparse,json,shutil,time
from collections import Counter,deque
from pathlib import Path
from playwright.sync_api import sync_playwright
import fangame_mv_longrun_probe as base

SAVE_JS="""async (slot)=>{try{let r=DataManager.saveGame(slot);if(r&&typeof r.then==='function')r=await r;return {ok:r!==false};}catch(e){return {ok:false,reason:String(e)}}}"""
LOAD_JS="""async (slot)=>{try{let r=DataManager.loadGame(slot);if(r&&typeof r.then==='function')r=await r;if(r===false)return {ok:false,reason:'load_false'};try{if($gameSystem&&$gameSystem.onAfterLoad)$gameSystem.onAfterLoad()}catch(e){};SceneManager.goto(Scene_Map);return {ok:true};}catch(e){return {ok:false,reason:String(e)}}}"""

def dump(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def log(f,x): f.write(json.dumps(x,ensure_ascii=False)+'\n'); f.flush()
def kt(k): return '/'.join(map(str,k))

def save(page,slot):
    try:return page.evaluate(SAVE_JS,slot)
    except Exception as e:return {'ok':False,'reason':repr(e)}
def load(page,slot):
    try:
        r=page.evaluate(LOAD_JS,slot);time.sleep(2);return r
    except Exception as e:return {'ok':False,'reason':repr(e)}

def event_target(state,nav,attempts,risk):
    pos=base.position_of(state)
    if not pos or not nav:return None
    mid,px,py=pos;c=[]
    for ev in state.get('events') or []:
        key=base.event_key(mid,ev)
        if attempts[key]>=(5 if ev.get('has_transfer') else 3):continue
        trig=ev.get('trigger')
        rank=0 if ev.get('has_transfer') else 1 if ev.get('has_battle') else 2 if trig in (1,2) else 3 if trig==0 and (ev.get('has_text') or ev.get('command_count',0)>1) else None
        if rank is None:continue
        ex,ey=ev.get('x'),ev.get('y')
        if not isinstance(ex,int) or not isinstance(ey,int):continue
        goals={}
        for de,g in base.adjacent_xy(ex,ey).items():
            if g in nav['graph']:goals[g]=base.OPPOSITE[de]
        cur=(px,py)
        if cur in goals:dist=0;d=None
        else:
            d,dist=base.bfs_first_step(nav,cur,set(goals))
            if d is None:continue
        c.append((risk[key],rank,dist,attempts[key],ev.get('id',0),ev,d,goals,key))
    if not c:return None
    c.sort(key=lambda x:x[:5]);r,rank,dist,_,_,ev,d,goals,key=c[0]
    if dist==0:return {'kind':'interact' if ev.get('trigger')==0 else 'bump','event':ev,'event_key':key,'direction':goals[(px,py)],'risk':r}
    return {'kind':'route','event':ev,'event_key':key,'direction':d,'distance':dist,'risk':r}

def frontier(state,nav,seen,visits,edge_risk):
    pos=base.position_of(state)
    if not pos or not nav:return None,None
    mid,x,y=pos;opts=[]
    for nx,ny,d in nav['graph'].get((x,y),()):
        nxt=(mid,nx,ny);score=edge_risk[(mid,x,y,d)]+(0 if nxt not in seen else 4+visits[nxt]);opts.append((score,d))
    if not opts:return None,None
    opts.sort();return opts[0][1],opts[0][0]

def learn(recent,erisk,drisk):
    rows=list(recent)[-60:]
    for i,r in enumerate(rows):
        age=len(rows)-i;w=4 if age<=8 else 2 if age<=20 else 1
        if r.get('event_key'):erisk[tuple(r['event_key'])]+=w
        if r.get('edge'):drisk[tuple(r['edge'])]+=w
    return {'recent':len(rows),'events':len({tuple(r['event_key']) for r in rows if r.get('event_key')}),'edges':len({tuple(r['edge']) for r in rows if r.get('edge')})}

def battle(page,state,strategy):
    ratio=sum((a.get('hp',0)/max(1,a.get('mhp',1))) for a in state.get('party') or [])/max(1,len(state.get('party') or []))
    if strategy>=3: base.key_tap(page,'Escape');base.key_tap(page,'ArrowDown');base.key_tap(page,'Enter');return 'battle_escape_probe'
    if strategy>=2 and ratio<.55: base.key_tap(page,'ArrowDown');base.key_tap(page,'Enter');return f'battle_guard_probe_hp{ratio:.2f}'
    base.key_tap(page,'Enter',hold=.1);return f'battle_default_hp{ratio:.2f}'

def guide(out,result,facts,erisk,drisk):
    obj={'schema':'fangame.observed_guide.v0.1','game_id':result.get('game_id'),'rule':'observed_facts are runtime facts; learned_heuristics are not asserted as game facts','observed_facts':facts,'learned_heuristics':{'event_risk':{kt(k):v for k,v in erisk.items() if v},'edge_risk':{kt(k):v for k,v in drisk.items() if v},'battle_strategy_final':result.get('battle_strategy_final')}}
    dump(out/'mv_learning_guide.json',obj)
    lines=['# Observed-facts guide','',f"- elapsed: {result.get('elapsed_play_seconds')} s",f"- maps: {result.get('unique_maps')}",f"- transitions: {result.get('map_transitions')}",f"- battles completed: {result.get('battle_completions')}",f"- deaths: {result.get('deaths')}",f"- checkpoint recoveries: {result.get('checkpoint_recoveries')}",'','## Observed transitions']
    lines += [f"- t={x['t']}s map {x['from_map']} {x['from_xy']} -> map {x['to_map']} {x['to_xy']}" for x in facts['map_transitions']] or ['- none']
    lines += ['','## Observed deaths/recoveries']
    lines += [f"- death #{x['death_no']} t={x['t']}s recovery={x['recovery']} battle_strategy->{x['battle_strategy_after']}" for x in facts['deaths']] or ['- none']
    lines += ['','## Learned avoidance heuristic']
    lines += [f"- event {kt(k)} risk={v}" for k,v in sorted(erisk.items(),key=lambda kv:-kv[1]) if v][:30] or ['- none']
    (out/'mv_learning_guide.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--static',required=True);ap.add_argument('--extract-root',required=True);ap.add_argument('--config',required=True);ap.add_argument('--outdir',required=True);a=ap.parse_args()
    cfg=json.load(open(a.config,encoding='utf-8'));st=json.load(open(a.static,encoding='utf-8'));mins=int(cfg.get('duration_minutes',240));mx=int(cfg.get('max_duration_minutes',240))
    if not 1<=mins<=mx<=240:raise SystemExit('INVALID_DURATION_GUARD')
    root=(Path(a.extract_root).resolve()/st.get('game_root','.')).resolve();out=Path(a.outdir).resolve();out.mkdir(parents=True,exist_ok=True);index=next((p for p in (root/'www'/'index.html',root/'index.html') if p.exists()),None)
    result={'schema':'fangame.mv_learning_longrun.v0.1','mode':'FOUR_HOUR_DEATH_LEARNING_PROOF','game_id':cfg.get('game_id'),'decision_engine':'runtime_symbolic_agent_v0.3_failure_memory_checkpoint_replay','external_ai_api':False,'local_llm':False,'requested_duration_minutes':mins,'max_duration_minutes':mx,'engine':st.get('engine'),'index_html':str(index) if index else None,'status':'NOT_RUN','save_load_verified':False,'long_run_4h_verified':False,'package_identity':cfg.get('package_identity')}
    if not index:dump(out/'mv_learning_summary.json',result);return 2
    result['index_uri']=index.as_uri();trace=open(out/'mv_learning_trace.jsonl','w',encoding='utf-8')
    visits=Counter();seen=set();maps=set();scenes=Counter();attempts=Counter();erisk=Counter();drisk=Counter();recent=deque(maxlen=int(cfg.get('learning_window_actions',120)));nav={};facts={'map_transitions':[],'deaths':[],'checkpoints':[]};prev=None
    trans=coords=actions=bst=bco=stalls=nref=route_steps=interacts=front_steps=deaths=recovs=loadfails=restarts=0;bactive=False;strategy=0;fatal=None;slot=int(cfg.get('save_slot',20));checkpoint=None
    try:
      with sync_playwright() as p:
        kw={'headless':True,'args':['--allow-file-access-from-files','--autoplay-policy=no-user-gesture-required','--disable-web-security','--no-sandbox','--disable-gpu']};chrome=shutil.which('google-chrome') or shutil.which('google-chrome-stable') or shutil.which('chromium');
        if chrome:kw['executable_path']=chrome
        browser=p.chromium.launch(**kw);page=browser.new_page(viewport={'width':1280,'height':720});first=base.bootstrap_to_map(page,result,out,int(cfg.get('max_intro_confirms',360)))
        if not first:result['status']='INTRO_NOT_CLEARED';browser.close();raise RuntimeError('INTRO_NOT_CLEARED')
        s=save(page,slot)
        if s.get('ok'):checkpoint={'t':0,'slot':slot,'state':base.snap_state(page)};facts['checkpoints'].append(checkpoint)
        started=time.monotonic();deadline=started+mins*60;lastprog=lastsave=started;lastshot=started;shot=2;loop=0
        while time.monotonic()<deadline:
          loop+=1;state=base.snap_state(page);now=time.monotonic();t=now-started;scene=state.get('scene');scenes[str(scene)]+=1;pos=base.position_of(state)
          if pos:maps.add(pos[0]);visits[pos]+=1;lastprog=now if pos not in seen else lastprog;seen.add(pos)
          if prev:
            if state.get('map_id')!=prev.get('map_id') and state.get('map_id') is not None:
              trans+=1;lastprog=now;pp=base.position_of(prev);cp=base.position_of(state);facts['map_transitions'].append({'t':round(t,3),'from_map':prev.get('map_id'),'from_xy':list(pp[1:]) if pp else None,'to_map':state.get('map_id'),'to_xy':list(cp[1:]) if cp else None})
            p0,p1=prev.get('player') or {},state.get('player') or {}
            if state.get('map_id')==prev.get('map_id') and (p0.get('x'),p0.get('y'))!=(p1.get('x'),p1.get('y')):coords+=1
          inb=scene=='Scene_Battle' or state.get('in_battle') is True
          if inb and not bactive:bactive=True;bst+=1;lastprog=now
          elif bactive and not inb and scene=='Scene_Map':bactive=False;bco+=1;lastprog=now
          if scene=='Scene_Gameover':
            deaths+=1;lrn=learn(recent,erisk,drisk);strategy=min(3,strategy+1) if bactive or any(r.get('in_battle') for r in recent) else strategy;r=load(page,slot) if checkpoint else {'ok':False}
            if r.get('ok'):recovs+=1;recovery='checkpoint_load';result['save_load_verified']=base.snap_state(page).get('scene')!='Scene_Gameover';bactive=False;prev=None
            else:
              loadfails+=1;page.reload(wait_until='domcontentloaded',timeout=30000);time.sleep(3);rr=base.bootstrap_to_map(page,result,out,int(cfg.get('max_intro_confirms',360)))
              if rr:restarts+=1;recovery='full_restart';bactive=False;prev=None;sv=save(page,slot);checkpoint={'t':round(time.monotonic()-started,3),'slot':slot,'state':base.snap_state(page)} if sv.get('ok') else None
              else:fatal='GAME_OVER_RECOVERY_FAILED';recovery='failed'
            facts['deaths'].append({'death_no':deaths,'t':round(t,3),'recovery':recovery,'learning':lrn,'battle_strategy_after':strategy});log(trace,{'t':round(t,3),'action':'death_learn_recover','recovery':recovery,'learning':lrn});recent.clear();lastprog=time.monotonic()
            if fatal:break
            continue
          safe=scene=='Scene_Map' and pos and state.get('message_busy') is False and state.get('event_running') is False and not inb and all(not x.get('dead') for x in state.get('party') or [])
          if safe and now-lastsave>=float(cfg.get('autosave_seconds',45)):
            r=save(page,slot)
            if r.get('ok'):checkpoint={'t':round(t,3),'slot':slot,'state':state};facts['checkpoints'].append(checkpoint);lastsave=now
          ek=edge=None
          if state.get('message_busy') is True or state.get('event_running') is True:act='confirm_event';base.key_tap(page,'Enter')
          elif inb:act=battle(page,state,strategy)
          elif scene=='Scene_Map' and pos:
            mid,x,y=pos
            if mid not in nav:nav[mid]=base.build_nav(page.evaluate(base.NAV_JS));nref+=1
            tg=event_target(state,nav[mid],attempts,erisk)
            if tg:
              d=tg['direction'];ek=list(tg['event_key']);edge=[mid,x,y,d]
              if tg['kind']=='route':act=f"route_event_{tg['event'].get('id')}_risk{tg['risk']}";base.move_one(page,d);route_steps+=1
              elif tg['kind']=='bump':act=f"bump_event_{tg['event'].get('id')}_risk{tg['risk']}";attempts[tg['event_key']]+=1;base.move_one(page,d);interacts+=1
              else:act=f"interact_event_{tg['event'].get('id')}_risk{tg['risk']}";attempts[tg['event_key']]+=1;base.key_tap(page,base.KEY_FOR_DIR[d]);base.key_tap(page,'Enter');interacts+=1
            else:
              d,score=frontier(state,nav[mid],seen,visits,drisk)
              if d is not None:edge=[mid,x,y,d];act=f'frontier_score{score}';base.move_one(page,d);front_steps+=1
              else:act='probe';base.key_tap(page,'Enter');d=base.DIRS[loop%4];edge=[mid,x,y,d];base.move_one(page,d)
          elif scene in ('Scene_Menu','Scene_Item','Scene_Skill','Scene_Equip','Scene_Status','Scene_Options'):act='escape_menu';base.key_tap(page,'Escape')
          else:act='generic_confirm';base.key_tap(page,'Enter')
          actions+=1;rec={'t':round(t,3),'state':state,'action':act,'event_key':ek,'edge':edge,'in_battle':inb};log(trace,rec);recent.append(rec)
          if now-lastprog>=float(cfg.get('stall_seconds',25)):
            stalls+=1;base.key_tap(page,'Enter');base.key_tap(page,'Escape');[base.move_one(page,d) for d in (6,2,4,8)];lastprog=time.monotonic()
          if now-lastshot>=float(cfg.get('checkpoint_seconds',300)):page.screenshot(path=str(out/f'{shot:03d}_checkpoint.png'));shot+=1;lastshot=now
          prev=state;time.sleep(.12)
        elapsed=time.monotonic()-started;result['final_state']=base.snap_state(page);browser.close()
    except Exception as e:
      if result.get('status')=='NOT_RUN':result['status']='LONGRUN_PROBE_ERROR';result['fatal_stop']=repr(e)
    trace.close();route_ok=trans>0 or bco>0 or len(seen)>=25;enough=len(maps)>=2 and coords>=40 and fatal is None
    result.update({'elapsed_play_seconds':round(locals().get('elapsed',0),3),'actions':actions,'unique_maps':sorted(maps),'unique_map_count':len(maps),'unique_position_count':len(seen),'map_transitions':trans,'coordinate_changes':coords,'battle_starts':bst,'battle_completions':bco,'stalls_recovered':stalls,'nav_refreshes':nref,'event_route_steps':route_steps,'event_interactions':interacts,'frontier_steps':front_steps,'scene_counts':dict(scenes),'fatal_stop':fatal or result.get('fatal_stop'),'deaths':deaths,'checkpoint_recoveries':recovs,'checkpoint_failures':loadfails,'full_restarts':restarts,'battle_strategy_final':strategy,'death_learning_exercised':deaths>0 and (recovs>0 or restarts>0),'battle_verified':bco>0,'route_progress_verified':route_ok and fatal is None})
    result['long_run_4h_verified']=result['elapsed_play_seconds']>=14400 and enough
    if result['long_run_4h_verified'] and deaths and recovs:result['status']='LONG_RUN_4H_VERIFIED_WITH_DEATH_LEARNING'
    elif result['long_run_4h_verified']:result['status']='LONG_RUN_4H_VERIFIED'
    elif result['elapsed_play_seconds']>=mins*60*.98 and route_ok and fatal is None:result['status']='LONGRUN_DURATION_REACHED_PROGRESS_OBSERVED'
    elif fatal:result['status']=f'LONGRUN_STOPPED_{fatal}'
    elif result.get('status')=='NOT_RUN':result['status']='LONGRUN_INCOMPLETE'
    guide(out,result,facts,erisk,drisk);dump(out/'mv_learning_summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['status'] in {'LONG_RUN_4H_VERIFIED_WITH_DEATH_LEARNING','LONG_RUN_4H_VERIFIED','LONGRUN_DURATION_REACHED_PROGRESS_OBSERVED'} else 4

if __name__=='__main__':raise SystemExit(main())
