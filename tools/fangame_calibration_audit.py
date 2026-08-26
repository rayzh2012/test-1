#!/usr/bin/env python3
import argparse
import collections
import json
from pathlib import Path

AUDIT_VERSION = "fangame.calibration.audit.v0.8"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def files_under(path):
    p = Path(path)
    if p.is_file():
        return [p]
    return sorted(x for x in p.rglob("*.json") if x.is_file())


def semantic_errors(rec):
    errors = []
    labels = rec.get("labels") if isinstance(rec.get("labels"), dict) else {}
    hours = labels.get("main_story_hours") if isinstance(labels.get("main_story_hours"), dict) else {}
    grind = labels.get("grind_pressure") if isinstance(labels.get("grind_pressure"), dict) else {}

    if hours.get("status") == "LABELED":
        lo, hi, measured = hours.get("min_hours"), hours.get("max_hours"), hours.get("measured_hours")
        if measured is None and (lo is None or hi is None):
            errors.append("hours labeled but neither measured_hours nor min/max range is complete")
        if lo is not None and hi is not None and lo > hi:
            errors.append("hours min_hours > max_hours")
        if hours.get("basis") == "UNKNOWN" or hours.get("confidence") == "UNKNOWN":
            errors.append("hours labeled with UNKNOWN basis/confidence")
        if not hours.get("evidence_refs"):
            errors.append("hours labeled without evidence_refs")
    elif any(hours.get(k) is not None for k in ("min_hours", "max_hours", "measured_hours")):
        errors.append("hours UNKNOWN but numeric hours are populated")

    if grind.get("status") == "LABELED":
        if grind.get("ordinal") is None:
            errors.append("grind labeled without ordinal")
        if grind.get("basis") == "UNKNOWN" or grind.get("confidence") == "UNKNOWN":
            errors.append("grind labeled with UNKNOWN basis/confidence")
        if not grind.get("evidence_refs"):
            errors.append("grind labeled without evidence_refs")
    elif grind.get("ordinal") is not None:
        errors.append("grind UNKNOWN but ordinal is populated")

    return errors


def baseline_context_ok(rec, policy):
    ctx = rec.get("context") or {}
    req = policy.get("baseline_training_context") or {}
    for key in ("cheats_or_debug_used", "speedup_used"):
        if key in req and ctx.get(key) != req[key]:
            return False
    return True


def label_class(rec, kind, policy):
    labels = rec.get("labels") or {}
    label = labels.get("main_story_hours" if kind == "hours" else "grind_pressure") or {}
    if label.get("status") != "LABELED":
        return "UNLABELED"

    q = policy["hours_quality" if kind == "hours" else "grind_quality"]
    basis = label.get("basis")
    conf = label.get("confidence")
    scope = (rec.get("context") or {}).get("completion_scope")

    if basis in q.get("experimental_basis", []):
        return "EXPERIMENTAL"
    if basis in q.get("reference_only_basis", []):
        return "REFERENCE_ONLY"
    if basis not in q.get("direct_training_basis", []):
        return "REFERENCE_ONLY"
    if conf not in policy.get("training_confidence", []):
        return "REFERENCE_ONLY"
    if scope not in q.get("accepted_completion_scope", []):
        return "CONTEXTUAL_ONLY"
    if not baseline_context_ok(rec, policy):
        return "CONTEXTUAL_ONLY"
    return "DIRECT_TRAINING"


def readiness(records, kind, policy):
    direct = [r for r in records if label_class(r, kind, policy) == "DIRECT_TRAINING"]
    games = {str((r.get("identity") or {}).get("game_id")) for r in direct}
    gate = policy["readiness_gates"][kind]
    reasons = []
    if len(direct) < gate["min_direct_label_records"]:
        reasons.append(f"direct_label_records {len(direct)} < {gate['min_direct_label_records']}")
    if len(games) < gate["min_distinct_games"]:
        reasons.append(f"distinct_games {len(games)} < {gate['min_distinct_games']}")
    ordinal_classes = []
    if kind == "grind":
        ordinal_classes = sorted({(r.get("labels") or {}).get("grind_pressure", {}).get("ordinal") for r in direct if (r.get("labels") or {}).get("grind_pressure", {}).get("ordinal") is not None})
        if len(ordinal_classes) < gate["min_distinct_ordinal_classes"]:
            reasons.append(f"ordinal_classes {len(ordinal_classes)} < {gate['min_distinct_ordinal_classes']}")
    return {
        "status": "READY_FOR_CALIBRATION_EXPERIMENT" if not reasons else "NOT_READY_BY_POLICY",
        "direct_label_records": len(direct),
        "distinct_games": len(games),
        "distinct_ordinal_classes": ordinal_classes if kind == "grind" else None,
        "blocking_reasons": reasons,
    }


def build_game_index(records, policy):
    out = {}
    for rec in records:
        ident = rec.get("identity") or {}
        gid = str(ident.get("game_id"))
        if not gid or gid == "None":
            continue
        entry = out.setdefault(gid, {
            "title": ident.get("title"),
            "versions": [],
            "sha256": [],
            "label_records": 0,
            "hours_classes": [],
            "grind_classes": [],
            "has_direct_hours": False,
            "has_direct_grind": False,
            "has_any_hours_label": False,
            "has_any_grind_label": False,
        })
        entry["label_records"] += 1
        for key in ("version", "sha256"):
            v = ident.get(key)
            dest = "versions" if key == "version" else "sha256"
            if v and v not in entry[dest]:
                entry[dest].append(v)
        hc = label_class(rec, "hours", policy); gc = label_class(rec, "grind", policy)
        if hc not in entry["hours_classes"]: entry["hours_classes"].append(hc)
        if gc not in entry["grind_classes"]: entry["grind_classes"].append(gc)
        if hc == "DIRECT_TRAINING": entry["has_direct_hours"] = True
        if gc == "DIRECT_TRAINING": entry["has_direct_grind"] = True
        if hc != "UNLABELED": entry["has_any_hours_label"] = True
        if gc != "UNLABELED": entry["has_any_grind_label"] = True
    for entry in out.values():
        entry["hours_classes"].sort(); entry["grind_classes"].sort(); entry["versions"].sort(); entry["sha256"].sort()
    return dict(sorted(out.items()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--schema")
    ap.add_argument("--out", default="fangame_calibration_audit.json")
    args = ap.parse_args()

    policy = load(args.policy)
    schema = load(args.schema) if args.schema else None
    validator = None
    if schema:
        try:
            import jsonschema
        except ImportError:
            raise SystemExit("jsonschema is required when --schema is supplied")
        validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())

    records = []
    invalid = []
    seen_record_ids = set()
    for path in files_under(args.labels):
        try:
            rec = load(path)
        except Exception as e:
            invalid.append({"file": str(path), "errors": [f"invalid JSON: {e}"]})
            continue
        errors = []
        if validator:
            errors.extend(sorted(e.message for e in validator.iter_errors(rec)))
        errors.extend(semantic_errors(rec))
        rid = (rec.get("audit") or {}).get("label_record_id")
        if rid:
            if rid in seen_record_ids:
                errors.append(f"duplicate label_record_id: {rid}")
            seen_record_ids.add(rid)
        if errors:
            invalid.append({"file": str(path), "errors": errors})
        else:
            records.append(rec)

    classes = {kind: collections.Counter(label_class(r, kind, policy) for r in records) for kind in ("hours", "grind")}
    game_ids = {str((r.get("identity") or {}).get("game_id")) for r in records}
    context_counts = collections.Counter(
        (
            (r.get("context") or {}).get("completion_scope"),
            (r.get("context") or {}).get("speedup_used"),
            (r.get("context") or {}).get("cheats_or_debug_used"),
        )
        for r in records
    )

    result = {
        "audit_version": AUDIT_VERSION,
        "rubric_version": policy.get("rubric_version"),
        "valid_records": len(records),
        "invalid_records": len(invalid),
        "distinct_games": len(game_ids),
        "label_classes": {k: dict(v) for k, v in classes.items()},
        "hours_readiness": readiness(records, "hours", policy),
        "grind_readiness": readiness(records, "grind", policy),
        "game_index": build_game_index(records, policy),
        "context_partitions": [
            {"completion_scope": k[0], "speedup_used": k[1], "cheats_or_debug_used": k[2], "records": n}
            for k, n in sorted(context_counts.items(), key=lambda kv: (-kv[1], str(kv[0])))
        ],
        "invalid": invalid,
        "policy_note": policy.get("readiness_note"),
        "training_boundary": "Only DIRECT_TRAINING labels count toward baseline readiness. REFERENCE_ONLY, CONTEXTUAL_ONLY and EXPERIMENTAL records remain preserved and are exposed through game_index without contaminating canonical Feature Store evidence.",
    }
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
