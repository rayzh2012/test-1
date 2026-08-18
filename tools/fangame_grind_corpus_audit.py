#!/usr/bin/env python3
import argparse
import collections
import json
from pathlib import Path

AUDIT_VERSION = "fangame.grind.corpus.audit.v0.5c"
DIMENSIONS = [
    "required_repetition",
    "level_pressure",
    "economy_pressure",
    "encounter_intrusion",
    "recovery_penalty",
    "overall_grind_burden",
]
ORDINAL = ["VERY_LOW", "LOW", "MEDIUM", "HIGH", "VERY_HIGH"]


def load_schema(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_ndjson(path):
    records = []
    for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rec = json.loads(line)
        except Exception as e:
            raise SystemExit(f"invalid JSON at {path}:{lineno}: {e}")
        records.append((lineno, rec))
    return records


def label_value(rec, dim):
    if dim == "overall_grind_burden":
        obj = rec.get(dim)
    else:
        obj = (rec.get("dimensions") or {}).get(dim)
    return obj.get("value") if isinstance(obj, dict) else None


def resolve_active_labels(valid):
    by_id = {x["label_id"]: x for x in valid}
    superseded = set()
    supersession_errors = []
    for rec in valid:
        old = (rec.get("audit") or {}).get("supersedes_label_id")
        if not old:
            continue
        if old == rec["label_id"]:
            supersession_errors.append({"label_id": rec["label_id"], "error": "LABEL_CANNOT_SUPERSEDE_ITSELF"})
            continue
        if old not in by_id:
            supersession_errors.append({"label_id": rec["label_id"], "error": "SUPERSEDED_LABEL_ID_NOT_FOUND", "supersedes": old})
            continue
        if by_id[old].get("game_id") != rec.get("game_id"):
            supersession_errors.append({"label_id": rec["label_id"], "error": "SUPERSESSION_CROSSES_GAME_ID", "supersedes": old})
            continue
        superseded.add(old)

    # Detect cycles/chains that loop. Chains themselves are fine: newest active label wins.
    for rec in valid:
        start = rec["label_id"]
        seen = set()
        cur = start
        while cur in by_id:
            if cur in seen:
                supersession_errors.append({"label_id": start, "error": "SUPERSESSION_CYCLE"})
                break
            seen.add(cur)
            nxt = (by_id[cur].get("audit") or {}).get("supersedes_label_id")
            if not nxt:
                break
            cur = nxt

    active = [x for x in valid if x["label_id"] not in superseded]
    return active, sorted(superseded), supersession_errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--schema", default="schemas/fangame_grind_label_v05c.schema.json")
    ap.add_argument("--out", default="fangame_grind_corpus_audit.json")
    args = ap.parse_args()

    rows = read_ndjson(args.labels)
    schema = load_schema(args.schema)
    try:
        import jsonschema
    except ImportError:
        jsonschema = None

    errors = []
    label_ids = set()
    duplicate_label_ids = []
    valid = []
    for lineno, rec in rows:
        if jsonschema is not None:
            try:
                jsonschema.validate(rec, schema)
            except Exception as e:
                errors.append({"line": lineno, "error": str(e)[:1500]})
                continue
        lid = rec.get("label_id")
        if lid in label_ids:
            duplicate_label_ids.append(lid)
            continue
        label_ids.add(lid)
        valid.append(rec)

    active, superseded_label_ids, supersession_errors = resolve_active_labels(valid)

    by_game = collections.defaultdict(list)
    source_types = collections.Counter()
    vector_versions = collections.Counter()
    coverage = collections.Counter()
    annotators = collections.Counter()
    independence_groups = collections.Counter()
    value_counts = {d: collections.Counter() for d in DIMENSIONS}

    for rec in active:
        by_game[rec["game_id"]].append(rec)
        src = rec["evidence_source"]
        ann = rec["annotation"]
        source_types[src["source_type"]] += 1
        independence_groups[src["independence_group"]] += 1
        vector_versions[rec["feature_vector_version"]] += 1
        coverage[ann["coverage"]] += 1
        annotators[ann["annotator_type"]] += 1
        for dim in DIMENSIONS:
            value_counts[dim][label_value(rec, dim)] += 1

    game_profiles = []
    conflict_count = 0
    for game_id, labels in sorted(by_game.items()):
        independent = sorted({x["evidence_source"]["independence_group"] for x in labels})
        types = sorted({x["evidence_source"]["source_type"] for x in labels})
        conflicts = {}
        for dim in DIMENSIONS:
            vals = sorted({label_value(x, dim) for x in labels if label_value(x, dim) in ORDINAL})
            if len(vals) > 1:
                conflicts[dim] = vals
        if conflicts:
            conflict_count += 1
        game_profiles.append({
            "game_id": game_id,
            "active_label_count": len(labels),
            "independent_evidence_groups": len(independent),
            "independence_groups": independent,
            "source_types": types,
            "conflicting_dimensions": conflicts,
        })

    if not rows:
        status = "CORPUS_EMPTY"
    elif errors or duplicate_label_ids or supersession_errors:
        status = "CORPUS_INVALID"
    elif active:
        status = "CORPUS_VALID_UNGATED"
    else:
        status = "CORPUS_INVALID"

    audit = {
        "audit_version": AUDIT_VERSION,
        "corpus_status": status,
        "records_seen": len(rows),
        "schema_valid_unique_label_records": len(valid),
        "active_label_records": len(active),
        "superseded_label_records": len(superseded_label_ids),
        "superseded_label_ids": superseded_label_ids,
        "distinct_games": len(by_game),
        "distinct_independence_groups": len(independence_groups),
        "source_type_counts": dict(sorted(source_types.items())),
        "feature_vector_versions": dict(sorted(vector_versions.items())),
        "annotation_coverage_counts": dict(sorted(coverage.items())),
        "annotator_type_counts": dict(sorted(annotators.items())),
        "dimension_value_counts": {
            d: {k: v for k, v in sorted(c.items()) if k is not None}
            for d, c in value_counts.items()
        },
        "games_with_conflicting_active_labels": conflict_count,
        "game_profiles": game_profiles,
        "validation_errors": errors,
        "duplicate_label_ids": sorted(set(duplicate_label_ids)),
        "supersession_errors": supersession_errors,
        "training_gate": {
            "status": "NOT_EVALUATED",
            "reason": "No calibration readiness policy supplied. Corpus validation and model-fit readiness are separate decisions.",
        },
        "leakage_policy": {
            "feature_store_contains_ground_truth_labels": False,
            "join_stage": "FUTURE_TRAINING_JOIN_ONLY",
            "note": "Ground-truth/source labels stay outside per-game production Feature Store to reduce label leakage and circular evaluation.",
        },
        "model_outputs": {
            "weights_emitted": False,
            "grind_score_emitted": False,
            "playtime_estimate_emitted": False,
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    if status == "CORPUS_INVALID":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
