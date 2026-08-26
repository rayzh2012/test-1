#!/usr/bin/env python3
import argparse
import csv
import json
import math
from pathlib import Path

ENGINE_VERSION = "evidence.next.action.v0.8"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_records(path):
    p = Path(path)
    if p.suffix.lower() in {".ndjson", ".jsonl"}:
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    obj = load(p)
    return obj if isinstance(obj, list) else [obj]


def nested(obj, path):
    cur = obj
    for key in path.split(".") if path else []:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def number(v):
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def condition_match(ctx, cond):
    val = nested(ctx, cond.get("path", ""))
    op = cond.get("op", "missing")
    target = cond.get("value")
    if op == "missing":
        return val is None
    if op == "present":
        return val is not None
    if op == "equals":
        return val == target
    if op == "not_equals":
        return val != target
    if op == "in":
        return val in (cond.get("values") or [])
    if op == "not_in":
        return val not in (cond.get("values") or [])
    if op == "truthy":
        return bool(val)
    if op == "falsy":
        return not bool(val)
    x = number(val); y = number(target)
    if x is None or y is None:
        return False
    if op == "lt": return x < y
    if op == "lte": return x <= y
    if op == "gt": return x > y
    if op == "gte": return x >= y
    raise ValueError(f"unknown condition op: {op}")


def compare_index(compare):
    if not isinstance(compare, dict):
        return {}
    return {str(x.get("id")): x for x in compare.get("objects", []) if x.get("id") is not None}


def aux_index(aux):
    if not isinstance(aux, dict):
        return {}
    if isinstance(aux.get("game_index"), dict):
        return {str(k): v for k, v in aux["game_index"].items()}
    if isinstance(aux.get("objects"), list):
        return {str(x.get("id")): x for x in aux["objects"] if x.get("id") is not None}
    return {}


def identity(rec, policy, idx):
    oid = nested(rec, policy.get("identity_path", "identity.game_id"))
    label = nested(rec, policy.get("label_path", "identity.title"))
    oid = str(oid) if oid not in (None, "") else f"record:{idx+1}"
    label = str(label) if label not in (None, "") else oid
    return oid, label


def novelty(compare_obj):
    if not compare_obj:
        return 0.5
    peers = compare_obj.get("nearest_neighbors") or []
    nearest = number(peers[0].get("similarity")) if peers else None
    peer_novelty = 1.0 if nearest is None else max(0.0, min(1.0, 1.0 - nearest))
    anom = number(compare_obj.get("anomaly_score"))
    anomaly_novelty = 0.5 if anom is None else math.tanh(max(0.0, anom) / 2.0)
    return 0.5 * peer_novelty + 0.5 * anomaly_novelty


def decision_importance(compare_obj):
    if not compare_obj:
        return 0.5
    ranking = compare_obj.get("ranking") if isinstance(compare_obj.get("ranking"), dict) else {}
    score = number(ranking.get("score_5")); coverage = number(ranking.get("coverage"))
    score01 = 0.5 if score is None else max(0.0, min(1.0, score / 5.0))
    cov01 = 0.5 if coverage is None else max(0.0, min(1.0, coverage))
    return 0.8 * score01 + 0.2 * cov01


def feature_gap(compare_obj):
    if not compare_obj:
        return 0.5
    cov = number(compare_obj.get("feature_coverage"))
    return 0.5 if cov is None else max(0.0, min(1.0, 1.0 - cov))


def cluster_leverage(compare_obj, cluster_sizes, max_cluster):
    if not compare_obj or max_cluster <= 0:
        return 0.5
    cid = compare_obj.get("cluster_id")
    return max(0.0, min(1.0, cluster_sizes.get(cid, 1) / max_cluster))


def uncertainty(ctx, action):
    terms = action.get("when") or []
    if not terms:
        return 1.0, []
    total = sum(max(0.0, float(t.get("weight", 1.0))) for t in terms)
    matched_weight = 0.0; reasons = []
    for t in terms:
        w = max(0.0, float(t.get("weight", 1.0)))
        ok = condition_match(ctx, t)
        if ok:
            matched_weight += w
            reasons.append({"path": t.get("path"), "op": t.get("op", "missing"), "value": t.get("value"), "weight": w, "reason": t.get("reason")})
    score = matched_weight / total if total else 0.0
    min_match = float(action.get("min_uncertainty", 0.000001))
    return (score if score >= min_match else 0.0), reasons


def prerequisites_ok(ctx, action):
    return all(condition_match(ctx, c) for c in (action.get("requires") or []))


def score_action(ctx, action, compare_obj, cluster_sizes, max_cluster):
    u, reasons = uncertainty(ctx, action)
    if u <= 0 or not prerequisites_ok(ctx, action):
        return None
    comps = {
        "uncertainty": u,
        "novelty": novelty(compare_obj),
        "decision_importance": decision_importance(compare_obj),
        "feature_gap": feature_gap(compare_obj),
        "peer_leverage": cluster_leverage(compare_obj, cluster_sizes, max_cluster),
    }
    weights = action.get("component_weights") or {"uncertainty": 0.5, "novelty": 0.2, "decision_importance": 0.2, "feature_gap": 0.1}
    numerator = 0.0; denom = 0.0; contributions = []
    for name, w0 in weights.items():
        w = max(0.0, float(w0)); v = comps.get(name)
        if v is None or w <= 0:
            continue
        numerator += w * v; denom += w
        contributions.append({"component": name, "value_0_1": round(v, 4), "weight": w, "weighted": round(w*v, 4)})
    base = numerator / denom if denom else 0.0
    cost = max(0.05, float(action.get("cost_units", 1.0)))
    cost_penalty = math.sqrt(cost)
    priority = max(0.0, min(5.0, 5.0 * base / cost_penalty))
    return {
        "action_id": action["action_id"],
        "action_label": action.get("label", action["action_id"]),
        "priority_proxy_5": round(priority, 4),
        "cost_units": cost,
        "cost_penalty": round(cost_penalty, 4),
        "components": sorted(contributions, key=lambda x: (-x["weighted"], x["component"])),
        "matched_uncertainty_reasons": reasons,
        "execution_hint": action.get("execution_hint"),
        "note": action.get("note"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--compare")
    ap.add_argument("--aux")
    ap.add_argument("--out-json", default="next_actions.json")
    ap.add_argument("--out-csv", default="next_actions.csv")
    args = ap.parse_args()

    records = read_records(args.records)
    policy = load(args.policy)
    compare = load(args.compare) if args.compare and Path(args.compare).exists() else {}
    aux = load(args.aux) if args.aux and Path(args.aux).exists() else {}
    cidx = compare_index(compare); aidx = aux_index(aux)
    cluster_sizes = {}
    for x in cidx.values():
        cid = x.get("cluster_id")
        cluster_sizes[cid] = cluster_sizes.get(cid, 0) + 1
    max_cluster = max(cluster_sizes.values()) if cluster_sizes else 0

    candidates = []
    for i, rec in enumerate(records):
        oid, label = identity(rec, policy, i)
        comp = cidx.get(oid, {})
        aux_obj = aidx.get(oid, {})
        ctx = {"record": rec, "compare": comp, "aux": aux_obj}
        for action in policy.get("actions", []):
            scored = score_action(ctx, action, comp, cluster_sizes, max_cluster)
            if not scored:
                continue
            candidates.append({"object_id": oid, "object_label": label, "cluster_id": comp.get("cluster_id"), **scored})

    candidates.sort(key=lambda x: (-x["priority_proxy_5"], x["cost_units"], x["object_id"], x["action_id"]))
    for rank, x in enumerate(candidates, 1):
        x["rank"] = rank

    result = {
        "engine_version": ENGINE_VERSION,
        "policy_version": policy.get("policy_version"),
        "score_semantics": "Expected information value proxy, not calibrated Bayesian information gain. Every score is policy-driven and decomposed into visible components.",
        "record_count": len(records),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    Path(args.out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = ["rank", "object_id", "object_label", "action_id", "action_label", "priority_proxy_5", "cost_units", "cluster_id", "execution_hint"]
    with Path(args.out_csv).open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader()
        for x in candidates:
            w.writerow({k: x.get(k) for k in fields})
    print(json.dumps({"records": len(records), "candidates": len(candidates), "policy": policy.get("policy_version"), "status": "OK"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
