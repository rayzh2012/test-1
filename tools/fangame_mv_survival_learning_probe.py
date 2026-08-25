#!/usr/bin/env python3
"""Survival-policy layer for the zero-cost RPG Maker learning probe.

Uses runtime UI introspection only to decide what *real keyboard input* to send.
It does not mutate HP, inventory, switches, battle results, or map state directly.
"""
import json
import fangame_mv_learning_longrun_probe as agent

BATTLE_UI_JS = r'''() => {
  const s = window.SceneManager ? SceneManager._scene : null;
  if (!s) return [];
  const names = ['_partyCommandWindow','_actorCommandWindow','_skillWindow','_itemWindow','_enemyWindow','_actorWindow'];
  const out = [];
  for (const n of names) {
    const w = s[n];
    if (!w) continue;
    let list = [];
    try {
      list = Array.isArray(w._list) ? w._list.map((c,i)=>({
        index:i, name:c && c.name != null ? String(c.name) : null,
        symbol:c && c.symbol != null ? String(c.symbol) : null,
        enabled:c && c.enabled !== false
      })) : [];
    } catch(e) {}
    out.push({name:n, active:!!w.active, visible:!!w.visible, index:Number.isInteger(w.index && w.index()) ? w.index() : w._index, list:list});
  }
  try { out.push({name:'_battle', can_escape: BattleManager.canEscape ? !!BattleManager.canEscape() : null}); } catch(e) {}
  return out;
}'''


def ui(page):
    try:
        return page.evaluate(BATTLE_UI_JS)
    except Exception:
        return []


def choose_symbol(page, window, preferred):
    choices = window.get('list') or []
    by_symbol = {c.get('symbol'): c for c in choices if c.get('enabled', True)}
    target = next((by_symbol[s] for s in preferred if s in by_symbol), None)
    if not target:
        return None
    cur = window.get('index')
    if not isinstance(cur, int) or cur < 0:
        cur = 0
    n = len(choices)
    dst = int(target['index'])
    if n:
        down = (dst-cur) % n
        up = (cur-dst) % n
        key = 'ArrowDown' if down <= up else 'ArrowUp'
        steps = min(down, up)
        for _ in range(steps):
            agent.base.key_tap(page, key, hold=0.04)
    agent.base.key_tap(page, 'Enter', hold=0.08)
    return target.get('symbol') or target.get('name') or str(dst)


def smart_battle(page, state, strategy):
    party = state.get('party') or []
    living = [a for a in party if not a.get('dead')]
    ratios = [a.get('hp',0)/max(1,a.get('mhp',1)) for a in living]
    min_ratio = min(ratios) if ratios else 0.0
    avg_ratio = sum(ratios)/len(ratios) if ratios else 0.0
    dead_count = sum(1 for a in party if a.get('dead'))
    danger = dead_count > 0 or min_ratio < 0.35 or avg_ratio < 0.45 or strategy >= 2
    windows = ui(page)
    active = next((w for w in windows if w.get('active') and w.get('visible') and w.get('name') != '_battle'), None)
    can_escape = next((w.get('can_escape') for w in windows if w.get('name') == '_battle'), None)

    if active:
        name = active.get('name')
        if name == '_partyCommandWindow':
            wanted = ['escape','fight'] if danger and can_escape is not False else ['fight','escape']
            chosen = choose_symbol(page, active, wanted)
            if chosen:
                return f"battle_ui_{chosen}_danger{int(danger)}_minhp{min_ratio:.2f}"
        if name == '_actorCommandWindow':
            wanted = ['guard','item','skill','attack'] if danger else ['attack','skill','guard','item']
            chosen = choose_symbol(page, active, wanted)
            if chosen:
                return f"battle_ui_{chosen}_danger{int(danger)}_minhp{min_ratio:.2f}"
        if name in ('_enemyWindow','_actorWindow'):
            agent.base.key_tap(page,'Enter',hold=0.08)
            return f"battle_target_confirm_{name}"
        if name in ('_skillWindow','_itemWindow'):
            if danger:
                agent.base.key_tap(page,'Escape',hold=0.06)
                return f"battle_back_from_{name}"
            agent.base.key_tap(page,'Enter',hold=0.08)
            return f"battle_select_first_{name}"

    # Unknown/plugin-specific phase: preserve real-input fallback, but use the
    # learned strategy only after symbolic windows fail to expose a command.
    return agent.battle_original(page, state, strategy) if hasattr(agent,'battle_original') else agent.base.key_tap(page,'Enter') or 'battle_fallback_confirm'


# Keep the original as an explicit fallback and monkey-patch the global function
# that agent.main() resolves at runtime.
agent.battle_original = agent.battle
agent.battle = smart_battle

if __name__ == '__main__':
    raise SystemExit(agent.main())
