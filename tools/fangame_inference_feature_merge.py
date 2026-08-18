#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

SCHEMA_VERSION = "fangame.features.v0.4"
MERGE_VERSION = "0.4.0"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compact_candidates(items):
    out = []
    for x in items or []:
        out.append({
            "candidate_id": x.get("candidate_id"),
            "score": x.get("score"),
            "confidence": x.get("confidence"),
            "maps": x.get("maps"),
            "source_map_id": x.get("source_map_id"),
            "state_keys": x.get("state_keys"),
            "signal_types": x.get("signal_types"),
            "evidence_node_ids": x.get("evidence_node_ids"),
            "reason_codes": x.get("reason_codes")
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--inference")
    ap.add_argument("--out")
    args = ap.parse_args()

    record = load(args.features)
    inference = load(args.inference) if args.inference and Path(args.inference).exists() else {}

    side = inference.get("sidequests") if isinstance(inference.get("sidequests"), dict) else {}
    endings = inference.get("endings") if isinstance(inference.get("endings"), dict) else {}
    inf = record.setdefault("inferred", {})
    inf["sidequest_candidate_count"] = side.get("candidate_count") if inference else None
    inf["sidequest_confidence"] = side.get("confidence") if inference else "UNKNOWN"
    inf["sidequest_candidates"] = compact_candidates(side.get("candidates")) if inference else []
    inf["ending_candidate_count"] = endings.get("candidate_count") if inference else None
    inf["distinct_terminal_cluster_count"] = endings.get("distinct_terminal_cluster_count") if inference else None
    inf["ending_confidence"] = endings.get("confidence") if inference else "UNKNOWN"
    inf["ending_candidates"] = compact_candidates(endings.get("candidates")) if inference else []
    inf["inference_version"] = inference.get("inference_version") if inference else "none.v0.4"
    inf["evidence_summary"] = (
        f"Graph inference: {side.get('candidate_count', 0)} sidequest candidate(s), "
        f"{endings.get('candidate_count', 0)} ending candidate(s). Counts are structural candidates, not official counts."
        if inference else
        "Graph inference unavailable; candidate fields remain UNKNOWN."
    )

    evidence = record.setdefault("evidence", {})
    evidence["inference_report"] = Path(args.inference).name if args.inference and Path(args.inference).exists() else None

    audit = record.setdefault("audit", {})
    audit["pre_inference_feature_version"] = record.get("schema_version")
    audit["schema_merge_version"] = MERGE_VERSION
    audit["inference_version"] = inf["inference_version"]
    record["schema_version"] = SCHEMA_VERSION

    out = Path(args.out or args.features)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
