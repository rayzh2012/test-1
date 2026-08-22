#!/usr/bin/env python3
import argparse, json
from pathlib import Path

CONTRACT_VERSION = "fangame.normalized_profile.contract.v0.1"
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    p = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    if p.get("schema") != SCHEMA:
        raise SystemExit(f"incompatible normalized schema: {p.get('schema')!r}")
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
