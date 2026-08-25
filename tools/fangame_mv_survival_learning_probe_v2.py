#!/usr/bin/env python3
"""Healing-aware survival policy for the zero-cost RPG Maker MV learning probe.

The policy reads runtime battle UI/database metadata to choose REAL keyboard inputs.
It never directly mutates HP, MP, items, switches, variables, battle outcomes, or map state.
"""
import fangame_mv_learning_longrun_probe as agent

UI_JS = r'''() => {
  const s = window.SceneManager ? SceneManager._scene : null;
  if (!s) return {windows:[], inventory:[], can_escape:null};
  const names = ['_partyCommandWindow','_actorCommandWindow','_skillWindow','_itemWindow','_enemyWindow','_actorWindow'];
  const windows=[];
  const simplifyEffect = e => e ? {code:e.code,dataId:e.dataId,value1:e.value1,value2:e.value2} : null;
  for (const n of names) {
    const w=s[n]; if(!w) continue;
    let commands=[]; let data=[]; let index=-1;
    try { index=(typeof w.index==='function') ? w.index() : w._index; } catch(e) {}
    try {
      commands=Array.isArray(w._list) ? w._list.map((c,i)=>({index:i,name:c&&c.name!=null?String(c.name):null,symbol:c&&c.symbol!=null?String(c.symbol):null,enabled:!c||c.enabled!==false,ext:c?c.ext:null})) : [];
    } catch(e) {}
    try {
      data=Array.isArray(w._data) ? w._data.map((o,i)=>o?({index:i,id:o.id,name:o.name||'',scope:o.scope,occasion:o.occasion,effects:Array.isArray(o.effects)?o.effects.map(simplifyEffect):[]}):null) : [];
    } catch(e) {}
    windows.push({name:n,active:!!w.active,visible:!!w.visible,index:index,commands:commands,data:data});
  }
  let inventory=[];
  try {
    inventory=$gameParty.items().map(o=>({id:o.id,name:o.name||'',scope:o.scope,occasion:o.occasion,count:$gameParty.numItems(o),effects:Array.isArray(o.effects)?o.effects.map(simplifyEffect):[]}));
  } catch(e) {}
  let can_escape=null; try {can_escape=BattleManager.canEscape?!!BattleManager.canEscape():null;}catch(e){}
  return {windows:windows,inventory:inventory,can_escape:can_escape};
}'''


def read_ui(page):
    try: return page.evaluate(UI_JS)
    except Exception: return {'windows':[], 'inventory':[], 'can_escape':None}


def move_index(page, current, target, count):
    if not isinstance(current,int) or current < 0: current=0
    if not count or count <= 0: return
    down=(target-current)%count; up=(current-target)%count
    key='ArrowDown' if down <= up else 'ArrowUp'; steps=min(down,up)
    for _ in range(steps): agent.base.key_tap(page,key,hold=0.035)


def choose_command(page,w,preferred):
    cs=[c for c in (w.get('commands') or []) if c and c.get('enabled',True)]
    by={c.get('symbol'):c for c in cs}
    c=next((by[x] for x in preferred if x in by),None)
    if not c:return None
    move_index(page,w.get('index'),int(c['index']),len(w.get('commands') or []));agent.base.key_tap(page,'Enter',hold=.07);return c.get('symbol')


def hp_effect(item):
    # RPG Maker MV Game_Action.EFFECT_RECOVER_HP = 11.
    vals=[e for e in item.get('effects') or [] if e and e.get('code')==11]
    if not vals:return 0.0
    return max(float(e.get('value1') or 0)*10000 + float(e.get('value2') or 0) for e in vals)


def revive_effect(item):
    # Death is normally state 1; EFFECT_REMOVE_STATE = 22.
    return any(e and e.get('code')==22 and e.get('dataId')==1 for e in item.get('effects') or [])


def usable_heals(inv):
    return [x for x in inv if x.get('count',0)>0 and (hp_effect(x)>0 or revive_effect(x))]


def choose_data_item(page,w,want_revive=False):
    data=[x for x in (w.get('data') or []) if x]
    cand=[]
    for x in data:
        rev=revive_effect(x); heal=hp_effect(x)
        if want_revive and rev: score=1e12+heal
        elif not want_revive and heal>0: score=heal
        else: continue
        cand.append((score,x))
    if not cand:return None
    cand.sort(key=lambda z:(-z[0],z[1].get('index',0)));x=cand[0][1]
    move_index(page,w.get('index'),int(x['index']),len(w.get('data') or []));agent.base.key_tap(page,'Enter',hold=.07);return x


def choose_actor(page,w,party,prefer_dead=False):
    if not party:agent.base.key_tap(page,'Enter',hold=.07);return None
    if prefer_dead:
        ids=[i for i,a in enumerate(party) if a.get('dead')]
        target=ids[0] if ids else min(range(len(party)),key=lambda i:party[i].get('hp',0)/max(1,party[i].get('mhp',1)))
    else:
        living=[i for i,a in enumerate(party) if not a.get('dead')]
        target=min(living,key=lambda i:party[i].get('hp',0)/max(1,party[i].get('mhp',1))) if living else 0
    move_index(page,w.get('index'),target,len(party));agent.base.key_tap(page,'Enter',hold=.07);return target


def smart_battle_v2(page,state,strategy):
    party=state.get('party') or []
    living=[a for a in party if not a.get('dead')]
    ratios=[a.get('hp',0)/max(1,a.get('mhp',1)) for a in living]
    minr=min(ratios) if ratios else 0.; avgr=sum(ratios)/len(ratios) if ratios else 0.; dead=sum(1 for a in party if a.get('dead'))
    u=read_ui(page);ws=u.get('windows') or [];active=next((w for w in ws if w.get('active') and w.get('visible')),None);inv=u.get('inventory') or [];heals=usable_heals(inv)
    critical=dead>0 or minr<.32 or avgr<.42; danger=critical or minr<.55 or strategy>=1
    has_revive=any(revive_effect(x) for x in heals);has_heal=any(hp_effect(x)>0 for x in heals)
    if active:
        n=active.get('name')
        if n=='_partyCommandWindow':
            pref=['escape','fight'] if critical and u.get('can_escape') is not False else ['fight','escape']
            c=choose_command(page,active,pref)
            if c:return f'battle_party_{c}_critical{int(critical)}_minhp{minr:.2f}'
        if n=='_actorCommandWindow':
            # Use real healing/revival items before passive guard when survival is threatened.
            pref=(['item','guard','skill','attack'] if (dead and has_revive) or (danger and has_heal) else ['guard','skill','attack','item'] if danger else ['attack','skill','guard','item'])
            c=choose_command(page,active,pref)
            if c:return f'battle_actor_{c}_danger{int(danger)}_items{len(heals)}_minhp{minr:.2f}'
        if n=='_itemWindow':
            x=choose_data_item(page,active,want_revive=dead>0 and has_revive)
            if x:return f"battle_item_{x.get('id')}_{x.get('name','')}_revive{int(revive_effect(x))}_heal{hp_effect(x):.0f}"
            agent.base.key_tap(page,'Escape',hold=.05);return 'battle_item_no_survival_item_back'
        if n=='_actorWindow':
            target=choose_actor(page,active,party,prefer_dead=dead>0 and has_revive)
            return f'battle_actor_target_{target}_deadpref{int(dead>0 and has_revive)}'
        if n=='_enemyWindow':agent.base.key_tap(page,'Enter',hold=.07);return 'battle_enemy_confirm'
        if n=='_skillWindow':
            # We do not yet assert spell semantics from names. Back out under danger; default first skill otherwise.
            if danger:agent.base.key_tap(page,'Escape',hold=.05);return 'battle_skill_back_danger'
            agent.base.key_tap(page,'Enter',hold=.07);return 'battle_skill_first'
    return agent.battle_original(page,state,strategy)

agent.battle_original=agent.battle
agent.battle=smart_battle_v2

if __name__=='__main__':raise SystemExit(agent.main())
