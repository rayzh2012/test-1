#!/usr/bin/env python3
"""Survival-learning v0.4 for RPG Maker MV.

Adds three conservative runtime policies over v0.3/v0.2:
1) structural healing/revival skill semantics from the live battle windows/database;
2) one escape attempt per encounter signature, then fight/guard/heal instead of escape spam;
3) transfer-loop suppression so repeated exits yield to local frontier exploration.

All gameplay actions remain real keyboard input. Runtime state is observed only; HP, MP,
items, switches, variables, map state, and battle outcomes are never directly mutated.
"""
from collections import Counter
from pathlib import Path
import sys

import fangame_mv_survival_learning_probe_v3_playlog as playlog
import fangame_mv_survival_learning_probe_v2 as v2
import fangame_mv_learning_longrun_probe as agent

BATTLE_V4_JS = r'''() => {
  const s = window.SceneManager ? SceneManager._scene : null;
  if (!s) return {windows:[], inventory:[], can_escape:null, actor_skills:[], current_actor:null};
  const names = ['_partyCommandWindow','_actorCommandWindow','_skillWindow','_itemWindow','_enemyWindow','_actorWindow'];
  const simplifyEffect = e => e ? {code:e.code,dataId:e.dataId,value1:e.value1,value2:e.value2} : null;
  const simplifyObj = (o,i) => o ? ({
    index:i,id:o.id,name:o.name||'',scope:o.scope,occasion:o.occasion,
    mpCost:o.mpCost||0,tpCost:o.tpCost||0,
    damage:o.damage ? {type:o.damage.type,formula:o.damage.formula||'',variance:o.damage.variance||0,elementId:o.damage.elementId} : null,
    effects:Array.isArray(o.effects)?o.effects.map(simplifyEffect):[]
  }) : null;
  const windows=[];
  for (const n of names) {
    const w=s[n]; if(!w) continue;
    let commands=[]; let data=[]; let index=-1;
    try { index=(typeof w.index==='function') ? w.index() : w._index; } catch(e) {}
    try { commands=Array.isArray(w._list) ? w._list.map((c,i)=>({index:i,name:c&&c.name!=null?String(c.name):null,symbol:c&&c.symbol!=null?String(c.symbol):null,enabled:!c||c.enabled!==false,ext:c?c.ext:null})) : []; } catch(e) {}
    try { data=Array.isArray(w._data) ? w._data.map(simplifyObj) : []; } catch(e) {}
    windows.push({name:n,active:!!w.active,visible:!!w.visible,index:index,commands:commands,data:data});
  }
  let inventory=[];
  try { inventory=$gameParty.items().map((o,i)=>Object.assign(simplifyObj(o,i),{count:$gameParty.numItems(o)})); } catch(e) {}
  let can_escape=null; try {can_escape=BattleManager.canEscape?!!BattleManager.canEscape():null;}catch(e){}
  let current_actor=null, actor_skills=[];
  try {
    const a=BattleManager.actor ? BattleManager.actor() : null;
    if(a){
      current_actor={id:a.actorId(),name:a.name(),hp:a.hp,mhp:a.mhp,mp:a.mp,mmp:a.mmp,tp:a.tp};
      actor_skills=a.skills().map((o,i)=>Object.assign(simplifyObj(o,i),{usable:a.canUse?!!a.canUse(o):true}));
    }
  } catch(e) {}
  return {windows:windows,inventory:inventory,can_escape:can_escape,current_actor:current_actor,actor_skills:actor_skills};
}'''


def read_ui_v4(page):
    try: return page.evaluate(BATTLE_V4_JS)
    except Exception: return {'windows':[], 'inventory':[], 'can_escape':None, 'actor_skills':[], 'current_actor':None}


def friend_scope(x):
    return int(x.get('scope') or 0) in (7,8,9,10,11)


def revive_semantic(x):
    return friend_scope(x) and (int(x.get('scope') or 0) in (9,10) or v2.revive_effect(x))


def heal_semantic(x):
    if not friend_scope(x): return False
    dmg=x.get('damage') or {}
    return int(dmg.get('type') or 0)==3 or v2.hp_effect(x)>0


def heal_score(x):
    score=v2.hp_effect(x)
    if int((x.get('damage') or {}).get('type') or 0)==3: score=max(score,5000.0)
    if revive_semantic(x): score+=1e9
    return score


def usable_survival_skills(ui, want_revive=False):
    out=[]
    for x in ui.get('actor_skills') or []:
        if not x or x.get('usable') is False: continue
        if want_revive and revive_semantic(x): out.append(x)
        elif not want_revive and heal_semantic(x): out.append(x)
    return out


def choose_skill(page,w,want_revive=False):
    data=[x for x in (w.get('data') or []) if x]
    cand=[]
    for x in data:
        if want_revive and revive_semantic(x): cand.append((1e12+heal_score(x),x))
        elif not want_revive and heal_semantic(x): cand.append((heal_score(x),x))
    if not cand:return None
    cand.sort(key=lambda z:(-z[0],int(z[1].get('mpCost') or 0),z[1].get('index',0)))
    x=cand[0][1]
    v2.move_index(page,w.get('index'),int(x['index']),len(w.get('data') or []))
    agent.base.key_tap(page,'Enter',hold=.07)
    return x


_escape_attempts=Counter()
_last_battle_turn={}

def battle_sig(state):
    enemies=tuple((e.get('name'),e.get('mhp')) for e in (state.get('enemies') or []))
    return (state.get('map_id'),enemies)


def smart_battle_v4(page,state,strategy):
    party=state.get('party') or []
    living=[a for a in party if not a.get('dead')]
    ratios=[a.get('hp',0)/max(1,a.get('mhp',1)) for a in living]
    minr=min(ratios) if ratios else 0.; avgr=sum(ratios)/len(ratios) if ratios else 0.; dead=sum(1 for a in party if a.get('dead'))
    ui=read_ui_v4(page); ws=ui.get('windows') or []; active=next((w for w in ws if w.get('active') and w.get('visible')),None)
    inv=ui.get('inventory') or []; heals=v2.usable_heals(inv)
    revive_items=[x for x in heals if v2.revive_effect(x)]; heal_items=[x for x in heals if v2.hp_effect(x)>0]
    revive_skills=usable_survival_skills(ui,True); heal_skills=usable_survival_skills(ui,False)
    critical=dead>0 or minr<.32 or avgr<.42
    # Failure memory should make the agent more decisive, not permanently defensive.
    # A permanent strategy>=1 danger flag caused endless Guard loops after the first death.
    danger=critical or minr < max(.42, .58 - .05*min(int(strategy or 0),3))
    actor=ui.get('current_actor') or {}; mp_ratio=(actor.get('mp',0)/max(1,actor.get('mmp',1))) if actor else 0.0
    sig=battle_sig(state)
    turn=int(((state.get('battle_ui') or {}).get('turn_count')) or 0)
    prior_turn=_last_battle_turn.get(sig)
    if prior_turn is not None and turn < prior_turn:
        # A new encounter with the same troop signature must get a fresh escape chance.
        # Keeping the old counter across checkpoint recovery made every replay unwinnable.
        _escape_attempts[sig]=0
    _last_battle_turn[sig]=turn
    if active:
        n=active.get('name')
        if n=='_partyCommandWindow':
            max_escape_attempts=1 + min(int(strategy or 0),1)
            allow_escape=critical and ui.get('can_escape') is not False and _escape_attempts[sig] < max_escape_attempts
            pref=['escape','fight'] if allow_escape else ['fight','escape']
            c=v2.choose_command(page,active,pref)
            if c=='escape': _escape_attempts[sig]+=1
            if c:return f'battle_v4_party_{c}_critical{int(critical)}_escapes{_escape_attempts[sig]}_minhp{minr:.2f}'
        if n=='_actorCommandWindow':
            have_revive=bool(revive_items or revive_skills); have_heal=bool(heal_items or heal_skills)
            skill_first=(dead and bool(revive_skills)) or (danger and bool(heal_skills) and mp_ratio>=.18)
            if skill_first: pref=['skill','item','guard','attack']
            elif (dead and revive_items) or (danger and heal_items): pref=['item','skill','guard','attack']
            elif danger and have_heal: pref=['skill','item','guard','attack']
            elif danger:
                # With no usable survival resource, guarding forever cannot end the encounter.
                # Guard at most one turn in three; attack on the other turns so the route can resume.
                turn=int(((state.get('battle_ui') or {}).get('turn_count')) or 0)
                pref=['guard','attack','skill','item'] if turn % 3 == 0 else ['attack','guard','skill','item']
            else: pref=['attack','skill','guard','item']
            c=v2.choose_command(page,active,pref)
            if c:return f'battle_v4_actor_{c}_danger{int(danger)}_healitems{len(heal_items)}_healskills{len(heal_skills)}_mp{mp_ratio:.2f}_minhp{minr:.2f}'
        if n=='_skillWindow':
            x=choose_skill(page,active,want_revive=dead>0 and bool(revive_skills))
            if x:return f"battle_v4_skill_{x.get('id')}_{x.get('name','')}_revive{int(revive_semantic(x))}_heal{int(heal_semantic(x))}_mpcost{int(x.get('mpCost') or 0)}"
            agent.base.key_tap(page,'Escape',hold=.05);return 'battle_v4_skill_no_survival_skill_back'
        if n=='_itemWindow':
            x=v2.choose_data_item(page,active,want_revive=dead>0 and bool(revive_items))
            if x:return f"battle_v4_item_{x.get('id')}_{x.get('name','')}_revive{int(v2.revive_effect(x))}_heal{v2.hp_effect(x):.0f}"
            agent.base.key_tap(page,'Escape',hold=.05);return 'battle_v4_item_no_survival_item_back'
        if n=='_actorWindow':
            target=v2.choose_actor(page,active,party,prefer_dead=dead>0)
            return f'battle_v4_actor_target_{target}_deadpref{int(dead>0)}'
        if n=='_enemyWindow':
            agent.base.key_tap(page,'Enter',hold=.07);return 'battle_v4_enemy_confirm'
    agent.base.key_tap(page,'Enter',hold=.08)
    return f'battle_v4_generic_minhp{minr:.2f}'


# Scene_Shop is a modal UI, not a running story event. The shared agent's generic
# event branch presses Enter forever there. Keep this repair v4-local so the current
# four-hour v3 candidate is not restarted; exit only through the game's real Escape key.
_original_snap_state = agent.base.snap_state
_original_key_tap = agent.base.key_tap
_latest_runtime_scene = None


def snap_state_v4(page):
    global _latest_runtime_scene
    state = _original_snap_state(page)
    _latest_runtime_scene = state.get('scene')
    return state


def key_tap_v4(page, key, *args, **kwargs):
    if _latest_runtime_scene == 'Scene_Shop' and key == 'Enter':
        key = 'Escape'
    return _original_key_tap(page, key, *args, **kwargs)


agent.base.snap_state = snap_state_v4
agent.base.key_tap = key_tap_v4

_route_calls=0
_repeat_transfer_skip=Counter()
_last_route_map=None
_local_after_transfer_budget=0

def event_target_v4(state,nav,attempts,risk):
    global _route_calls,_last_route_map,_local_after_transfer_budget
    _route_calls+=1
    if _route_calls % 220 == 0:
        for k in list(attempts):
            if attempts[k]>0: attempts[k]-=1
    pos=agent.base.position_of(state)
    if not pos or not nav:return None
    mid,px,py=pos
    if _last_route_map is not None and mid != _last_route_map:
        # After a real transfer, spend a bounded window on reachable local events.
        # This prevents immediate A<->B exit ping-pong while still allowing travel later.
        _local_after_transfer_budget=90
    _last_route_map=mid
    if _local_after_transfer_budget>0:
        _local_after_transfer_budget-=1
    c=[];nontransfer=0
    for ev in state.get('events') or []:
        key=agent.base.event_key(mid,ev); is_transfer=bool(ev.get('has_transfer'))
        if attempts[key]>=3:continue
        trig=ev.get('trigger')
        rank=0 if is_transfer and attempts[key]==0 else 1 if ev.get('has_battle') else 2 if trig in (1,2) else 3 if trig==0 and (ev.get('has_text') or ev.get('command_count',0)>1) else 4 if is_transfer else None
        if rank is None:continue
        ex,ey=ev.get('x'),ev.get('y')
        if not isinstance(ex,int) or not isinstance(ey,int):continue
        goals={}
        for de,g in agent.base.adjacent_xy(ex,ey).items():
            if g in nav['graph']:goals[g]=agent.base.OPPOSITE[de]
        cur=(px,py)
        if cur in goals:dist=0;d=None
        else:
            d,dist=agent.base.bfs_first_step(nav,cur,set(goals))
            if d is None:continue
        c.append((rank,risk[key],dist,attempts[key],ev.get('id',0),is_transfer,ev,d,goals,key))
        if not is_transfer: nontransfer+=1
    if not c:return None
    if _local_after_transfer_budget>0 and nontransfer:
        local=[x for x in c if not x[5]]
        if local:c=local
    repeated_only=nontransfer==0 and all(x[5] and x[3]>=1 for x in c)
    if repeated_only:
        _repeat_transfer_skip[mid]+=1
        if _repeat_transfer_skip[mid] < 24:return None
        _repeat_transfer_skip[mid]=0
    c.sort(key=lambda x:x[:5]);rank,r,dist,_,_,_,ev,d,goals,key=c[0]
    if dist==0:return {'kind':'interact' if ev.get('trigger')==0 else 'bump','event':ev,'event_key':key,'direction':goals[(px,py)],'risk':r}
    return {'kind':'route','event':ev,'event_key':key,'direction':d,'distance':dist,'risk':r}


agent.battle=smart_battle_v4
agent.event_target=event_target_v4

if __name__=='__main__':
    outdir=None
    if '--outdir' in sys.argv:
        try: outdir=Path(sys.argv[sys.argv.index('--outdir')+1]).resolve()
        except Exception: outdir=None
    rc=agent.main()
    if outdir: playlog.compact_playlog(outdir/'mv_learning_trace.jsonl',outdir)
    raise SystemExit(rc)
