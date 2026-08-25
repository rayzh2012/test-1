#!/usr/bin/env python3
import argparse, json
from pathlib import Path

CONTRACT_VERSION = "fangame.normalized_profile.contract.v0.2"
SCHEMA = "fangame.normalized_profile.v0.1"


def infer_parser_family(engine):
    e = (engine or "").upper()
    if "RPG MAKER MV" in e or "RPG MAKER MZ" in e:
        return "MV_JSON"
    if "RPG MAKER XP" in e or "RPG MAKER VX ACE" in e or e.strip() == "RPG MAKER VX":
        return "RGSS_MARSHAL"
    if "RPG MAKER 2000" in e or "RPG MAKER 2003" in e:
        return "RPG2000_2003"
    return None


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else {}


def first_source(target):
    if target.get("source_url"):
        return target["source_url"]
    if target.get("source"):
        return target["source"]
    sources = target.get("sources")
    return sources[0] if isinstance(sources, list) and sources else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-json")
    args = ap.parse_args()

    p = load(args.profile)
    target = load(args.target_json)
    if p.get("schema") != SCHEMA:
        raise SystemExit(f"incompatible normalized schema: {p.get('schema')!r}")

    # Stable corpus identity comes from the declared target, never from a parser slug,
    # while measured bytes/SHA and structural metrics remain parser outputs.
    if target:
        p["game_id"] = target.get("game_id") or target.get("id") or p.get("game_id")
        p["title"] = target.get("name") or target.get("title") or p.get("title")
        p["version"] = target.get("version") or target.get("release_version") or p.get("version")
        p["engine"] = target.get("engine") or p.get("engine")
        p["source_url"] = first_source(target) or p.get("source_url")
        p["corpus_role"] = target.get("corpus_role") or p.get("corpus_role")
        p["source_kind"] = target.get("source_kind") or p.get("source_kind")
        if target.get("provenance_note"):
            p["provenance_note"] = target["provenance_note"]

    family = p.get("parser_family") or infer_parser_family(p.get("engine"))
    if not family:
        raise SystemExit(f"cannot resolve parser_family for engine {p.get('engine')!r}")
    p["parser_family"] = family
    p["profile_contract_version"] = CONTRACT_VERSION
    p["baseline_compatibility"] = {
        "normalized_schema": SCHEMA,
        "parser_family": family,
        "rule": "EXACT_SCHEMA_AND_PARSER_FAMILY"
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(p, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"game_id": p.get("game_id"), "engine": p.get("engine"), "parser_family": family, "contract": CONTRACT_VERSION}, ensure_ascii=False))


if __name__ == "__main__":
    main()
