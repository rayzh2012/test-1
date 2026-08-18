#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

SCHEMA_VERSION = "fangame.features.v0.5a"
BRIDGE_VERSION = "0.5a.0"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--progression")
    ap.add_argument("--out")
    args = ap.parse_args()

    record = load(args.features)
    incoming_version = record.get("schema_version")
    progression = load(args.progression) if args.progression and Path(args.progression).exists() else {}
    observed = progression.get("observed") if isinstance(progression.get("observed"), dict) else {}
    derived = progression.get("derived") if isinstance(progression.get("derived"), dict) else {}

    if progression and observed:
        status = "PROGRESSION_OBSERVED"
    elif progression:
        status = "PROGRESSION_PRESENT_NO_OBSERVED"
    else:
        status = "PROGRESSION_UNAVAILABLE"

    record["schema_version"] = SCHEMA_VERSION
    record["progression"] = {
        "status": status,
        "evidence_version": progression.get("evidence_version") if progression else None,
        "observed": observed,
        "derived": derived,
        "limitations": progression.get("limitations", []) if progression else [],
        "load_error_count": len(progression.get("load_errors", []) or []) if progression else 0,
    }

    # v0.5a is evidence-only by contract. Policy/model outputs are deliberately cleared.
    inferred = record.setdefault("inferred", {})
    inferred["estimated_hours_range"] = None
    inferred["grind_pressure"] = None
    inferred["progression_inference_status"] = "NOT_RUN_V0.5A_EVIDENCE_ONLY"

    evidence = record.setdefault("evidence", {})
    evidence["progression_report"] = (
        Path(args.progression).name if args.progression and Path(args.progression).exists() else None
    )

    audit = record.setdefault("audit", {})
    audit["pre_progression_feature_version"] = incoming_version
    audit["progression_bridge_version"] = BRIDGE_VERSION
    audit["progression_evidence_version"] = progression.get("evidence_version") if progression else None

    out = Path(args.out or args.features)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
