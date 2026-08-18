#!/usr/bin/env python3
import argparse, json, re
from collections import defaultdict

QUEST_RE = re.compile(r'(任务|委托|帮忙|帮助|寻找|收集|交给|奖励|报酬|悬赏|支线|拜托|请你|需要你|带回|取得)')
ENDING_RE = re.compile(r'(结局|终章|尾声|全剧终|感谢.*游玩|谢谢.*游玩|THE END|ENDING|完结|结束了|最终战|最终BOSS)', re.I)


def infer(map_graph, dialogue, normalized):
    rows = dialogue.get('rows', [])
    by_event = defaultdict(lambda: {'texts': [], 'maps': set(), 'conditions': [], 'quest_hits': 0, 'ending_hits': 0})
    for r in rows:
        if r.get('scope') != 'map':
            continue
        key = (r.get('map_id'), r.get('event_id'))
        text = r.get('text') or ''
        ent = by_event[key]
        ent['texts'].append(text)
        ent['maps'].add(r.get('map_id'))
        ent['conditions'].append(r.get('conditions') or {})
        ent['quest_hits'] += len(QUEST_RE.findall(text))
        ent['ending_hits'] += len(ENDING_RE.findall(text))

    swr = map_graph.get('switch_writes', {})
    srr = map_graph.get('switch_reads', {})
    vwr = map_graph.get('variable_writes', {})
    vrr = map_graph.get('variable_reads', {})
    state_by_event = defaultdict(lambda: {'switch_writes': set(), 'switch_reads': set(), 'variable_writes': set(), 'variable_reads': set()})
    for sid, arr in swr.items():
        for x in arr: state_by_event[(x.get('map_id'),x.get('event_id'))]['switch_writes'].add(int(sid))
    for sid, arr in srr.items():
        for x in arr: state_by_event[(x.get('map_id'),x.get('event_id'))]['switch_reads'].add(int(sid))
    for vid, arr in vwr.items():
        for x in arr: state_by_event[(x.get('map_id'),x.get('event_id'))]['variable_writes'].add(int(vid))
    for vid, arr in vrr.items():
        for x in arr: state_by_event[(x.get('map_id'),x.get('event_id'))]['variable_reads'].add(int(vid))

    quest_candidates=[]
    ending_candidates=[]
    leaf=set(normalized.get('leaf_maps',[])); isolated=set(normalized.get('isolated_maps',[]))
    for key, ent in by_event.items():
        st=state_by_event.get(key, {})
        state_ops=sum(len(st.get(k,set())) for k in ('switch_writes','switch_reads','variable_writes','variable_reads'))
        qscore=ent['quest_hits']*2 + min(state_ops,4)
        if ent['quest_hits'] and qscore >= 3:
            quest_candidates.append({
                'map_id':key[0],'event_id':key[1],'score':qscore,
                'quest_keyword_hits':ent['quest_hits'],'state_signal_count':state_ops,
                'switch_writes':sorted(st.get('switch_writes',set())),
                'switch_reads':sorted(st.get('switch_reads',set())),
                'sample_texts':ent['texts'][:3],
                'confidence':'MEDIUM' if qscore < 6 else 'HIGH'
            })
        escore=ent['ending_hits']*3
        if key[0] in leaf: escore += 1
        if key[0] in isolated: escore += 1
        if state_ops: escore += 1
        if ent['ending_hits'] and escore >= 4:
            ending_candidates.append({
                'map_id':key[0],'event_id':key[1],'score':escore,
                'ending_keyword_hits':ent['ending_hits'],'leaf_map':key[0] in leaf,'isolated_map':key[0] in isolated,
                'state_signal_count':state_ops,'sample_texts':ent['texts'][:3],
                'confidence':'MEDIUM' if escore < 7 else 'HIGH'
            })
    quest_candidates.sort(key=lambda x:(-x['score'],x['map_id'],x['event_id']))
    ending_candidates.sort(key=lambda x:(-x['score'],x['map_id'],x['event_id']))
    return {
        'schema':'fangame-quest-ending-candidates-v1',
        'summary':{
            'quest_candidate_events':len(quest_candidates),
            'ending_candidate_events':len(ending_candidates),
            'warning':'Candidates are heuristic evidence clusters, not official sidequest or ending counts. Dialogue/state/topology can produce false positives.'
        },
        'quest_candidates':quest_candidates,
        'ending_candidates':ending_candidates
    }


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('map_graph'); ap.add_argument('dialogue'); ap.add_argument('normalized'); ap.add_argument('--out',default='quest_ending_candidates.json'); a=ap.parse_args()
    mg=json.load(open(a.map_graph,encoding='utf-8')); d=json.load(open(a.dialogue,encoding='utf-8')); n=json.load(open(a.normalized,encoding='utf-8'))
    out=infer(mg,d,n)
    json.dump(out,open(a.out,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps(out['summary'],ensure_ascii=False,indent=2))

if __name__=='__main__': main()
