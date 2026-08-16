#!/usr/bin/env python3
"""Lightweight static inspection for rescued RPG Maker/freeware archives.

This is NOT a claim of interactive gameplay. It inspects archive structure to
estimate engine/completeness, identify the clean launcher, and flag repack
wrappers. Output is JSON for the preservation catalog.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, zipfile
from pathlib import Path

WRAPPER_PATTERNS = [
    r"智能安装", r"高速下载", r"高速安装", r"下载器", r"安装器", r"PlayGame\.exe$",
    r"开始游戏\.exe$", r"962", r"9?9dj", r"游侠", r"多特"
]


def list_archive(path: Path):
    names=[]
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as z:
            names=z.namelist()
        return names, "ZIP"
    try:
        p=subprocess.run(["7z","l","-slt",str(path)], text=True, capture_output=True, timeout=120)
        if p.returncode==0:
            for line in p.stdout.splitlines():
                if line.startswith("Path = "):
                    v=line[7:].strip()
                    if v and v != str(path): names.append(v)
            first=(p.stdout[:1000]).lower()
            typ="RAR" if "type = rar" in first else "7Z/OTHER"
            return names, typ
    except Exception:
        pass
    return [], "UNKNOWN"


def norm(s): return s.replace('\\','/')

def main():
    if len(sys.argv)<2:
        raise SystemExit("usage: fangame_static_review.py ARCHIVE [OUTPUT]")
    p=Path(sys.argv[1])
    out=Path(sys.argv[2]) if len(sys.argv)>2 else Path("ai_static_review.json")
    names=[norm(x) for x in list_archive(p)[0]]
    _, atype=list_archive(p)
    low=[x.lower() for x in names]
    ext=lambda e: sum(x.endswith(e) for x in low)
    map_count=sum(bool(re.search(r"(?:^|/)map\d+\.(?:rxdata|rvdata|rvdata2)$",x)) for x in low)
    has=lambda pat: any(re.search(pat,x,re.I) for x in names)
    exe=[x for x in names if x.lower().endswith('.exe')]
    wrappers=[x for x in exe if any(re.search(q,x,re.I) for q in WRAPPER_PATTERNS)]
    clean=[]
    for x in exe:
        b=x.rsplit('/',1)[-1].lower()
        if b=='game.exe': clean.append(x)
    engine="UNKNOWN"
    if ext('.rvdata2') or has(r'rgss3\d*e\.dll$'): engine="RPG Maker VX Ace / RGSS3"
    elif ext('.rvdata') or has(r'rgss2\d*e\.dll$'): engine="RPG Maker VX / RGSS2"
    elif ext('.rxdata') or has(r'rgss10\d.*\.dll$'): engine="RPG Maker XP / RGSS1"
    elif has(r'game\.rpgproject$') or has(r'www/data/.*\.json$') or has(r'/data/.*\.json$'): engine="RPG Maker MV/MZ-like"
    data_count=sum('/data/' in ('/'+x.lower()) or x.lower().startswith('data/') for x in names)
    graphics_count=sum('/graphics/' in ('/'+x.lower()) or x.lower().startswith('graphics/') or '/img/' in ('/'+x.lower()) for x in names)
    audio_count=sum('/audio/' in ('/'+x.lower()) or x.lower().startswith('audio/') for x in names)
    encrypted=has(r'game\.(?:rgssad|rgss2a|rgss3a)$')
    complete_signals=sum([bool(map_count), bool(data_count or encrypted), bool(audio_count), bool(graphics_count), bool(clean)])
    completeness=min(1.0, complete_signals/5)
    report={
        "review_type":"STATIC_INSPECTION_NOT_GAMEPLAY",
        "archive":p.name,
        "archive_bytes":p.stat().st_size,
        "archive_type":atype,
        "entries":len(names),
        "engine_guess":engine,
        "map_count":map_count,
        "rxdata_count":ext('.rxdata'),
        "rvdata_count":ext('.rvdata'),
        "rvdata2_count":ext('.rvdata2'),
        "data_entries":data_count,
        "graphics_entries":graphics_count,
        "audio_entries":audio_count,
        "encrypted_game_archive":encrypted,
        "clean_game_launchers":clean[:20],
        "repack_wrapper_flags":wrappers[:50],
        "completeness_confidence":round(completeness,2),
        "catalog_note":"Static structure inspection only; do not label this as AI gameplay until an actual runtime agent boots and interacts with the game."
    }
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
