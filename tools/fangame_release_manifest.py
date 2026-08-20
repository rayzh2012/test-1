#!/usr/bin/env python3
import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path

SCHEMA_VERSION = "fangame-release-manifest.v0.1"
DEFAULT_IGNORES = [".DS_Store", "Thumbs.db", "desktop.ini"]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def ignored(rel: str, patterns) -> bool:
    name = Path(rel).name
    return any(fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(name, p) for p in patterns)


def root_hash(files) -> str:
    h = hashlib.sha256()
    for row in sorted(files, key=lambda x: x["path"]):
        record = f'{row["path"]}\0{row["size"]}\0{row["sha256"]}\n'.encode("utf-8")
        h.update(record)
    return h.hexdigest()


def build_manifest(root: Path, args):
    root = root.resolve()
    patterns = DEFAULT_IGNORES + list(args.ignore or [])
    rows = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        filenames.sort()
        base = Path(dirpath)
        for name in filenames:
            p = base / name
            if not p.is_file() or p.is_symlink():
                continue
            rel = p.relative_to(root).as_posix()
            if ignored(rel, patterns):
                continue
            rows.append({
                "path": rel,
                "size": p.stat().st_size,
                "sha256": sha256_file(p),
            })
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "game_id": args.game_id,
        "title": args.title,
        "release_id": args.release_id,
        "version": args.version,
        "release_kind": args.kind,
        "parent_release_id": args.parent_release_id,
        "content_root_sha256": root_hash(rows),
        "total_files": len(rows),
        "total_bytes": sum(x["size"] for x in rows),
        "files": rows,
    }
    return manifest


def load_manifest(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != SCHEMA_VERSION:
        raise SystemExit(f"unsupported manifest schema: {data.get('schema_version')}")
    return data


def index_by_path(m):
    return {x["path"]: x for x in m.get("files", [])}


def index_hashes(m):
    out = {}
    for x in m.get("files", []):
        out.setdefault(x["sha256"], []).append(x)
    return out


def diff_manifests(old, new):
    a = index_by_path(old)
    b = index_by_path(new)
    old_hashes = index_hashes(old)
    added, removed, changed, unchanged, reused_by_hash = [], [], [], [], []

    for path in sorted(set(a) | set(b)):
        av = a.get(path)
        bv = b.get(path)
        if av is None:
            added.append(bv)
            if bv["sha256"] in old_hashes:
                reused_by_hash.append({
                    "new_path": path,
                    "sha256": bv["sha256"],
                    "size": bv["size"],
                    "old_paths": [x["path"] for x in old_hashes[bv["sha256"]]],
                })
        elif bv is None:
            removed.append(av)
        elif av["sha256"] == bv["sha256"]:
            unchanged.append(bv)
        else:
            changed.append({"path": path, "old": av, "new": bv})

    content_hashes_old = set(old_hashes)
    reused_content_bytes = sum(
        x["size"] for x in new.get("files", []) if x["sha256"] in content_hashes_old
    )
    total_new = new.get("total_bytes", 0)
    new_content_bytes = max(0, total_new - reused_content_bytes)

    return {
        "schema_version": "fangame-release-diff.v0.1",
        "from_release_id": old.get("release_id"),
        "to_release_id": new.get("release_id"),
        "from_root_sha256": old.get("content_root_sha256"),
        "to_root_sha256": new.get("content_root_sha256"),
        "counts": {
            "added": len(added),
            "removed": len(removed),
            "changed": len(changed),
            "unchanged": len(unchanged),
            "reused_by_hash": len(reused_by_hash),
        },
        "bytes": {
            "target_total": total_new,
            "reused_content": reused_content_bytes,
            "new_or_changed_content": new_content_bytes,
            "reuse_ratio": (reused_content_bytes / total_new) if total_new else 1.0,
        },
        "added": added,
        "removed": removed,
        "changed": changed,
        "unchanged": unchanged,
        "reused_by_hash": reused_by_hash,
    }


def rollback_plan(current, target):
    cur_by_hash = index_hashes(current)
    cur_by_path = index_by_path(current)
    target_by_path = index_by_path(target)

    reuse = []
    need = []
    write_paths = []
    delete_paths = sorted(set(cur_by_path) - set(target_by_path))

    for row in target.get("files", []):
        if row["sha256"] in cur_by_hash:
            reuse.append({
                "target_path": row["path"],
                "sha256": row["sha256"],
                "size": row["size"],
                "candidate_source_paths": [x["path"] for x in cur_by_hash[row["sha256"]]],
            })
        else:
            need.append({"sha256": row["sha256"], "size": row["size"]})
        existing = cur_by_path.get(row["path"])
        if not existing or existing["sha256"] != row["sha256"]:
            write_paths.append(row["path"])

    unique_need = {}
    for x in need:
        unique_need[x["sha256"]] = x

    return {
        "schema_version": "fangame-rollback-plan.v0.1",
        "from_release_id": current.get("release_id"),
        "target_release_id": target.get("release_id"),
        "target_root_sha256": target.get("content_root_sha256"),
        "reuse_objects": reuse,
        "need_objects": sorted(unique_need.values(), key=lambda x: x["sha256"]),
        "write_paths": sorted(write_paths),
        "delete_paths": delete_paths,
        "verification": "After checkout, regenerate manifest and require content_root_sha256 == target_root_sha256.",
    }


def write_json(data, out):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if out:
        Path(out).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main():
    ap = argparse.ArgumentParser(description="Fangame release manifest/diff/rollback planner")
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("manifest", help="build deterministic file-tree manifest")
    m.add_argument("root")
    m.add_argument("--game-id", required=True)
    m.add_argument("--title", required=True)
    m.add_argument("--release-id", required=True)
    m.add_argument("--version", required=True)
    m.add_argument("--kind", default="UNKNOWN", choices=["ORIGINAL", "FIX", "PATCH", "REPACK", "MAJOR", "UNKNOWN"])
    m.add_argument("--parent-release-id")
    m.add_argument("--ignore", action="append", default=[])
    m.add_argument("--out")

    d = sub.add_parser("diff", help="compare two release manifests")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("--out")

    r = sub.add_parser("rollback-plan", help="plan content rollback using current objects")
    r.add_argument("current")
    r.add_argument("target")
    r.add_argument("--out")

    args = ap.parse_args()
    if args.cmd == "manifest":
        write_json(build_manifest(Path(args.root), args), args.out)
    elif args.cmd == "diff":
        write_json(diff_manifests(load_manifest(Path(args.old)), load_manifest(Path(args.new))), args.out)
    else:
        write_json(rollback_plan(load_manifest(Path(args.current)), load_manifest(Path(args.target))), args.out)


if __name__ == "__main__":
    main()
