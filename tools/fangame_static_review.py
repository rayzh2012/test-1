#!/usr/bin/env python3
"""Lightweight static inspection for rescued RPG Maker/freeware archives.

This is NOT a claim of interactive gameplay. It inspects archive structure to
estimate engine/completeness, identify the clean launcher, flag repack wrappers,
and (when possible) inspect a large nested self-extracting EXE without running it.
Output is JSON for the preservation catalog.
"""
from __future__ import annotations
import json, os, re, subprocess, sys, tempfile, zipfile
from pathlib import Path

WRAPPER_PATTERNS = [
    r"智能安装", r"高速下载", r"高速安装", r"下载器", r"安装器", r"PlayGame\.exe$",
    r"开始游戏\.exe$", r"962", r"9?9dj", r"游侠", r"多特"
]


def sevenzip_details(path: Path):
    """Return [(name,size)], archive type using 7z -slt, without executing content."""
    try:
        p=subprocess.run(["7z","l","-slt",str(path)], text=True, capture_output=True, timeout=180)
        if p.returncode != 0:
            return [], "UNKNOWN"
        first=(p.stdout[:1500]).lower()
        typ="RAR" if "type = rar" in first else ("ZIP" if "type = zip" in first else "7Z/OTHER")
        rows=[]; cur={}
        for line in p.stdout.splitlines():
            if not line.strip():
                if cur.get("Path") and cur["Path"] != str(path):
                    try: size=int(cur.get("Size","0") or 0)
                    except Exception: size=0
                    rows.append((cur["Path"],size))
                cur={}; continue
            if " = " in line:
                k,v=line.split(" = ",1)
                if k in {"Path","Size"}: cur[k]=v.strip()
        if cur.get("Path") and cur["Path"] != str(path):
            try: size=int(cur.get("Size","0") or 0)
            except Exception: size=0
            rows.append((cur["Path"],size))
        return rows,typ
    except Exception:
        return [],"UNKNOWN"


def list_archive(path: Path):
    if zipfile.is_zipfile(path):
        try:
            with zipfile.ZipFile(path) as z:
                return [(x.filename,x.file_size) for x in z.infolist()], "ZIP"
        except Exception:
            pass
    return sevenzip_details(path)


def norm(s): return s.replace('\\','/')


def inspect_large_nested_exe(archive: Path, entries):
    """Inspect at most two large EXEs as archive/SFX containers; never execute them."""
    candidates=[]
    for name,size in entries:
        n=norm(name)
        if n.lower().endswith('.exe') and size >= 10*1024*1024:
            if not any(re.search(q,n,re.I) for q in WRAPPER_PATTERNS):
                candidates.append((n,size))
    candidates=sorted(candidates,key=lambda x:x[1],reverse=True)[:2]
    reports=[]; nested_names=[]
    for name,size in candidates:
        rec={"path":name,"bytes":size,"inspectable":False,"entries":0,"archive_type":"UNKNOWN"}
        try:
            with tempfile.TemporaryDirectory(prefix="fangame_nested_") as td:
                # Extract exactly the candidate file; do not run it.
                cp=subprocess.run(["7z","e","-y",f"-o{td}",str(archive),name],text=True,capture_output=True,timeout=240)
                if cp.returncode != 0:
                    rec["error"]="extract_failed"
                    reports.append(rec); continue
                ep=Path(td)/Path(name).name
                if not ep.exists():
                    rec["error"]="extracted_file_missing"
                    reports.append(rec); continue
                sub,typ=sevenzip_details(ep)
                rec["archive_type"]=typ
                rec["entries"]=len(sub)
                rec["inspectable"]=bool(sub)
                if sub:
                    normalized=[norm(x[0]) for x in sub]
                    nested_names.extend(normalized)
                    rec["sample_entries"]=normalized[:30]
                reports.append(rec)
        except Exception as e:
            rec["error"]=type(e).__name__
            reports.append(rec)
    return reports,nested_names


def main():
    if len(sys.argv)<2:
        raise SystemExit("usage: fangame_static_review.py ARCHIVE [OUTPUT]")
    p=Path(sys.argv[1])
    out=Path(sys.argv[2]) if len(sys.argv)>2 else Path("ai_static_review.json")
    entries,atype=list_archive(p)
    names=[norm(x[0]) for x in entries]
    nested_reports,nested_names=inspect_large_nested_exe(p,entries)
    analysis_names=names+nested_names
    low=[x.lower() for x in analysis_names]
    ext=lambda e: sum(x.endswith(e) for x in low)
    map_count=sum(bool(re.search(r"(?:^|/)map\d+\.(?:rxdata|rvdata|rvdata2)$",x)) for x in low)
    has=lambda pat: any(re.search(pat,x,re.I) for x in analysis_names)
    outer_exe=[x for x in names if x.lower().endswith('.exe')]
    all_exe=[x for x in analysis_names if x.lower().endswith('.exe')]
    wrappers=[x for x in outer_exe if any(re.search(q,x,re.I) for q in WRAPPER_PATTERNS)]
    clean=[]
    for x in all_exe:
        if x.rsplit('/',1)[-1].lower()=='game.exe': clean.append(x)
    engine="UNKNOWN"
    if ext('.rvdata2') or has(r'rgss3\d*e\.dll$'): engine="RPG Maker VX Ace / RGSS3"
    elif ext('.rvdata') or has(r'rgss2\d*e\.dll$'): engine="RPG Maker VX / RGSS2"
    elif ext('.rxdata') or has(r'rgss10\d.*\.dll$'): engine="RPG Maker XP / RGSS1"
    elif has(r'game\.rpgproject$') or has(r'www/data/.*\.json$') or has(r'/data/.*\.json$'): engine="RPG Maker MV/MZ-like"
    data_count=sum('/data/' in ('/'+x.lower()) or x.lower().startswith('data/') for x in analysis_names)
    graphics_count=sum('/graphics/' in ('/'+x.lower()) or x.lower().startswith('graphics/') or '/img/' in ('/'+x.lower()) for x in analysis_names)
    audio_count=sum('/audio/' in ('/'+x.lower()) or x.lower().startswith('audio/') for x in analysis_names)
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
        "nested_large_exe_inspection":nested_reports,
        "nested_entries_used_for_analysis":len(nested_names),
        "completeness_confidence":round(completeness,2),
        "catalog_note":"Static structure inspection only; nested EXEs are archive-listed only and never executed. Do not label this as AI gameplay until an actual runtime agent boots and interacts with the game."
    }
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
