#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPLAY_VERSION = "fangame.evidence.replay.v0.6"
OUTPUT_SCHEMA = "fangame.features.v0.5b"
ROOT = Path(__file__).resolve().parents[1]

TOOLCHAIN = [
    "tools/fangame_evidence_replay.py",
    "tools/fangame_inspect.py",
    "tools/rpgmaker_marshal_probe.rb",
    "tools/rpgmaker_graph_probe.rb",
    "tools/rpgmaker_progression_probe.rb",
    "tools/fangame_feature_emitter.py",
    "tools/fangame_graph_feature_merge.py",
    "tools/fangame_graph_inference.py",
    "tools/fangame_inference_feature_merge.py",
    "tools/fangame_progression_feature_merge.py",
    "tools/fangame_grind_vector.py",
    "tools/fangame_grind_vector_feature_merge.py",
    "schemas/fangame_features_v05b.schema.json",
]


def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def find_one(root: Path, name: str, required=True):
    direct = root / name
    if direct.exists():
        return direct
    matches = [p for p in root.rglob(name) if p.is_file()]
    if len(matches) == 1:
        return matches[0]
    if not matches and not required:
        return None
    if not matches:
        raise SystemExit(f"required replay input not found: {name}")
    raise SystemExit(f"ambiguous replay input {name}: {[str(x) for x in matches[:10]]}")


def parse_expected_sha(path: Path | None):
    if not path or not path.exists():
        return None
    for token in path.read_text(encoding="utf-8", errors="ignore").replace("*", " ").split():
        t = token.strip().lower()
        if len(t) == 64 and all(c in "0123456789abcdef" for c in t):
            return t
    return None


def run(cmd):
    subprocess.run([str(x) for x in cmd], cwd=ROOT, check=True)


def toolchain_hashes():
    rows = []
    for rel in TOOLCHAIN:
        p = ROOT / rel
        if not p.exists():
            raise SystemExit(f"replay toolchain file missing: {rel}")
        rows.append({"path": rel, "sha256": sha256_file(p)})
    return rows


def main():
    ap = argparse.ArgumentParser(description="Replay immutable Fangame raw artifact through current evidence collectors.")
    ap.add_argument("--bundle", required=True, help="Extracted historical *-full GitHub Actions artifact directory")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--target", help="Optional current target manifest for title/provenance enrichment")
    ap.add_argument("--source-run-id")
    ap.add_argument("--source-artifact-name")
    args = ap.parse_args()

    bundle = Path(args.bundle).resolve()
    out = Path(args.outdir).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    fetch_report_path = find_one(bundle, "fetch_report.json")
    sha_txt = find_one(bundle, "SHA256.txt", required=False)
    fetch = load_json(fetch_report_path)
    archive_name = fetch.get("file")
    if not archive_name:
        raise SystemExit("fetch_report.json does not contain accepted archive filename in key 'file'")

    archive = find_one(bundle, Path(archive_name).name)
    actual_sha = sha256_file(archive)
    expected_sha = parse_expected_sha(sha_txt) or (fetch.get("sha256") or "").lower() or None
    if expected_sha and actual_sha != expected_sha:
        raise SystemExit(f"immutable raw artifact SHA256 mismatch: expected={expected_sha} actual={actual_sha}")

    # Preserve the historical identity contract alongside the new derivation.
    shutil.copy2(fetch_report_path, out / "source_fetch_report.json")
    (out / "SOURCE_SHA256.txt").write_text(f"{actual_sha}  {archive.name}\n", encoding="utf-8")

    work = out / "replay_work"
    static = out / "playability_static.json"
    graph = out / "rpgmaker_graph.json"
    progression = out / "rpgmaker_progression.json"
    features = out / "fangame_features.json"
    inference = out / "fangame_inference.json"
    grind_vector = out / "fangame_grind_vector.json"

    run([
        sys.executable, ROOT / "tools/fangame_inspect.py", archive,
        "--workdir", work,
        "--out", static,
        "--graph-out", graph,
        "--progression-out", progression,
    ])

    emitter = [
        sys.executable, ROOT / "tools/fangame_feature_emitter.py",
        "--fetch", fetch_report_path,
        "--static", static,
        "--out", features,
    ]
    if sha_txt:
        emitter += ["--sha256", sha_txt]
    target = Path(args.target).resolve() if args.target else None
    if target and target.exists():
        emitter += ["--target", target]
    run(emitter)

    graph_merge = [sys.executable, ROOT / "tools/fangame_graph_feature_merge.py", "--features", features, "--out", features]
    if graph.exists():
        graph_merge += ["--graph", graph]
    run(graph_merge)

    inference_merge = [sys.executable, ROOT / "tools/fangame_inference_feature_merge.py", "--features", features, "--out", features]
    if graph.exists():
        run([sys.executable, ROOT / "tools/fangame_graph_inference.py", "--graph", graph, "--out", inference])
        inference_merge += ["--inference", inference]
    run(inference_merge)

    progression_merge = [sys.executable, ROOT / "tools/fangame_progression_feature_merge.py", "--features", features, "--out", features]
    if progression.exists():
        progression_merge += ["--progression", progression]
    run(progression_merge)

    run([sys.executable, ROOT / "tools/fangame_grind_vector.py", "--features", features, "--out", grind_vector])
    run([
        sys.executable, ROOT / "tools/fangame_grind_vector_feature_merge.py",
        "--features", features, "--vector", grind_vector, "--out", features,
    ])

    rec = load_json(features)
    if rec.get("schema_version") != OUTPUT_SCHEMA:
        raise SystemExit(f"unexpected replay feature schema: {rec.get('schema_version')}")
    try:
        import jsonschema
    except ImportError:
        pass
    else:
        schema = load_json(ROOT / "schemas/fangame_features_v05b.schema.json")
        jsonschema.validate(rec, schema)

    manifest = {
        "replay_version": REPLAY_VERSION,
        "source": {
            "github_actions_run_id": args.source_run_id,
            "github_actions_artifact_name": args.source_artifact_name,
            "historical_fetch_report": "source_fetch_report.json",
            "archive_filename": archive.name,
            "archive_bytes": archive.stat().st_size,
            "archive_sha256": actual_sha,
            "expected_sha256": expected_sha,
            "sha256_verified": expected_sha is None or expected_sha == actual_sha,
        },
        "immutability": {
            "raw_artifact_changed": False,
            "archive_repacked": False,
            "archive_executed": False,
        },
        "replay_scope": {
            "static_structure_replayed": True,
            "graph_replayed": graph.exists(),
            "progression_economy_replayed": progression.exists(),
            "grind_vector_replayed": grind_vector.exists(),
            "runtime_replayed": False,
            "historical_runtime_evidence_carried_forward": False,
        },
        "output": {
            "feature_schema": rec.get("schema_version"),
            "graph_version": (rec.get("graph") or {}).get("graph_version"),
            "progression_evidence_version": (rec.get("progression") or {}).get("evidence_version"),
            "grind_vector_version": (rec.get("grind_vector") or {}).get("vector_version"),
            "grind_pressure": (rec.get("inferred") or {}).get("grind_pressure"),
            "estimated_hours_range": (rec.get("inferred") or {}).get("estimated_hours_range"),
        },
        "toolchain": toolchain_hashes(),
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    (out / "replay_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # The extracted working tree is derivation scratch, not a durable replay product.
    if work.exists():
        shutil.rmtree(work)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
