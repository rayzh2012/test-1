#!/usr/bin/env python3
import argparse, json
from collections import Counter, defaultdict, deque


def normalize(data):
    nodes = {int(n['map_id']): n for n in data.get('nodes', [])}
    raw = [e for e in data.get('edges', []) if e.get('type') == 'transfer' and e.get('to_map')]
    counts = Counter((int(e['from_map']), int(e['to_map'])) for e in raw)
    pairs = sorted(counts)
    pairset = set(pairs)
    reciprocal_pairs = {tuple(sorted((a,b))) for a,b in pairs if a != b and (b,a) in pairset}

    # Collapse duplicate transfer commands to one directed topology edge. Reciprocal
    # A<->B is retained as one undirected connectivity relation for topology metrics,
    # while directionality remains available in directed_edges.
    directed = [{'from_map':a,'to_map':b,'raw_transfer_count':counts[(a,b)],
                 'reciprocal': (b,a) in pairset} for a,b in pairs]
    undirected_keys = sorted({tuple(sorted((a,b))) for a,b in pairs if a != b})
    undirected = [{'map_a':a,'map_b':b,
                   'a_to_b':counts.get((a,b),0),'b_to_a':counts.get((b,a),0),
                   'reciprocal': (a,b) in pairset and (b,a) in pairset}
                  for a,b in undirected_keys]

    adj = defaultdict(set)
    for e in undirected:
        adj[e['map_a']].add(e['map_b']); adj[e['map_b']].add(e['map_a'])
    degree = {m: len(adj[m]) for m in nodes}
    hubs = sorted(({'map_id':m,'normalized_degree':d} for m,d in degree.items()),
                  key=lambda x:(-x['normalized_degree'],x['map_id']))[:20]
    leaves = sorted(m for m,d in degree.items() if d == 1)
    isolated = sorted(m for m,d in degree.items() if d == 0)
    branching = sorted(m for m,d in degree.items() if d >= 3)

    # Connected components provide a safer structural primitive than raw terminal
    # counts, which are inflated by one-way event semantics and unused maps.
    seen=set(); comps=[]
    for start in sorted(nodes):
        if start in seen: continue
        q=deque([start]); seen.add(start); comp=[]
        while q:
            u=q.popleft(); comp.append(u)
            for v in adj[u]:
                if v not in seen: seen.add(v); q.append(v)
        comps.append(sorted(comp))
    comps.sort(key=lambda c:(-len(c),c[0]))

    summary = {
      'map_nodes': len(nodes),
      'raw_transfer_commands': len(raw),
      'unique_directed_edges': len(directed),
      'normalized_undirected_edges': len(undirected),
      'duplicate_transfer_commands_removed': len(raw)-len(directed),
      'reciprocal_map_pairs': len(reciprocal_pairs),
      'normalized_branching_maps_degree_ge_3': len(branching),
      'normalized_leaf_maps_degree_1': len(leaves),
      'isolated_maps_degree_0': len(isolated),
      'connected_component_count': len(comps),
      'largest_component_size': len(comps[0]) if comps else 0,
      'hub_candidates': hubs,
      'warning': 'Topology normalization reduces duplicate/reciprocal transfer inflation; it does not by itself prove optionality or open-world design.'
    }
    return {'schema':'fangame-map-graph-normalized-v1','summary':summary,
            'directed_edges':directed,'normalized_edges':undirected,
            'branching_maps':branching,'leaf_maps':leaves,'isolated_maps':isolated,
            'connected_components':comps}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('graph_json'); ap.add_argument('--out')
    a=ap.parse_args()
    with open(a.graph_json,'r',encoding='utf-8') as f: data=json.load(f)
    out=normalize(data); text=json.dumps(out,ensure_ascii=False,indent=2)
    if a.out:
        with open(a.out,'w',encoding='utf-8') as f:f.write(text+'\n')
    else: print(text)

if __name__=='__main__': main()
