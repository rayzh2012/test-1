#!/usr/bin/env python3
import argparse
import csv
import glob
import json
import math
import statistics
from pathlib import Path

ENGINE_VERSION = "evidence.feature.compare.v0.6"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def nested(obj, path):
    cur = obj
    for key in path.split(".") if path else []:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def number(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def transform(v, kind):
    x = number(v)
    if x is None:
        return None
    if kind == "log1p":
        return math.log1p(max(0.0, x))
    if kind == "sqrt":
        return math.sqrt(max(0.0, x))
    if kind == "binary":
        return 1.0 if x else 0.0
    return x


def percentile_rank(values, x):
    vals = sorted(v for v in values if v is not None)
    if not vals or x is None:
        return None
    if len(vals) == 1:
        return 0.5
    below = sum(v < x for v in vals)
    equal = sum(v == x for v in vals)
    return (below + 0.5 * equal) / len(vals)


def robust_stats(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return {"median": None, "scale": None, "count": 0}
    med = statistics.median(vals)
    absdev = [abs(v - med) for v in vals]
    mad = statistics.median(absdev)
    if mad > 0:
        scale = 1.4826 * mad
    else:
        spread = max(vals) - min(vals)
        scale = spread / 2.0 if spread > 0 else 1.0
    return {"median": med, "scale": scale or 1.0, "count": len(vals)}


def read_records(path):
    p = Path(path)
    if p.is_file() and p.suffix.lower() in {".ndjson", ".jsonl"}:
        return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    if p.is_file():
        obj = load_json(p)
        if isinstance(obj, list):
            return obj
        return [obj]
    files = sorted(glob.glob(str(p / "**" / "fangame_features.json"), recursive=True))
    if not files:
        files = sorted(glob.glob(str(p / "**" / "*.features.json"), recursive=True))
    return [load_json(f) for f in files]


def identity(record, policy, idx):
    oid = nested(record, policy.get("identity_path", "identity.game_id"))
    label = nested(record, policy.get("label_path", "identity.title"))
    oid = str(oid) if oid not in (None, "") else f"record:{idx+1}"
    label = str(label) if label not in (None, "") else oid
    return oid, label


def make_matrix(records, features):
    raw = []
    stats = {}
    for rec in records:
        row = {}
        for f in features:
            row[f["path"]] = transform(nested(rec, f["path"]), f.get("transform", "identity"))
        raw.append(row)
    for f in features:
        path = f["path"]
        stats[path] = robust_stats([r[path] for r in raw])
    zrows = []
    for row in raw:
        z = {}
        for f in features:
            path = f["path"]
            v = row[path]
            s = stats[path]
            z[path] = None if v is None or s["median"] is None else max(-6.0, min(6.0, (v - s["median"]) / s["scale"]))
        zrows.append(z)
    return raw, zrows, stats


def pair_similarity(i, j, features, zrows):
    terms = []
    details = []
    total_policy_weight = sum(max(0.0, float(f.get("weight", 1.0))) for f in features)
    common_weight = 0.0
    for f in features:
        path = f["path"]
        a, b = zrows[i][path], zrows[j][path]
        w = max(0.0, float(f.get("weight", 1.0)))
        if a is None or b is None or w <= 0:
            continue
        d = abs(a - b)
        terms.append(w * d * d)
        common_weight += w
        details.append((d, path, a, b, w))
    if common_weight <= 0:
        return None
    distance = math.sqrt(sum(terms) / common_weight)
    similarity = 1.0 / (1.0 + distance)
    coverage = common_weight / total_policy_weight if total_policy_weight else 0.0
    similar = sorted(details, key=lambda x: (x[0], x[1]))[:4]
    different = sorted(details, key=lambda x: (-x[0], x[1]))[:4]
    return {
        "similarity": round(similarity, 6),
        "distance": round(distance, 6),
        "coverage": round(coverage, 4),
        "similar_reasons": [{"path": p, "z_gap": round(d, 4)} for d, p, _, _, _ in similar],
        "different_reasons": [{"path": p, "z_gap": round(d, 4)} for d, p, _, _, _ in different],
    }


def rank_record(record, records, ranking_rules):
    contributions = []
    weighted = 0.0
    used = 0.0
    total = sum(max(0.0, float(r.get("weight", 1.0))) for r in ranking_rules)
    for rule in ranking_rules:
        path = rule["path"]
        w = max(0.0, float(rule.get("weight", 1.0)))
        x = number(nested(record, path))
        if x is None or w <= 0:
            continue
        mode = rule.get("mode", "fixed")
        if mode == "percentile":
            vals = [number(nested(r, path)) for r in records]
            q = percentile_rank(vals, x)
            if q is None:
                continue
            score = 5.0 * q
        else:
            lo = float(rule.get("min", 0.0)); hi = float(rule.get("max", 5.0))
            if hi <= lo:
                continue
            score = 5.0 * max(0.0, min(1.0, (x - lo) / (hi - lo)))
        if rule.get("direction", "higher_better") == "lower_better":
            score = 5.0 - score
        weighted += w * score
        used += w
        contributions.append({"path": path, "raw": x, "score_5": round(score, 4), "weight": w, "weighted": round(w * score, 4)})
    return {
        "score_5": round(weighted / used, 4) if used else None,
        "coverage": round(used / total, 4) if total else 0.0,
        "contributions": sorted(contributions, key=lambda x: (-x["weighted"], x["path"])),
    }


def anomaly_score(zrow, features):
    vals = []
    for f in features:
        z = zrow.get(f["path"])
        w = max(0.0, float(f.get("weight", 1.0)))
        if z is not None and w > 0:
            vals.append((abs(z), w))
    if not vals:
        return None
    return round(sum(z * w for z, w in vals) / sum(w for _, w in vals), 6)


def components(n, pair_lookup, threshold, min_coverage):
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    for (i, j), p in pair_lookup.items():
        if p and p["similarity"] >= threshold and p["coverage"] >= min_coverage:
            union(i, j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    ordered = sorted(groups.values(), key=lambda g: (-len(g), min(g)))
    cluster_of = {}
    for idx, group in enumerate(ordered, 1):
        for i in group:
            cluster_of[i] = f"cluster:{idx:03d}"
    return cluster_of, ordered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out-json", default="feature_compare.json")
    ap.add_argument("--out-csv", default="feature_compare.csv")
    args = ap.parse_args()

    records = read_records(args.records)
    policy = load_json(args.policy)
    features = policy.get("similarity_features", [])
    ranking_rules = policy.get("ranking_rules", [])
    if not records:
        raise SystemExit("no records")
    if not features:
        raise SystemExit("policy has no similarity_features")

    ids = [identity(r, policy, i) for i, r in enumerate(records)]
    raw, zrows, stats = make_matrix(records, features)
    pairs = {}
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            pairs[(i, j)] = pair_similarity(i, j, features, zrows)

    cluster_cfg = policy.get("clustering", {})
    threshold = float(cluster_cfg.get("similarity_threshold", 0.65))
    min_cov = float(cluster_cfg.get("min_pair_coverage", 0.5))
    cluster_of, groups = components(len(records), pairs, threshold, min_cov)
    k = int(policy.get("nearest_neighbors", 5))

    objects = []
    for i, rec in enumerate(records):
        neighbors = []
        for j in range(len(records)):
            if i == j:
                continue
            key = (i, j) if i < j else (j, i)
            p = pairs.get(key)
            if not p:
                continue
            neighbors.append({"id": ids[j][0], "label": ids[j][1], **p})
        neighbors.sort(key=lambda x: (-x["similarity"], -x["coverage"], x["id"]))
        objects.append({
            "id": ids[i][0],
            "label": ids[i][1],
            "cluster_id": cluster_of[i],
            "anomaly_score": anomaly_score(zrows[i], features),
            "ranking": rank_record(rec, records, ranking_rules),
            "nearest_neighbors": neighbors[:k],
            "feature_coverage": round(sum(zrows[i][f["path"]] is not None for f in features) / len(features), 4),
        })

    ranked = sorted(objects, key=lambda x: (-(x["ranking"]["score_5"] if x["ranking"]["score_5"] is not None else -1), -x["ranking"]["coverage"], x["id"]))
    for pos, obj in enumerate(ranked, 1):
        obj["rank"] = pos

    result = {
        "engine_version": ENGINE_VERSION,
        "policy_version": policy.get("policy_version"),
        "record_count": len(records),
        "feature_count": len(features),
        "cluster_count": len(groups),
        "clustering": {"similarity_threshold": threshold, "min_pair_coverage": min_cov},
        "feature_stats": stats,
        "objects": sorted(objects, key=lambda x: x["rank"]),
        "policy_note": policy.get("note"),
    }
    Path(args.out_json).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = ["rank", "id", "label", "cluster_id", "ranking_score_5", "ranking_coverage", "anomaly_score", "feature_coverage", "nearest_peer", "nearest_similarity", "nearest_coverage"]
    with Path(args.out_csv).open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields); w.writeheader()
        for obj in sorted(objects, key=lambda x: x["rank"]):
            peer = obj["nearest_neighbors"][0] if obj["nearest_neighbors"] else {}
            w.writerow({
                "rank": obj["rank"], "id": obj["id"], "label": obj["label"], "cluster_id": obj["cluster_id"],
                "ranking_score_5": obj["ranking"]["score_5"], "ranking_coverage": obj["ranking"]["coverage"],
                "anomaly_score": obj["anomaly_score"], "feature_coverage": obj["feature_coverage"],
                "nearest_peer": peer.get("label"), "nearest_similarity": peer.get("similarity"), "nearest_coverage": peer.get("coverage"),
            })
    print(json.dumps({"records": len(records), "clusters": len(groups), "policy": policy.get("policy_version"), "status": "OK"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
