#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

SCHEMA_VERSION = "fangame.features.v0.5b"
BRIDGE_VERSION = "0.5b.0"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--vector")
    ap.add_argument("--out")
    args = ap.parse_args()

    record = load(args.features)
    incoming_version = record.get("schema_version")
    vector = load(args.vector) if args.vector and Path(args.vector).exists() else {}

    if vector:
        block = {
            "status": vector.get("status"),
            "vector_version": vector.get("vector_version"),
            "coverage": vector.get("coverage"),
            "missing_core_inputs": vector.get("missing_core_inputs", []),
            "features": vector.get("features", {}),
            "context_only": vector.get("context_only", {}),
            "calibration_status": vector.get("calibration_status"),
            "policy": vector.get("policy", {}),
        }
    else:
        block = {
            "status": "VECTOR_UNAVAILABLE",
            "vector_version": None,
            "coverage": 0.0,
            "missing_core_inputs": [],
            "features": {},
            "context_only": {},
            "calibration_status": "UNLABELED_VECTOR_ONLY",
            "policy": {
                "weighted_score_emitted": False,
                "hours_estimate_emitted": False,
                "note": "Grind vector artifact unavailable; no inference is permitted."
            },
        }

    record["schema_version"] = SCHEMA_VERSION
    record["grind_vector"] = block

    inferred = record.setdefault("inferred", {})
    inferred["grind_pressure"] = None
    inferred["estimated_hours_range"] = None
    inferred["grind_inference_status"] = "CALIBRATION_NOT_RUN"

    evidence = record.setdefault("evidence", {})
    evidence["grind_vector_report"] = Path(args.vector).name if args.vector and Path(args.vector).exists() else None

    audit = record.setdefault("audit", {})
    audit["pre_grind_vector_feature_version"] = incoming_version
    audit["grind_vector_bridge_version"] = BRIDGE_VERSION
    audit["grind_vector_version"] = vector.get("vector_version") if vector else None

    out = Path(args.out or args.features)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
