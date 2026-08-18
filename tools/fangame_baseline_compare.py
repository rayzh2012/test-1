#!/usr/bin/env python3
import argparse, json, math, statistics
from pathlib import Path


def q(xs, p):
    xs=sorted(float(x) for x in xs if x is not None)
    if not xs: return None
    if len(xs)==1: return xs[0]
    pos=(len(xs)-1)*p
    lo=math.floor(pos); hi=math.ceil(pos)
    if lo==hi: return xs[lo]
    return xs[lo] + (xs[hi]-xs[lo])*(pos-lo)


def get(d, path):
    cur=d
    for key in path.split('.'):
        if not isinstance(cur, dict): return None
        cur=cur.get(key)
    return cur

METRICS={
  'maps':'metrics.maps',
  'event_commands':'metrics.event_commands',
  'dialogue_chars':'metrics.dialogue_chars',
  'events_per_map':'derived.events_per_map',
  'event_commands_per_map':'derived.event_commands_per_map',
  'dialogue_chars_per_map':'derived.dialogue_chars_per_map',
  'choice_options_per_map':'derived.choice_options_per_map',
  'random_encounter_map_ratio':'progression.random_encounter_map_ratio',
  'encounter_step_median':'progression.encounter_step_median',
  'enemy_exp_median':'progression.enemy_exp_median',
  'equipment_price_median':'progression.equipment_price_median',
}

LOW_IS_INTERESTING={'random_encounter_map_ratio'}
HIGH_IS_LOW_PRESSURE={'encounter_step_median'}


def percentile(v, xs):
    if v is None or not xs: return None
    xs=sorted(float(x) for x in xs if x is not None)
    if not xs: return None
    return 100.0*sum(1 for x in xs if x <= float(v))/len(xs)


def band(p):
    if p is None: return 'UNKNOWN'
    if p >= 95: return 'EXTREME_HIGH'
    if p >= 80: return 'HIGH'
    if p >= 20: return 'NORMAL_RANGE'
    if p >= 5: return 'LOW'
    return 'EXTREME_LOW'


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--game',required=True,help='normalized genome/profile JSON')
    ap.add_argument('--baseline',required=True,help='JSON list of normalized ordinary-RPG profiles')
    ap.add_argument('--out',default='fangame_baseline_comparison.json')
    a=ap.parse_args()
    game=json.loads(Path(a.game).read_text(encoding='utf-8'))
    baseline=json.loads(Path(a.baseline).read_text(encoding='utf-8'))
    if isinstance(baseline,dict): baseline=baseline.get('games',[])
    rows=[]
    for name,path in METRICS.items():
        v=get(game,path)
        xs=[get(x,path) for x in baseline]
        xs=[x for x in xs if isinstance(x,(int,float))]
        if v is None or not xs: continue
        p=percentile(v,xs)
        med=q(xs,.5); p25=q(xs,.25); p75=q(xs,.75)
        ratio=(float(v)/med) if med not in (None,0) else None
        rows.append({
          'metric':name,'value':v,'baseline_n':len(xs),
          'baseline_p25':p25,'baseline_median':med,'baseline_p75':p75,
          'ratio_to_median':ratio,'percentile':p,'band':band(p)
        })
    by={r['metric']:r for r in rows}
    signals=[]
    def add(metric, cond, text):
        r=by.get(metric)
        if r and cond(r): signals.append(text.format(**r))
    add('event_commands_per_map',lambda r:r['percentile']>=80,'事件命令密度处于普通 RPG 的 P{percentile:.0f}：人工编排密度偏高。')
    add('dialogue_chars_per_map',lambda r:r['percentile']>=80,'对白密度处于普通 RPG 的 P{percentile:.0f}：叙事容量偏高。')
    add('random_encounter_map_ratio',lambda r:r['percentile']<=20,'随机遇敌地图覆盖仅处于普通 RPG 的 P{percentile:.0f}：随机战斗覆盖偏低。')
    add('encounter_step_median',lambda r:r['percentile']>=80,'遇敌步数中位数处于普通 RPG 的 P{percentile:.0f}：随机遇敌频率偏低。')
    out={
      'comparison_version':'ordinary-rpg-baseline.v0.1',
      'game':game.get('title') or game.get('name'),
      'baseline_population':len(baseline),
      'baseline_requirement':'Production labels are valid only when baseline rows come from real ordinary RPGs measured by the same parser/schema.',
      'metrics':rows,
      'signals':signals,
      'summary':' '.join(signals) if signals else '当前没有足够同口径基准指标形成异常标签。'
    }
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
