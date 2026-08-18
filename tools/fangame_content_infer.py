#!/usr/bin/env python3
import argparse, json, re
from collections import Counter, defaultdict
from pathlib import Path

SIDEQUEST_PATTERNS=[
 ('quest_term',re.compile(r'任务|委托|支线|请求|拜托')),
 ('help_term',re.compile(r'帮我|帮助|麻烦你|能不能.*帮|请你')),
 ('search_term',re.compile(r'寻找|找到|收集|带来|交给|送给|取回')),
 ('reward_term',re.compile(r'奖励|报酬|酬谢|谢礼|获得|领取')),
 ('completion_term',re.compile(r'完成|做到了|谢谢你|辛苦了|干得好')),
]
ENDING_PATTERNS=[
 ('ending_term',re.compile(r'结局|终章|大结局|完结|剧终|THE\s*END|ENDING',re.I)),
 ('credits_term',re.compile(r'制作人员|制作名单|STAFF|CREDITS?',re.I)),
 ('farewell_term',re.compile(r'再见了|永别|故事.*结束|旅程.*结束|一切.*结束')),
]

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def map_state_usage(graph):
    out=defaultdict(lambda:{'switch_read':set(),'switch_write':set(),'var_read':set(),'var_write':set()})
    for field,key in [('switch_reads','switch_read'),('switch_writes','switch_write'),('variable_reads','var_read'),('variable_writes','var_write')]:
        for sid, refs in (graph.get(field) or {}).items():
            for r in refs:
                mid=r.get('map_id')
                if mid is not None: out[int(mid)][key].add(str(sid))
    return out

def dialogue_by_map(dialogue):
    by=defaultdict(list)
    for r in dialogue.get('rows',[]):
        if r.get('kind')!='dialogue' or r.get('scope')!='map': continue
        mid=r.get('map_id')
        if mid is not None and r.get('text'): by[int(mid)].append(r)
    return by

def term_hits(text, pats):
    hits=[]
    for label,rx in pats:
        if rx.search(text): hits.append(label)
    return hits

def sidequest_candidates(dialogue, graph, norm):
    by=dialogue_by_map(dialogue); usage=map_state_usage(graph)
    leaves=set(norm.get('leaf_maps',[])); branching=set(norm.get('branching_maps',[]))
    candidates=[]
    for mid, rows in by.items():
        text='\n'.join(r.get('text','') for r in rows)
        hits=term_hits(text,SIDEQUEST_PATTERNS)
        u=usage.get(mid,{}); local_state=len(u.get('switch_read',()))+len(u.get('switch_write',()))+len(u.get('var_read',()))+len(u.get('var_write',()))
        score=0; evidence=[]
        unique_hits=len(set(hits))
        if unique_hits>=1: score+=2; evidence.append(f'sidequest_language:{sorted(set(hits))}')
        if unique_hits>=3: score+=2
        if local_state>=1: score+=1; evidence.append(f'state_refs:{local_state}')
        if mid in leaves: score+=1; evidence.append('normalized_leaf_map')
        if mid in branching: score+=1; evidence.append('normalized_branching_map')
        # Require semantics plus at least one additional structural/state signal, or very strong semantics.
        if (unique_hits>=1 and score>=3) or unique_hits>=3:
            conf='HIGH' if score>=6 else ('MEDIUM' if score>=4 else 'LOW')
            samples=[]
            for r in rows:
                if term_hits(r.get('text',''),SIDEQUEST_PATTERNS):
                    samples.append({'event_id':r.get('event_id'),'page_id':r.get('page_id'),'text':r.get('text','')[:220]})
                    if len(samples)>=3: break
            candidates.append({'map_id':mid,'score':score,'confidence':conf,'evidence':evidence,'samples':samples})
    candidates.sort(key=lambda x:(-x['score'],x['map_id']))
    return candidates

def ending_candidates(dialogue, graph, norm):
    by=dialogue_by_map(dialogue)
    terminal=set(norm.get('leaf_maps',[])) | set(norm.get('isolated_maps',[]))
    candidates=[]
    for mid,rows in by.items():
        text='\n'.join(r.get('text','') for r in rows)
        hits=sorted(set(term_hits(text,ENDING_PATTERNS)))
        if not hits: continue
        score=2*len(hits); evidence=[f'ending_language:{hits}']
        if mid in terminal: score+=2; evidence.append('terminal_like_topology')
        conf='HIGH' if score>=6 else ('MEDIUM' if score>=4 else 'LOW')
        samples=[]
        for r in rows:
            if term_hits(r.get('text',''),ENDING_PATTERNS):
                samples.append({'event_id':r.get('event_id'),'page_id':r.get('page_id'),'text':r.get('text','')[:260]})
                if len(samples)>=4: break
        candidates.append({'map_id':mid,'score':score,'confidence':conf,'evidence':evidence,'samples':samples})
    candidates.sort(key=lambda x:(-x['score'],x['map_id']))
    return candidates

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('dialogue_json'); ap.add_argument('map_graph_json'); ap.add_argument('normalized_graph_json'); ap.add_argument('--out',required=True)
    a=ap.parse_args(); d=load(a.dialogue_json); g=load(a.map_graph_json); n=load(a.normalized_graph_json)
    sq=sidequest_candidates(d,g,n); en=ending_candidates(d,g,n)
    summary={
      'sidequest_candidate_maps':len(sq),
      'sidequest_high_confidence_maps':sum(x['confidence']=='HIGH' for x in sq),
      'sidequest_medium_confidence_maps':sum(x['confidence']=='MEDIUM' for x in sq),
      'ending_candidate_maps':len(en),
      'ending_high_confidence_maps':sum(x['confidence']=='HIGH' for x in en),
      'ending_medium_confidence_maps':sum(x['confidence']=='MEDIUM' for x in en),
      'interpretation':'Candidates are inference, not official quest/ending counts. v1 combines semantic text signals with state/topology evidence and intentionally underclaims.'
    }
    out={'schema':'fangame-content-inference-v1','summary':summary,'sidequest_candidates':sq,'ending_candidates':en}
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
