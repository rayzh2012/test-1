#!/usr/bin/env python3
import argparse, json, re
from collections import defaultdict

QUEST_RE = re.compile(r'(任务|委托|帮忙|帮助|寻找|收集|交给|奖励|报酬|悬赏|支线|拜托|请你|需要你|带回|取得)')
ENDING_RE = re.compile(r'(结局|终章|尾声|全剧终|感谢.*游玩|谢谢.*游玩|THE END|ENDING|完结|结束了|最终战|最终BOSS)', re.I)

def infer(map_graph, dialogue, normalized):
    rows=dialogue.get('rows',[])
    by_event=defaultdict(lambda:{'texts':[],'quest_hits':0,'ending_hits':0})
    for r in rows:
        if r.get('scope')!='map': continue
        key=(r.get('map_id'),r.get('event_id')); text=r.get('text') or ''
        by_event[key]['texts'].append(text)
        by_event[key]['quest_hits']+=len(QUEST_RE.findall(text)); by_event[key]['ending_hits']+=len(ENDING_RE.findall(text))
    state=defaultdict(lambda:{'switch_writes':set(),'switch_reads':set(),'variable_writes':set(),'variable_reads':set()})
    for bucket,name in [('switch_writes','switch_writes'),('switch_reads','switch_reads'),('variable_writes','variable_writes'),('variable_reads','variable_reads')]:
        for sid,arr in map_graph.get(bucket,{}).items():
            for x in arr: state[(x.get('map_id'),x.get('event_id'))][name].add(int(sid))
    leaf=set(normalized.get('leaf_maps',[])); isolated=set(normalized.get('isolated_maps',[])); qc=[]; ec=[]
    for key,ent in by_event.items():
        st=state.get(key,{}); ops=sum(len(st.get(k,set())) for k in ('switch_writes','switch_reads','variable_writes','variable_reads'))
        qscore=ent['quest_hits']*2+min(ops,4)
        if ent['quest_hits'] and qscore>=3:
            qc.append({'map_id':key[0],'event_id':key[1],'score':qscore,'quest_keyword_hits':ent['quest_hits'],'state_signal_count':ops,'sample_texts':ent['texts'][:3],'confidence':'HIGH' if qscore>=6 else 'MEDIUM'})
        escore=ent['ending_hits']*3+(1 if key[0] in leaf else 0)+(1 if key[0] in isolated else 0)+(1 if ops else 0)
        if ent['ending_hits'] and escore>=4:
            ec.append({'map_id':key[0],'event_id':key[1],'score':escore,'ending_keyword_hits':ent['ending_hits'],'leaf_map':key[0] in leaf,'isolated_map':key[0] in isolated,'state_signal_count':ops,'sample_texts':ent['texts'][:3],'confidence':'HIGH' if escore>=7 else 'MEDIUM'})
    qc.sort(key=lambda x:(-x['score'],x['map_id'],x['event_id'])); ec.sort(key=lambda x:(-x['score'],x['map_id'],x['event_id']))
    return {'schema':'fangame-quest-ending-candidates-v1','summary':{'quest_candidate_events':len(qc),'ending_candidate_events':len(ec),'warning':'Heuristic candidates, not official quest/ending counts.'},'quest_candidates':qc,'ending_candidates':ec}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('map_graph'); ap.add_argument('dialogue'); ap.add_argument('normalized'); ap.add_argument('--out',default='quest_ending_candidates.json'); a=ap.parse_args()
    out=infer(json.load(open(a.map_graph,encoding='utf-8')),json.load(open(a.dialogue,encoding='utf-8')),json.load(open(a.normalized,encoding='utf-8')))
    json.dump(out,open(a.out,'w',encoding='utf-8'),ensure_ascii=False,indent=2); print(json.dumps(out['summary'],ensure_ascii=False,indent=2))
if __name__=='__main__': main()
