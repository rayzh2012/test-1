#!/usr/bin/env python3
"""Runtime-only play-log layer for Final Redemption survival learning.

This wrapper does NOT read map/event code to narrate the game. It augments snapshots with
what the running game is actually displaying, then post-processes the real action trace into
human-readable route / battle / death / recovery / story-observation logs.
"""
import json
import sys
from pathlib import Path

import fangame_mv_survival_learning_probe_v2  # installs survival-v2 battle policy
import fangame_mv_learning_longrun_probe as agent

_RUNTIME_OBS_JS = r'''() => {
  const out={message_text:[], choices:[], speaker:null, troop:[]};
  try {
    if (window.$gameMessage) {
      out.message_text=Array.isArray($gameMessage._texts) ? $gameMessage._texts.map(String) : [];
      out.choices=Array.isArray($gameMessage._choices) ? $gameMessage._choices.map(String) : [];
      out.speaker=$gameMessage._speakerName || null;
    }
  } catch(e) {}
  try {
    if (window.$gameTroop && $gameTroop.members) {
      out.troop=$gameTroop.members().map((e,i)=>({index:i,name:e&&e.name?e.name():null,hp:e?e.hp:null,mhp:e?e.mhp:null,dead:e&&e.isDead?e.isDead():null}));
    }
  } catch(e) {}
  return out;
}'''

_orig_snap = agent.base.snap_state

def snap_with_runtime_observation(page):
    s = _orig_snap(page)
    try:
        obs = page.evaluate(_RUNTIME_OBS_JS)
    except Exception:
        obs = {}
    s['runtime_observation'] = obs
    return s

agent.base.snap_state = snap_with_runtime_observation

DIR_NAME={2:'下',4:'左',6:'右',8:'上'}

def pos_of(rec):
    st=rec.get('state') or {}; p=st.get('player') or {}
    if st.get('map_id') is None or p.get('x') is None or p.get('y') is None:return None
    return (st.get('map_id'),p.get('x'),p.get('y'))

def compact_playlog(trace_path,outdir):
    if not trace_path.exists(): return
    rows=[]
    with trace_path.open(encoding='utf-8') as f:
        for line in f:
            try: rows.append(json.loads(line))
            except Exception: pass
    facts=[]; move_seg=None; last_msg=None; battle_no=0; in_battle=False
    def flush_move():
        nonlocal move_seg
        if move_seg:
            facts.append(move_seg); move_seg=None
    for i,r in enumerate(rows):
        t=r.get('t'); st=r.get('state') or {}; act=str(r.get('action') or ''); pos=pos_of(r)
        obs=st.get('runtime_observation') or {}
        msg='\n'.join(x for x in (obs.get('message_text') or []) if x).strip()
        if msg and msg!=last_msg:
            flush_move(); facts.append({'t':t,'type':'story_text','map_id':st.get('map_id'),'xy':list(pos[1:]) if pos else None,'speaker':obs.get('speaker'),'text':msg,'choices':obs.get('choices') or []}); last_msg=msg
        elif not msg: last_msg=None
        cur_battle=bool(r.get('in_battle')) or st.get('scene')=='Scene_Battle'
        if cur_battle and not in_battle:
            flush_move(); battle_no+=1
            troop=[x.get('name') for x in (obs.get('troop') or []) if x.get('name')]
            facts.append({'t':t,'type':'battle_start','battle_no':battle_no,'map_id':st.get('map_id'),'xy':list(pos[1:]) if pos else None,'enemies':troop,'party':st.get('party') or []})
        if in_battle and not cur_battle:
            flush_move(); facts.append({'t':t,'type':'battle_end','battle_no':battle_no,'party':st.get('party') or []})
        in_battle=cur_battle
        if act.startswith('battle_'):
            flush_move(); facts.append({'t':t,'type':'battle_action','battle_no':battle_no,'action':act,'party':st.get('party') or [],'enemies':obs.get('troop') or st.get('enemies') or []})
            continue
        if act=='death_learn_recover':
            flush_move(); facts.append({'t':t,'type':'death_recovery','recovery':r.get('recovery'),'learning':r.get('learning')}); continue
        edge=r.get('edge')
        if edge and len(edge)>=4 and (act.startswith('route_') or act.startswith('frontier_') or act=='probe'):
            d=edge[3]; key=(st.get('map_id'),d)
            if move_seg and move_seg.get('_key')==key:
                move_seg['steps']+=1; move_seg['to_xy']=list(pos[1:]) if pos else move_seg.get('to_xy'); move_seg['t_end']=t
            else:
                flush_move(); move_seg={'t':t,'t_end':t,'type':'movement','map_id':st.get('map_id'),'direction':DIR_NAME.get(d,str(d)),'steps':1,'from_xy':list(pos[1:]) if pos else None,'to_xy':list(pos[1:]) if pos else None,'reason':act,'_key':key}
            continue
        if act.startswith('interact_event_') or act.startswith('bump_event_'):
            flush_move(); facts.append({'t':t,'type':'event_interaction','map_id':st.get('map_id'),'xy':list(pos[1:]) if pos else None,'action':act})
    flush_move()
    for x in facts: x.pop('_key',None)
    (outdir/'mv_human_play_log.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in facts),encoding='utf-8')
    lines=['# Final Redemption 实际游玩日志','', '> 本日志只记录运行时真实观察：真实按键、坐标移动、屏幕剧情文本、战斗、死亡与读档恢复。不会把静态读取的事件代码冒充为已游玩剧情。','']
    for x in facts:
        typ=x.get('type'); t=x.get('t')
        if typ=='movement': lines.append(f"- t={t}s｜地图{x.get('map_id')}｜向{x.get('direction')}走 {x.get('steps')} 步｜{x.get('from_xy')} → {x.get('to_xy')}｜{x.get('reason')}")
        elif typ=='story_text': lines.append(f"- t={t}s｜剧情｜地图{x.get('map_id')} {x.get('xy')}｜{x.get('speaker') or ''}{': ' if x.get('speaker') else ''}{x.get('text')}" + (f"｜选项={x.get('choices')}" if x.get('choices') else ''))
        elif typ=='battle_start': lines.append(f"- t={t}s｜战斗#{x.get('battle_no')}开始｜敌人={x.get('enemies')}｜位置=地图{x.get('map_id')} {x.get('xy')}")
        elif typ=='battle_action': lines.append(f"- t={t}s｜战斗#{x.get('battle_no')}动作｜{x.get('action')}｜我方={[(a.get('name'),a.get('hp'),a.get('mhp')) for a in x.get('party') or []]}")
        elif typ=='battle_end': lines.append(f"- t={t}s｜战斗#{x.get('battle_no')}结束｜我方={[(a.get('name'),a.get('hp'),a.get('mhp')) for a in x.get('party') or []]}")
        elif typ=='death_recovery': lines.append(f"- t={t}s｜死亡/恢复｜{x.get('recovery')}｜学习={x.get('learning')}")
        elif typ=='event_interaction': lines.append(f"- t={t}s｜事件触发尝试｜地图{x.get('map_id')} {x.get('xy')}｜{x.get('action')}")
    (outdir/'mv_human_play_log.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':
    outdir=None
    if '--outdir' in sys.argv:
        try: outdir=Path(sys.argv[sys.argv.index('--outdir')+1]).resolve()
        except Exception: outdir=None
    rc=agent.main()
    if outdir:
        compact_playlog(outdir/'mv_learning_trace.jsonl',outdir)
    raise SystemExit(rc)
