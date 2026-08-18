#!/usr/bin/env python3
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def run(cmd, cwd=ROOT):
    t=time.perf_counter()
    p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=True)
    return {'cmd':[str(x) for x in cmd],'returncode':p.returncode,'stdout':p.stdout[-12000:],'stderr':p.stderr[-12000:],'wall_time_sec':round(time.perf_counter()-t,3)}

def require(step, name):
    if step['returncode']!=0:
        raise RuntimeError(f"{name} failed: {step['stderr'] or step['stdout']}")

def main():
    ap=argparse.ArgumentParser(description='Run reusable Fangame Genome pipeline on one package/target')
    src=ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--target-json')
    src.add_argument('--package')
    ap.add_argument('--outdir',required=True)
    ap.add_argument('--workdir',required=True)
    ap.add_argument('--perceptual-threshold',type=int,default=6)
    ap.add_argument('--skip-perceptual',action='store_true')
    a=ap.parse_args()
    out=Path(a.outdir).resolve(); work=Path(a.workdir).resolve(); fetch_dir=work/'fetch'
    shutil.rmtree(out,ignore_errors=True); shutil.rmtree(work,ignore_errors=True)
    out.mkdir(parents=True); work.mkdir(parents=True); fetch_dir.mkdir(parents=True)
    audit=[]

    if a.target_json:
        s=run([sys.executable,str(ROOT/'tools/fangame_fetcher.py'),a.target_json,'-o',str(fetch_dir)])
        audit.append({'stage':'fetch',**s}); require(s,'fetch')
        report=json.loads((fetch_dir/'fetch_report.json').read_text(encoding='utf-8'))
        package=fetch_dir/report['file']
    else:
        package=Path(a.package).resolve()

    static=out/'playability_static.json'
    s=run([sys.executable,str(ROOT/'tools/fangame_inspect.py'),str(package),'--workdir',str(work/'inspect'),'--out',str(static)])
    audit.append({'stage':'inspect',**s}); require(s,'inspect')
    st=json.loads(static.read_text(encoding='utf-8'))
    game_root=(work/'inspect'/'extract'/st['game_root']).resolve()

    stages=[
      ('dialogue',['ruby',str(ROOT/'tools/rpgmaker_dialogue_extract.rb'),str(game_root),'--out',str(out/'dialogue_corpus.json')]),
      ('map_graph',['ruby',str(ROOT/'tools/rpgmaker_map_graph.rb'),str(game_root),'--out',str(out/'map_graph.json')]),
    ]
    for name,cmd in stages:
        s=run(cmd); audit.append({'stage':name,**s}); require(s,name)
    s=run([sys.executable,str(ROOT/'tools/rpgmaker_graph_normalize.py'),str(out/'map_graph.json'),'--out',str(out/'map_graph_normalized.json')])
    audit.append({'stage':'graph_normalize',**s}); require(s,'graph_normalize')
    s=run([sys.executable,str(ROOT/'tools/fangame_content_infer.py'),str(out/'dialogue_corpus.json'),str(out/'map_graph.json'),str(out/'map_graph_normalized.json'),'--out',str(out/'content_inference.json')])
    audit.append({'stage':'content_inference',**s}); require(s,'content_inference')
    s=run([sys.executable,str(ROOT/'tools/fangame_asset_fingerprint.py'),str(game_root),'--out',str(out/'asset_fingerprint.json')])
    audit.append({'stage':'asset_fingerprint',**s}); require(s,'asset_fingerprint')
    if not a.skip_perceptual:
        s=run([sys.executable,str(ROOT/'tools/fangame_perceptual_hash.py'),str(game_root),'--threshold',str(a.perceptual_threshold),'--out',str(out/'perceptual_hash.json')])
        audit.append({'stage':'perceptual_hash',**s}); require(s,'perceptual_hash')

    d=json.loads((out/'dialogue_corpus.json').read_text(encoding='utf-8'))['summary']
    g=json.loads((out/'map_graph.json').read_text(encoding='utf-8'))['summary']
    gn=json.loads((out/'map_graph_normalized.json').read_text(encoding='utf-8'))['summary']
    ci=json.loads((out/'content_inference.json').read_text(encoding='utf-8'))['summary']
    af=json.loads((out/'asset_fingerprint.json').read_text(encoding='utf-8'))['summary']
    ph=json.loads((out/'perceptual_hash.json').read_text(encoding='utf-8'))['summary'] if (out/'perceptual_hash.json').exists() else {}
    m=st.get('marshal_content') or {}; maps=max(1,g.get('map_nodes',0) or 0)
    summary={
      'schema':'fangame-genome-runner-v1.1','engine':st.get('engine'),'game_root':st.get('game_root'),
      'maps':g.get('map_nodes'),'dialogue_blocks':d.get('dialogue_blocks'),'dialogue_chars':d.get('dialogue_chars'),
      'dialogue_density_chars_per_map':round(d.get('dialogue_chars',0)/maps,2),
      'raw_transfer_commands':g.get('transfer_edges'),'normalized_undirected_edges':gn.get('normalized_undirected_edges'),
      'normalized_branching_maps':gn.get('normalized_branching_maps_degree_ge_3'),'connected_component_count':gn.get('connected_component_count'),
      'sidequest_candidate_maps':ci.get('sidequest_candidate_maps'),'ending_candidate_maps':ci.get('ending_candidate_maps'),
      'asset_files':af.get('asset_files'),'exact_reuse_ratio':af.get('exact_reuse_ratio'),
      'perceptual_image_files':ph.get('image_files'),'near_duplicate_clusters':ph.get('near_duplicate_clusters'),
      'battle_calls':m.get('battle_calls'),'shops':m.get('shop_calls'),'choices':m.get('choice_options'),
      'total_pipeline_wall_time_sec':round(sum(x['wall_time_sec'] for x in audit),3),
      'stage_wall_time_sec':{x['stage']:x['wall_time_sec'] for x in audit},
      'note':'Reusable runner. Fetch/cache payload stays outside evidence outdir. Inferred quest/ending counts are candidates, not official counts; pipeline time is measured as evaluation cost.'
    }
    (out/'genome_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'genome_audit.json').write_text(json.dumps({'schema':'fangame-genome-audit-v1','stages':audit},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
