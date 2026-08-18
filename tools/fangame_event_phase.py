#!/usr/bin/env python3
import argparse,json
from collections import defaultdict,deque

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('inventory'); ap.add_argument('normalized'); ap.add_argument('--out',default='event_phase.json'); a=ap.parse_args()
    inv=json.load(open(a.inventory,encoding='utf-8')); norm=json.load(open(a.normalized,encoding='utf-8'))
    start=inv.get('start_map_id')
    adj=defaultdict(set)
    for e in norm.get('normalized_edges',[]):
        x,y=int(e['map_a']),int(e['map_b']); adj[x].add(y); adj[y].add(x)
    dist={}
    if start:
        q=deque([int(start)]); dist[int(start)]=0
        while q:
            u=q.popleft()
            for v in adj[u]:
                if v not in dist: dist[v]=dist[u]+1; q.append(v)
    reached=sorted(dist.values())
    maxd=max(reached) if reached else 0
    def phase(mid):
        if mid not in dist: return 'UNREACHED_OR_OPTIONAL'
        if maxd<=0:return 'EARLY'
        r=dist[mid]/maxd
        return 'EARLY' if r<0.34 else ('MID' if r<0.67 else 'LATE')
    totals=defaultdict(lambda: defaultdict(int)); maps=[]
    for m in inv.get('maps',[]):
        mid=int(m['map_id']); ph=phase(mid)
        row={'map_id':mid,'phase':ph,'distance_from_start':dist.get(mid),'event_count':m.get('event_count',0),'event_pages':m.get('event_pages',0),'dialogue_commands':m.get('dialogue_commands',0),'battle_calls':m.get('battle_calls',0),'shop_calls':m.get('shop_calls',0)}
        maps.append(row)
        for k in ('event_count','event_pages','dialogue_commands','battle_calls','shop_calls'): totals[ph][k]+=row[k]
        totals[ph]['maps']+=1
    summary={p:dict(v) for p,v in totals.items()}
    out={'schema':'fangame-event-phase-v1','start_map_id':start,'max_shortest_path_distance':maxd,'phase_rule':'Shortest-path distance from RPG Maker start map, split into thirds. UNREACHED_OR_OPTIONAL means disconnected from the normalized transfer graph and is not automatically a sidequest.','summary_by_phase':summary,'maps':sorted(maps,key=lambda x:x['map_id'])}
    json.dump(out,open(a.out,'w',encoding='utf-8'),ensure_ascii=False,indent=2)
    print(json.dumps({'start_map_id':start,'max_distance':maxd,'summary_by_phase':summary},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
