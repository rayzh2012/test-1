#!/usr/bin/env python3
import argparse, json, re
from collections import defaultdict
from pathlib import Path

SIDEQUEST_PATTERNS=[
 ('quest_term',re.compile(r'任务|委托|支线|请求|拜托')),
 ('help_term',re.compile(r'帮我|帮助|麻烦你|能不能.*帮|请你')),
 ('search_term',re.compile(r'寻找|找到|收集|带来|交给|送给|取回')),
 ('reward_term',re.compile(r'奖励|报酬|酬谢|谢礼|获得|领取')),
 ('completion_term',re.compile(r'完成|做到了|谢谢你|辛苦了|干得好')),
]
ACTIONABLE_SIDEQUEST={'quest_term','help_term','search_term','completion_term'}
ENDING_PATTERNS=[
 ('ending_term',re.compile(r'结局|終章|终章|大结局|完结|剧终|THE\s*END|ENDING',re.I)),
 ('credits_term',re.compile(r'制作人员|制作名单|STAFF|CREDITS?',re.I)),
 ('farewell_term',re.compile(r'再见了|永别|故事.*结束|旅程.*结束|一切.*结束')),
]
EXPLICIT_TASK_RE=re.compile(r'接受任务|接受任務|任务完成|任務完成|支线任务|支線任務|完成任务|完成任務')
MAINLINE_RE=re.compile(r'救出?国王|救出?國王|救国王|救國王|魔王|拯救.{0,8}(?:大陆|大陸|世界|王国|王國)|铲除邪恶|剷除邪惡|救世界|救国|救國')
OPTIONAL_CONTENT_RE=re.compile(r'神兽|神獸|宠物蛋|寵物蛋|神器|凤凰的羽毛|鳳凰的羽毛|隐藏|隱藏|神兽开关|神獸開關|宠物|寵物')
CONTENT_ENDPOINT_RE=re.compile(r'(?:还没有结束|還沒有結束|尚未结束|尚未結束|未完待续|未完待續).{0,80}(?:继续更新|繼續更新|后续|後續)|(?:游戏|遊戲).{0,30}(?:还没有结束|還沒有結束)',re.I|re.S)

def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def map_state_usage(graph):
    out=defaultdict(lambda:{'switch_read':set(),'switch_write':set(),'var_read':set(),'var_write':set()})
    for field,key in [('switch_reads','switch_read'),('switch_writes','switch_write'),('variable_reads','var_read'),('variable_writes','var_write')]:
        for sid,refs in (graph.get(field) or {}).items():
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

def dialogue_by_event(dialogue):
    by=defaultdict(list)
    for r in dialogue.get('rows',[]):
        if r.get('kind')!='dialogue' or r.get('scope')!='map': continue
        mid,eid=r.get('map_id'),r.get('event_id')
        if mid is not None and eid is not None and r.get('text'): by[(int(mid),int(eid))].append(r)
    return by

def normalized_text(s): return re.sub(r'\s+','',s or '')

def repeated_texts(by,min_maps=3):
    owners=defaultdict(set)
    for mid,rows in by.items():
        for r in rows:
            t=normalized_text(r.get('text',''))
            if len(t)>=12: owners[t].add(mid)
    return {t for t,maps in owners.items() if len(maps)>=min_maps}

def term_hits(text,pats): return [label for label,rx in pats if rx.search(text)]

def informative_rows(rows,boilerplate): return [r for r in rows if normalized_text(r.get('text','')) not in boilerplate]

def candidate_event_ids(rows):
    out=set()
    for r in rows:
        if set(term_hits(r.get('text',''),SIDEQUEST_PATTERNS)) & ACTIONABLE_SIDEQUEST and r.get('event_id') is not None:
            out.add(int(r['event_id']))
    return sorted(out)

def event_condition_switches(rows):
    out=set()
    for r in rows:
        c=r.get('conditions') or {}
        for k in ('switch1_id','switch2_id'):
            v=c.get(k)
            if v not in (None,0,'0',''): out.add(str(v))
    return sorted(out,key=lambda x:int(x) if x.isdigit() else x)

def external_writers(graph,mid,eid,switch_ids):
    found={}; writes=graph.get('switch_writes') or {}
    for sid in switch_ids:
        ext=[]
        for w in writes.get(str(sid),[]):
            if (w.get('map_id'),w.get('event_id')) != (mid,eid):
                ext.append({k:w.get(k) for k in ('map_id','event_id','page_id','command_index','value') if w.get(k) is not None})
        if ext: found[str(sid)]=ext
    return found

def explicit_sidequest_events(dialogue,graph):
    out=[]
    for (mid,eid),rows in dialogue_by_event(dialogue).items():
        text='\n'.join(r.get('text','') for r in rows)
        hits=set(term_hits(text,SIDEQUEST_PATTERNS))
        ext=external_writers(graph,mid,eid,event_condition_switches(rows))
        if not EXPLICIT_TASK_RE.search(text): continue
        if 'completion_term' not in hits or 'reward_term' not in hits or not ext: continue
        out.append({
          'map_id':mid,'event_id':eid,'classification':'SIDEQUEST_EXPLICIT','confidence':'HIGH',
          'completion_switches':ext,
          'evidence':['explicit_task_wording','completion_language','reward_language','external_completion_switch'],
          'samples':[r.get('text','')[:260] for r in rows if EXPLICIT_TASK_RE.search(r.get('text','')) or 'reward_term' in term_hits(r.get('text',''),SIDEQUEST_PATTERNS)][:4]
        })
    return sorted(out,key=lambda x:(x['map_id'],x['event_id']))

def classify_candidate(candidate,rows_by_event,explicit_index):
    mid=int(candidate['map_id']); eids=candidate.get('candidate_event_ids') or []
    text='\n'.join(r.get('text','') for eid in eids for r in rows_by_event.get((mid,eid),[]))
    explicit=[x for (m,e),x in explicit_index.items() if m==mid and (not eids or e in eids)]
    if explicit: return 'SIDEQUEST_EXPLICIT',['explicit_task_state_reward_closure']
    if MAINLINE_RE.search(text): return 'MAINLINE_GATE',['mainline_rescue_or_world_progression_language']
    if OPTIONAL_CONTENT_RE.search(text): return 'OPTIONAL_CONTENT',['collectible_or_hidden_content_language']
    return 'QUEST_CANDIDATE_UNRESOLVED',['insufficient_semantic_separation']

def sidequest_candidates(dialogue,graph,norm):
    by=dialogue_by_map(dialogue); byev=dialogue_by_event(dialogue); usage=map_state_usage(graph); boilerplate=repeated_texts(by)
    leaves=set(norm.get('leaf_maps',[])); branching=set(norm.get('branching_maps',[]))
    explicit=explicit_sidequest_events(dialogue,graph); explicit_idx={(x['map_id'],x['event_id']):x for x in explicit}
    candidates=[]
    for mid,raw_rows in by.items():
        rows=informative_rows(raw_rows,boilerplate)
        text='\n'.join(r.get('text','') for r in rows)
        hits=set(term_hits(text,SIDEQUEST_PATTERNS)); actionable=hits&ACTIONABLE_SIDEQUEST
        if not actionable: continue
        u=usage.get(mid,{}); local_state=len(u.get('switch_read',()))+len(u.get('switch_write',()))+len(u.get('var_read',()))+len(u.get('var_write',()))
        score=2*len(actionable); evidence=[f'action_language:{sorted(actionable)}']
        if 'reward_term' in hits: score+=1; evidence.append('reward_language')
        if local_state>=1: score+=1; evidence.append(f'state_refs:{local_state}')
        if mid in leaves: score+=1; evidence.append('normalized_leaf_map')
        if mid in branching: evidence.append('normalized_branching_map_context_only')
        corroborated=(local_state>=1 or mid in leaves)
        if not corroborated and len(actionable)<2: continue
        conf='HIGH' if score>=7 else ('MEDIUM' if score>=5 else 'LOW')
        samples=[]
        for r in rows:
            rh=set(term_hits(r.get('text',''),SIDEQUEST_PATTERNS))
            if rh&ACTIONABLE_SIDEQUEST:
                samples.append({'event_id':r.get('event_id'),'page_id':r.get('page_id'),'text':r.get('text','')[:220]})
                if len(samples)>=3: break
        eids=candidate_event_ids(rows)
        candidate={'map_id':mid,'score':score,'confidence':conf,'evidence':evidence,'samples':samples,'candidate_event_ids':eids}
        cls,reasons=classify_candidate(candidate,byev,explicit_idx)
        candidate['semantic_class']=cls; candidate['classification_reasons']=reasons
        candidates.append(candidate)
    candidates.sort(key=lambda x:(-x['score'],x['map_id']))
    return candidates,len(boilerplate),explicit

def ending_candidates(dialogue,graph,norm):
    by=dialogue_by_map(dialogue); boilerplate=repeated_texts(by)
    terminal=set(norm.get('leaf_maps',[])) | set(norm.get('isolated_maps',[])); candidates=[]
    for mid,raw_rows in by.items():
        rows=informative_rows(raw_rows,boilerplate); text='\n'.join(r.get('text','') for r in rows)
        hits=sorted(set(term_hits(text,ENDING_PATTERNS)))
        if not hits: continue
        score=2*len(hits); evidence=[f'ending_language:{hits}']
        if mid in terminal: score+=2; evidence.append('terminal_like_topology')
        conf='HIGH' if score>=6 else ('MEDIUM' if score>=4 else 'LOW'); samples=[]
        for r in rows:
            if term_hits(r.get('text',''),ENDING_PATTERNS):
                samples.append({'event_id':r.get('event_id'),'page_id':r.get('page_id'),'text':r.get('text','')[:260]})
                if len(samples)>=4: break
        candidates.append({'map_id':mid,'score':score,'confidence':conf,'evidence':evidence,'samples':samples})
    candidates.sort(key=lambda x:(-x['score'],x['map_id']))
    return candidates

def content_endpoints(dialogue):
    found=[]; seen=set()
    for r in dialogue.get('rows',[]):
        if r.get('kind')!='dialogue' or r.get('scope')!='map': continue
        text=r.get('text') or ''
        if not CONTENT_ENDPOINT_RE.search(text): continue
        key=(r.get('map_id'),r.get('event_id'),r.get('page_id'))
        if key in seen: continue
        seen.add(key)
        found.append({'map_id':r.get('map_id'),'event_id':r.get('event_id'),'page_id':r.get('page_id'),'classification':'CONTENT_ENDPOINT_UNFINISHED_RELEASE','confidence':'HIGH','text':text[:500]})
    return found

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('dialogue_json'); ap.add_argument('map_graph_json'); ap.add_argument('normalized_graph_json'); ap.add_argument('--out',required=True)
    a=ap.parse_args(); d=load(a.dialogue_json); g=load(a.map_graph_json); n=load(a.normalized_graph_json)
    sq,suppressed,explicit=sidequest_candidates(d,g,n); en=ending_candidates(d,g,n); ep=content_endpoints(d)
    cls=lambda name:[x for x in sq if x.get('semantic_class')==name]
    mainline=cls('MAINLINE_GATE'); optional=cls('OPTIONAL_CONTENT'); unresolved=cls('QUEST_CANDIDATE_UNRESOLVED')
    status='ENDING_SIGNAL_PRESENT' if en else ('UNFINISHED_CONTENT_ENDPOINT' if ep else 'UNKNOWN')
    summary={
      'sidequest_candidate_maps':len(sq),
      'sidequest_high_confidence_maps':sum(x['confidence']=='HIGH' for x in sq),
      'sidequest_medium_confidence_maps':sum(x['confidence']=='MEDIUM' for x in sq),
      'ending_candidate_maps':len(en),
      'ending_high_confidence_maps':sum(x['confidence']=='HIGH' for x in en),
      'ending_medium_confidence_maps':sum(x['confidence']=='MEDIUM' for x in en),
      'explicit_sidequest_maps':len({x['map_id'] for x in explicit}),
      'mainline_gate_maps':len({x['map_id'] for x in mainline}),
      'optional_content_maps':len({x['map_id'] for x in optional}),
      'unresolved_quest_candidate_maps':len({x['map_id'] for x in unresolved}),
      'content_endpoint_maps':len({x['map_id'] for x in ep}),
      'release_completion_status':status,
      'boilerplate_text_blocks_suppressed':suppressed,
      'interpretation':'Candidates are inference, not official quest/ending counts. v1.2 preserves v1.1 candidate recall but factorizes candidates into explicit sidequest, mainline gate, optional content, or unresolved. Unfinished content endpoints are distinct from completed endings.'
    }
    out={'schema':'fangame-content-inference-v1.2','summary':summary,'sidequest_candidates':sq,'explicit_sidequest_candidates':explicit,'mainline_gate_candidates':mainline,'optional_content_candidates':optional,'unresolved_quest_candidates':unresolved,'content_endpoints':ep,'ending_candidates':en}
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
