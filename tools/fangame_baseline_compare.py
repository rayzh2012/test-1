#!/usr/bin/env python3
import argparse, json, math
from pathlib import Path

COMPARISON_VERSION='ordinary-rpg-baseline.v0.2'
DEFAULT_MIN_PRODUCTION_N=20


def q(xs,p):
    xs=sorted(float(x) for x in xs if isinstance(x,(int,float)))
    if not xs:return None
    if len(xs)==1:return xs[0]
    pos=(len(xs)-1)*p; lo=math.floor(pos); hi=math.ceil(pos)
    if lo==hi:return xs[lo]
    return xs[lo]+(xs[hi]-xs[lo])*(pos-lo)


def get(d,path):
    cur=d
    for key in path.split('.'):
        if not isinstance(cur,dict):return None
        cur=cur.get(key)
    return cur


def db_objects(p):
    m=p.get('metrics') or {}
    vals=[m.get(k) for k in ('actors','classes','skills','items','weapons','armors','enemies','troops','states','common_events')]
    nums=[float(v) for v in vals if isinstance(v,(int,float))]
    return sum(nums) if nums else None


def asset_count(p):
    m=p.get('metrics') or {}; vals=[m.get('image_count'),m.get('audio_count')]
    nums=[float(v) for v in vals if isinstance(v,(int,float))]
    return sum(nums) if nums else None

METRICS={
  'maps':lambda p:get(p,'metrics.maps'),
  'event_commands':lambda p:get(p,'metrics.event_commands'),
  'dialogue_chars':lambda p:get(p,'metrics.dialogue_chars'),
  'database_object_count':db_objects,
  'asset_count':asset_count,
  'enabled_plugins':lambda p:get(p,'metrics.enabled_plugins'),
  'events_per_map':lambda p:get(p,'derived.events_per_map'),
  'event_commands_per_map':lambda p:get(p,'derived.event_commands_per_map'),
  'dialogue_chars_per_map':lambda p:get(p,'derived.dialogue_chars_per_map'),
  'choice_options_per_map':lambda p:get(p,'derived.choice_options_per_map'),
  'conditional_branches_per_map':lambda p:get(p,'derived.conditional_branches_per_map'),
  'transfers_per_map':lambda p:get(p,'derived.transfers_per_map'),
  'battle_calls_per_map':lambda p:get(p,'derived.battle_calls_per_map'),
  'random_encounter_map_ratio':lambda p:get(p,'progression.random_encounter_map_ratio'),
  'encounter_step_median':lambda p:get(p,'progression.encounter_step_median'),
  'enemy_exp_median':lambda p:get(p,'progression.enemy_exp_median'),
  'equipment_price_median':lambda p:get(p,'progression.equipment_price_median'),
}


def percentile(v,xs):
    if v is None:return None
    xs=sorted(float(x) for x in xs if isinstance(x,(int,float)))
    if not xs:return None
    return 100.0*sum(1 for x in xs if x<=float(v))/len(xs)


def band(p):
    if p is None:return 'UNKNOWN'
    if p>=95:return 'EXTREME_HIGH'
    if p>=80:return 'HIGH'
    if p>=20:return 'NORMAL_RANGE'
    if p>=5:return 'LOW'
    return 'EXTREME_LOW'


def load_corpus(path):
    obj=json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(obj,list):
        return {'schema':'legacy-list','games':obj,'corpus_id':None,'corpus_version':None,'provenance_status':'LEGACY_UNVERSIONED'}
    if not isinstance(obj,dict):raise SystemExit('baseline must be a JSON list or corpus object')
    return {
      'schema':obj.get('schema'),'games':obj.get('games',[]) or [],'corpus_id':obj.get('corpus_id'),
      'corpus_version':obj.get('corpus_version'),'provenance_status':obj.get('provenance_status','UNKNOWN')
    }


def compatible(game,row):
    return row.get('schema')==game.get('schema') and row.get('parser_family')==game.get('parser_family')


def engine_exact(game,row):
    return compatible(game,row) and row.get('engine')==game.get('engine')


def compare_stratum(game,rows,name,min_n):
    metrics=[]
    for metric,fn in METRICS.items():
        v=fn(game); xs=[fn(x) for x in rows]; xs=[x for x in xs if isinstance(x,(int,float))]
        if not isinstance(v,(int,float)) or not xs:continue
        p=percentile(v,xs); n=len(xs); production=n>=min_n
        med=q(xs,.5); p25=q(xs,.25); p75=q(xs,.75)
        metrics.append({
          'metric':metric,'value':v,'baseline_n':n,'baseline_p25':p25,'baseline_median':med,'baseline_p75':p75,
          'ratio_to_median':(float(v)/med) if med not in (None,0) else None,
          'percentile':p,'band':band(p),'percentile_status':'PRODUCTION_ELIGIBLE' if production else 'EXPLORATORY_ONLY_INSUFFICIENT_N'
        })
    return {'stratum':name,'row_count':len(rows),'min_production_n':min_n,'metrics':metrics}


def production_signals(stratum):
    by={r['metric']:r for r in stratum['metrics'] if r['percentile_status']=='PRODUCTION_ELIGIBLE'}
    signals=[]
    def add(metric,cond,text):
        r=by.get(metric)
        if r and cond(r):signals.append(text.format(**r))
    add('event_commands_per_map',lambda r:r['percentile']>=80,'事件命令密度 P{percentile:.0f}：人工编排密度偏高。')
    add('dialogue_chars_per_map',lambda r:r['percentile']>=80,'对白密度 P{percentile:.0f}：叙事容量偏高。')
    add('database_object_count',lambda r:r['percentile']>=80,'数据库对象总量 P{percentile:.0f}：系统/内容广度偏高。')
    add('enabled_plugins',lambda r:r['percentile']>=80,'启用插件数 P{percentile:.0f}：插件系统表面偏广。')
    add('conditional_branches_per_map',lambda r:r['percentile']>=80,'条件分支密度 P{percentile:.0f}：事件逻辑分支偏密。')
    add('random_encounter_map_ratio',lambda r:r['percentile']<=20,'随机遇敌地图覆盖 P{percentile:.0f}：随机战斗覆盖偏低。')
    add('encounter_step_median',lambda r:r['percentile']>=80,'遇敌步数中位数 P{percentile:.0f}：随机遇敌频率偏低。')
    return signals


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--game',required=True,help='normalized genome/profile JSON')
    ap.add_argument('--baseline',required=True,help='versioned ordinary-RPG corpus JSON')
    ap.add_argument('--min-production-n',type=int,default=DEFAULT_MIN_PRODUCTION_N)
    ap.add_argument('--out',default='fangame_baseline_comparison.json')
    a=ap.parse_args()
    game=json.loads(Path(a.game).read_text(encoding='utf-8'))
    corpus=load_corpus(a.baseline); all_rows=[x for x in corpus['games'] if isinstance(x,dict)]
    compat=[x for x in all_rows if compatible(game,x)]
    exact=[x for x in compat if engine_exact(game,x)]
    rejected=len(all_rows)-len(compat)

    strata=[compare_stratum(game,compat,'same_schema_and_parser_family',a.min_production_n)]
    if exact and len(exact)!=len(compat):
        strata.append(compare_stratum(game,exact,'same_engine_exact',a.min_production_n))
    primary=max(strata,key=lambda s:s['row_count']) if strata else None
    signals=production_signals(primary) if primary else []
    production_metrics=sum(1 for r in (primary or {}).get('metrics',[]) if r['percentile_status']=='PRODUCTION_ELIGIBLE')

    out={
      'comparison_version':COMPARISON_VERSION,
      'game':{'title':game.get('title'),'game_id':game.get('game_id'),'schema':game.get('schema'),'parser_family':game.get('parser_family'),'engine':game.get('engine')},
      'corpus':{'schema':corpus['schema'],'corpus_id':corpus['corpus_id'],'corpus_version':corpus['corpus_version'],'provenance_status':corpus['provenance_status'],'total_rows':len(all_rows)},
      'compatibility':{
        'rule':'Exact normalized schema AND parser_family are required. Engine-exact is reported as an optional narrower stratum.',
        'compatible_rows':len(compat),'rejected_incompatible_rows':rejected,
        'min_production_n_per_metric':a.min_production_n,
      },
      'strata':strata,
      'production_label_status':'ENABLED_FOR_SOME_METRICS' if production_metrics else 'DISABLED_INSUFFICIENT_COMPATIBLE_N',
      'signals':signals,
      'summary':' '.join(signals) if signals else '仅输出探索性统计；当前没有达到 production percentile 门槛的同口径普通 RPG 样本。'
    }
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
