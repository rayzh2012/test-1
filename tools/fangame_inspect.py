#!/usr/bin/env python3
import argparse, json, math, os, re, shutil, subprocess
from pathlib import Path

DATA_PATTERNS = {
    'RPG Maker XP': ('*.rxdata', 'Map*.rxdata'),
    'RPG Maker VX': ('*.rvdata', 'Map*.rvdata'),
    'RPG Maker VX Ace': ('*.rvdata2', 'Map*.rvdata2'),
    'RPG Maker 2000/2003': ('*.ldb', 'Map*.lmu'),
}

def extract_archive(src: Path, dst: Path):
    dst.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(['7z','x','-y','-bd',f'-o{dst}',str(src)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return p.returncode == 0, p.stdout[-4000:]

def score_root(p: Path):
    names = {x.name.lower() for x in p.iterdir()} if p.is_dir() else set()
    score = 0
    for n,w in [('game.exe',8),('game.ini',8),('rpg_rt.exe',10),('rpg_rt.ini',6),('data',6),('graphics',3),('audio',3),('www',5)]:
        if n in names: score += w
    if (p/'www'/'data'/'System.json').exists() or (p/'data'/'System.json').exists(): score += 10
    return score

def find_game_root(root: Path):
    best=(score_root(root),root)
    for p in root.rglob('*'):
        if p.is_dir():
            try: s=score_root(p)
            except Exception: continue
            if s>best[0]: best=(s,p)
    return best[1], best[0]

def read_game_ini(root: Path):
    p=root/'Game.ini'
    if not p.exists(): return ''
    b=p.read_bytes()
    for enc in ('utf-8','gb18030','big5','shift_jis','latin1'):
        try: return b.decode(enc)
        except Exception: pass
    return b.decode('latin1','ignore')

def detect_engine(root: Path):
    ini=read_game_ini(root)
    m=re.search(r'Library\s*=\s*([^\r\n]+)',ini,re.I)
    lib=(m.group(1).strip() if m else '')
    u=lib.upper()
    if 'RGSS1' in u or (root/'Game.rgssad').exists(): return 'RPG Maker XP', lib
    if 'RGSS2' in u or (root/'Game.rgss2a').exists(): return 'RPG Maker VX', lib
    if 'RGSS3' in u or (root/'Game.rgss3a').exists(): return 'RPG Maker VX Ace', lib
    if (root/'RPG_RT.exe').exists() or (root/'RPG_RT.ldb').exists(): return 'RPG Maker 2000/2003', lib
    if (root/'www'/'data'/'System.json').exists(): return 'RPG Maker MV', lib
    if (root/'data'/'System.json').exists() and ((root/'Game.exe').exists() or (root/'package.json').exists()): return 'RPG Maker MV/MZ', lib
    return 'UNKNOWN', lib

def files_matching(root: Path, pattern: str):
    return [p for p in root.rglob(pattern) if p.is_file()]

def count_assets(root: Path):
    exts_img={'.png','.jpg','.jpeg','.bmp','.gif','.webp'}
    exts_audio={'.ogg','.mp3','.wav','.wma','.mid','.midi','.m4a','.opus'}
    image=audio=0
    image_bytes=audio_bytes=0
    for p in root.rglob('*'):
        if not p.is_file(): continue
        e=p.suffix.lower()
        try: sz=p.stat().st_size
        except OSError: sz=0
        if e in exts_img: image+=1; image_bytes+=sz
        if e in exts_audio: audio+=1; audio_bytes+=sz
    return image,image_bytes,audio,audio_bytes

def literal_text_chars(root: Path):
    # Exact for plain-text formats only. Binary RPG Maker data is represented separately by map/data byte proxies.
    exts={'.txt','.rb','.json','.ini','.js','.csv','.md'}
    chars=cjk=words=0
    for p in root.rglob('*'):
        if not p.is_file() or p.suffix.lower() not in exts: continue
        try:
            b=p.read_bytes()
            text=''
            for enc in ('utf-8','gb18030','big5','shift_jis'):
                try: text=b.decode(enc); break
                except Exception: continue
            if not text: text=b.decode('latin1','ignore')
            chars+=len(text)
            cjk+=sum(1 for ch in text if '\u3400' <= ch <= '\u9fff')
            words+=len(re.findall(r"[A-Za-z]{2,}",text))
        except Exception: pass
    return chars,cjk,words

def scale_label(map_count, map_bytes, asset_count):
    signal = map_count + min(250, map_bytes//150000) + min(150, asset_count//8)
    if signal >= 500: return 'VERY_LARGE'
    if signal >= 260: return 'LARGE'
    if signal >= 120: return 'MEDIUM'
    if signal >= 45: return 'SMALL'
    return 'TINY_OR_OPAQUE'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('archive')
    ap.add_argument('--workdir',default='playability_work')
    ap.add_argument('--out',default='playability_static.json')
    args=ap.parse_args()
    src=Path(args.archive).resolve(); work=Path(args.workdir).resolve()
    if work.exists(): shutil.rmtree(work)
    ok,log=extract_archive(src,work/'extract')
    result={'archive':src.name,'extract_ok':ok,'extract_log_tail':log}
    if not ok:
        result.update({'engine':'UNKNOWN','playability_structural':'FAILED_EXTRACT'})
        Path(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8'); return 2
    root,root_score=find_game_root(work/'extract')
    engine,lib=detect_engine(root)
    pattern=DATA_PATTERNS.get(engine)
    data_files=[]; map_files=[]
    if pattern:
        data_files=files_matching(root,pattern[0]); map_files=files_matching(root,pattern[1])
    elif engine.startswith('RPG Maker MV'):
        d=(root/'www'/'data') if (root/'www'/'data').exists() else (root/'data')
        data_files=list(d.glob('*.json')) if d.exists() else []
        map_files=list(d.glob('Map*.json')) if d.exists() else []
    map_bytes=sum(p.stat().st_size for p in map_files)
    data_bytes=sum(p.stat().st_size for p in data_files)
    img,img_b,aud,aud_b=count_assets(root)
    chars,cjk,words=literal_text_chars(root)
    encrypted=any((root/n).exists() for n in ('Game.rgssad','Game.rgss2a','Game.rgss3a'))
    clean_launcher=(root/'Game.exe').exists() or (root/'RPG_RT.exe').exists()
    result.update({
        'game_root':str(root.relative_to(work/'extract')) if root != work/'extract' else '.',
        'root_score':root_score,
        'engine':engine,
        'rgss_library':lib,
        'clean_launcher_present':clean_launcher,
        'encrypted_game_archive':encrypted,
        'map_count':len(map_files),
        'map_data_bytes':map_bytes,
        'data_file_count':len(data_files),
        'data_bytes':data_bytes,
        'image_count':img,'image_bytes':img_b,
        'audio_count':aud,'audio_bytes':aud_b,
        'literal_text_chars':chars,
        'literal_cjk_chars':cjk,
        'literal_latin_words':words,
        'content_scale':scale_label(len(map_files),map_bytes,img+aud),
        'text_note':'literal_text_* counts plain-text formats only; binary/encrypted RPG Maker event text is not counted exactly. map_data_bytes/data_bytes are the structural story/event-volume proxy.',
        'playability_structural':'STRUCTURAL_OK' if root_score>=8 and (clean_launcher or engine!='UNKNOWN') else 'STRUCTURAL_WEAK'
    })
    Path(args.out).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
