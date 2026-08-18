#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

SCHEMA_VERSION = "fangame.features.v0.3"
BRIDGE_VERSION = "0.3.0"


def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--graph")
    ap.add_argument("--out")
    args = ap.parse_args()

    record = load(args.features)
    graph = load(args.graph) if args.graph and Path(args.graph).exists() else {}
    summary = graph.get("summary") if isinstance(graph.get("summary"), dict) else {}

    if graph and summary:
        status = "GRAPH_OBSERVED"
    elif graph:
        status = "GRAPH_PRESENT_NO_SUMMARY"
    else:
        status = "GRAPH_UNAVAILABLE"

    record["schema_version"] = SCHEMA_VERSION
    record["graph"] = {
        "status": status,
        "graph_version": graph.get("graph_version") if graph else None,
        "start_map_id": summary.get("start_map_id"),
        "summary": summary,
    }

    evidence = record.setdefault("evidence", {})
    evidence["graph_report"] = Path(args.graph).name if args.graph and Path(args.graph).exists() else None

    audit = record.setdefault("audit", {})
    audit["base_feature_emitter_version"] = audit.get("feature_emitter_version")
    audit["feature_emitter_version"] = BRIDGE_VERSION
    audit["graph_bridge_version"] = BRIDGE_VERSION

    out = Path(args.out or args.features)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
