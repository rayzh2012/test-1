#!/usr/bin/env python3
import argparse
import collections
import json
import re
from pathlib import Path

INFERENCE_VERSION = "fangame.graph.inference.v0.4.1"

TASK_TEXT = re.compile(
    r"(支线|支線|任务|任務|委托|委託|请求|請求|帮忙|幫忙|帮助|幫助|接受|接下|完成|交付|"
    r"悬赏|懸賞|讨伐|討伐|寻找|尋找|收集|护送|護送|"
    r"\bquest\b|\bmission\b|\brequest\b|\bhelp\b|\baccept\b|\bcomplete\b|\bdeliver\b|\bhunt\b|\bcollect\b|\bescort\b)",
    re.I,
)
REWARD_TEXT = re.compile(
    r"(奖励|獎勵|报酬|報酬|获得|獲得|得到|金币|金幣|经验|經驗|"
    r"\breward\b|\breceive\b|\bobtained\b|\bgain(?:ed)?\b|\bearned\b|\bexp\b|\bgold\b)",
    re.I,
)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def confidence(score):
    if score >= 5.0:
        return "HIGH"
    if score >= 3.5:
        return "MEDIUM"
    return "LOW"


def bfs(start, adj):
    if start is None:
        return {}
    dist = {start: 0}
    q = collections.deque([start])
    while q:
        cur = q.popleft()
        for nxt in adj.get(cur, ()):
            if nxt not in dist:
                dist[nxt] = dist[cur] + 1
                q.append(nxt)
    return dist


def node_maps(graph):
    out = {}
    for page in graph.get("event_pages", []):
        nid = page.get("node_id")
        if nid:
            out[nid] = page.get("map_id")
    for ce in graph.get("common_events", []):
        nid = ce.get("node_id")
        if nid:
            out[nid] = None
    return out


def event_page_lookup(graph):
    return {x.get("node_id"): x for x in graph.get("event_pages", []) if x.get("node_id")}


def common_event_lookup(graph):
    return {x.get("node_id"): x for x in graph.get("common_events", []) if x.get("node_id")}


def node_set(items):
    return {x.get("node_id") for x in items if x.get("node_id")}


def state_key(edge):
    t = edge.get("state_type")
    sid = edge.get("state_id")
    if t not in {"switch", "variable"} or sid is None:
        return None
    return f"{t}:{sid}"


def text_by_node(graph):
    out = collections.defaultdict(list)
    for row in list(graph.get("event_pages", [])) + list(graph.get("common_events", [])):
        nid = row.get("node_id")
        if not nid:
            continue
        for text in row.get("dialogue_samples", []) or []:
            if isinstance(text, str) and text.strip():
                out[nid].append(text.strip())
    for row in graph.get("choice_nodes", []):
        nid = row.get("node_id")
        if not nid:
            continue
        for text in row.get("options", []) or []:
            if isinstance(text, str) and text.strip():
                out[nid].append(text.strip())
    return out


def build_optional_clusters(graph):
    reads = graph.get("state_reads", [])
    writes = graph.get("state_writes", [])
    page_lookup = event_page_lookup(graph)
    start_map = (graph.get("system") or {}).get("start_map_id")

    by_state = collections.defaultdict(lambda: {"reads": set(), "writes": set(), "maps": set()})
    for e in reads:
        key = state_key(e)
        if not key:
            continue
        nid = e.get("node_id")
        if nid:
            by_state[key]["reads"].add(nid)
        if e.get("map_id") is not None:
            by_state[key]["maps"].add(e.get("map_id"))
    for e in writes:
        key = state_key(e)
        if not key:
            continue
        nid = e.get("node_id")
        if nid:
            by_state[key]["writes"].add(nid)
        if e.get("map_id") is not None:
            by_state[key]["maps"].add(e.get("map_id"))

    eligible = {
        key: info for key, info in by_state.items()
        if info["reads"] and info["writes"] and 0 < len(info["maps"]) <= 4
    }

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    state_nodes = {}
    for key, info in eligible.items():
        nodes = set(info["reads"]) | set(info["writes"])
        state_nodes[key] = nodes
        ordered = sorted(nodes)
        for n in ordered:
            find(n)
        for n in ordered[1:]:
            union(ordered[0], n)

    groups = collections.defaultdict(set)
    for key, nodes in state_nodes.items():
        for n in nodes:
            groups[find(n)].add(key)
            break

    choices = node_set(graph.get("choice_nodes", []))
    battles = node_set(graph.get("battle_nodes", []))
    shops = node_set(graph.get("shop_nodes", []))
    terminal_nodes = node_set(graph.get("terminal_signals", []))
    common_calls = node_set(graph.get("common_event_edges", []))
    text_map = text_by_node(graph)

    candidates = []
    for idx, (_, states) in enumerate(sorted(groups.items(), key=lambda kv: sorted(kv[1])[0]), 1):
        nodes = set()
        maps = set()
        for key in states:
            nodes |= state_nodes[key]
            maps |= eligible[key]["maps"]

        score = 2.0
        reasons = ["LOCAL_STATE_READ_WRITE_LOOP"]
        if len(states) >= 2:
            score += min(1.5, 0.5 * (len(states) - 1))
            reasons.append("MULTI_STATE_CLUSTER")
        if 2 <= len(nodes) <= 6:
            score += 1.0
            reasons.append("MULTI_EVENT_CLUSTER")
        elif len(nodes) > 10:
            score -= 1.0
            reasons.append("LARGE_CLUSTER_MAINLINE_RISK")
        if 1 <= len(maps) <= 3:
            score += 0.75
            reasons.append("MAP_LOCALITY")
        if nodes & choices:
            score += 0.8
            reasons.append("HAS_PLAYER_CHOICE")
        if nodes & battles:
            score += 0.8
            reasons.append("HAS_BATTLE_GATE")
        if nodes & shops:
            score += 0.3
            reasons.append("HAS_SHOP_INTERACTION")
        if nodes & common_calls:
            score += 0.4
            reasons.append("USES_COMMON_EVENT")

        dialogue = sum((page_lookup.get(n) or {}).get("dialogue_lines", 0) or 0 for n in nodes)
        if dialogue >= 3:
            score += 0.5
            reasons.append("HAS_DIALOGUE_PAYLOAD")
        if nodes & terminal_nodes:
            score -= 2.0
            reasons.append("TERMINAL_OVERLAP_PENALTY")
        if start_map in maps and not (nodes & choices or nodes & battles):
            score -= 0.75
            reasons.append("START_MAP_TUTORIAL_RISK")

        if score < 3.0:
            continue

        samples = []
        for nid in sorted(nodes):
            for text in text_map.get(nid, []):
                if text not in samples:
                    samples.append(text)
                if len(samples) >= 12:
                    break
            if len(samples) >= 12:
                break

        candidates.append({
            "candidate_id": f"optional:{idx}",
            "score": round(score, 2),
            "confidence": confidence(score),
            "maps": sorted(maps),
            "state_keys": sorted(states),
            "evidence_node_ids": sorted(nodes),
            "reason_codes": reasons,
            "dialogue_lines_in_cluster": dialogue,
            "semantic_text_samples": samples,
            "evidence_summary": (
                f"Optional-state cluster across {len(maps)} map(s), {len(nodes)} event/common-event node(s), "
                f"{len(states)} state key(s)."
            ),
        })

    overall = "UNKNOWN"
    if candidates:
        overall = confidence(sum(x["score"] for x in candidates) / len(candidates))
    return {
        "candidate_count": len(candidates),
        "confidence": overall,
        "candidates": candidates,
        "method": (
            "Local switch/variable read-write clusters plus interaction evidence. These are optional-content/state-machine "
            "candidates only and must not be reported as quest counts."
        ),
    }


def infer_sidequests(graph, optional_clusters):
    reward_nodes = node_set(graph.get("reward_nodes", []))
    candidates = []

    for idx, opt in enumerate(optional_clusters.get("candidates", []), 1):
        nodes = set(opt.get("evidence_node_ids") or [])
        samples = opt.get("semantic_text_samples") or []
        task_hits = [x for x in samples if TASK_TEXT.search(x)]
        reward_hits = [x for x in samples if REWARD_TEXT.search(x)]
        observed_reward = bool(nodes & reward_nodes)

        # Conservative semantic promotion: topology alone proves optional structure, not a quest.
        if not task_hits and not reward_hits and not observed_reward:
            continue

        score = min(2.5, float(opt.get("score") or 0) * 0.35)
        reasons = ["PROMOTED_FROM_OPTIONAL_CLUSTER"]
        if task_hits:
            score += 2.25
            reasons.append("TASK_TEXT_SIGNAL")
        if reward_hits:
            score += 1.75
            reasons.append("REWARD_TEXT_SIGNAL")
        if observed_reward:
            score += 2.5
            reasons.append("OBSERVED_REWARD_COMMAND")
        if len(opt.get("state_keys") or []) >= 2 and len(nodes) >= 2:
            score += 0.75
            reasons.append("MULTI_STAGE_STATE_PROGRESS")
        if "HAS_PLAYER_CHOICE" in (opt.get("reason_codes") or []):
            score += 0.25
            reasons.append("PLAYER_ACCEPT_REJECT_SHAPE")
        if "HAS_BATTLE_GATE" in (opt.get("reason_codes") or []):
            score += 0.25
            reasons.append("COMBAT_OBJECTIVE_SHAPE")

        semantic_samples = []
        for x in task_hits + reward_hits:
            if x not in semantic_samples:
                semantic_samples.append(x)

        candidates.append({
            "candidate_id": f"sidequest:{idx}",
            "score": round(score, 2),
            "confidence": confidence(score),
            "maps": opt.get("maps") or [],
            "state_keys": opt.get("state_keys") or [],
            "evidence_node_ids": opt.get("evidence_node_ids") or [],
            "reason_codes": reasons,
            "semantic_signal_samples": semantic_samples[:8],
            "source_optional_candidate_id": opt.get("candidate_id"),
            "evidence_summary": (
                "Optional structural cluster promoted to sidequest candidate only after task/reward semantic evidence."
            ),
        })

    overall = "UNKNOWN"
    if candidates:
        overall = confidence(sum(x["score"] for x in candidates) / len(candidates))
    elif optional_clusters.get("candidate_count"):
        overall = "LOW"

    return {
        "candidate_count": len(candidates),
        "confidence": overall,
        "candidates": candidates,
        "unpromoted_optional_cluster_count": max(
            0, int(optional_clusters.get("candidate_count") or 0) - len(candidates)
        ),
        "method": (
            "Conservative promotion from optional structural clusters. A cluster is not called a sidequest candidate unless "
            "task/reward text or an observed reward command is present."
        ),
    }


def infer_endings(graph):
    signals = graph.get("terminal_signals", [])
    page_lookup = event_page_lookup(graph)
    start_map = (graph.get("system") or {}).get("start_map_id")

    adj = collections.defaultdict(set)
    for e in graph.get("map_edges", []):
        if e.get("target_mode") != "direct":
            continue
        a, b = e.get("source_map_id"), e.get("target_map_id")
        if a is not None and b is not None:
            adj[a].add(b)
    reachable = bfs(start_map, adj)

    accepted_types = {"return_to_title", "terminal_text_signal"}
    grouped = collections.defaultdict(list)
    for s in signals:
        if s.get("type") in accepted_types:
            nid = s.get("node_id") or f"signal:{len(grouped)+1}"
            grouped[nid].append(s)

    state_reads = collections.defaultdict(list)
    for e in graph.get("state_reads", []):
        if e.get("node_id"):
            state_reads[e["node_id"]].append(e)

    candidates = []
    for idx, (nid, sigs) in enumerate(sorted(grouped.items()), 1):
        types = {s.get("type") for s in sigs}
        score = 0.0
        reasons = []
        if "return_to_title" in types:
            score += 3.0
            reasons.append("RETURN_TO_TITLE")
        if "terminal_text_signal" in types:
            score += 2.0
            reasons.append("TERMINAL_TEXT")
        if len(types) >= 2:
            score += 1.0
            reasons.append("MULTI_SIGNAL_AGREEMENT")

        reads = [e for e in state_reads.get(nid, []) if e.get("state_type") in {"switch", "variable", "self_switch"}]
        if reads:
            score += 0.75
            reasons.append("CONDITIONAL_TERMINAL_PATH")

        source_map = next((s.get("map_id") for s in sigs if s.get("map_id") is not None), None)
        if source_map is not None and source_map in reachable:
            score += 0.5
            reasons.append("REACHABLE_FROM_START")

        page = page_lookup.get(nid) or {}
        condition = page.get("conditions") or {}
        condition_signature = {
            "switches": condition.get("switches", []),
            "variables": condition.get("variables", []),
            "self_switches": condition.get("self_switches", []),
        }

        if score < 2.0:
            continue
        candidates.append({
            "candidate_id": f"ending:{idx}",
            "score": round(score, 2),
            "confidence": confidence(score),
            "source_node_id": nid,
            "source_map_id": source_map,
            "signal_types": sorted(types),
            "condition_signature": condition_signature,
            "evidence_node_ids": [nid],
            "reason_codes": reasons,
            "terminal_text_samples": [s.get("text") for s in sigs if s.get("text")][:5],
            "evidence_summary": f"Terminal candidate with {', '.join(sorted(types))}; score {score:.2f}.",
        })

    overall = "UNKNOWN"
    if candidates:
        overall = confidence(sum(c["score"] for c in candidates) / len(candidates))
    return {
        "candidate_count": len(candidates),
        "distinct_terminal_cluster_count": len(candidates),
        "confidence": overall,
        "candidates": candidates,
        "method": (
            "Strong terminal signals (return-to-title and/or terminal text), with conditional and reachability evidence. "
            "Game-over and exit-event alone are excluded."
        ),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", required=True)
    ap.add_argument("--out", default="fangame_inference.json")
    args = ap.parse_args()

    graph = load(args.graph)
    warnings = []
    if not graph.get("summary"):
        warnings.append("GRAPH_SUMMARY_MISSING")
    if (graph.get("summary") or {}).get("load_error_count", 0):
        warnings.append("GRAPH_LOAD_ERRORS_PRESENT")
    if not any((x.get("dialogue_samples") or []) for x in graph.get("event_pages", [])):
        warnings.append("SIDEQUEST_SEMANTIC_TEXT_SPARSE")

    optional = build_optional_clusters(graph)
    sidequests = infer_sidequests(graph, optional)
    endings = infer_endings(graph)

    out = {
        "inference_version": INFERENCE_VERSION,
        "source_graph_version": graph.get("graph_version"),
        "optional_clusters": optional,
        "sidequests": sidequests,
        "endings": endings,
        "warnings": warnings,
        "evidence_policy": {
            "optional_cluster": "structural candidate from local state/read-write topology",
            "sidequest_candidate": "optional cluster plus semantic task/reward evidence",
            "ending_candidate": "strong terminal signal cluster; not official ending count",
        },
        "disclaimer": (
            "All counts are conservative structural/semantic candidates inferred from RPG Maker graph evidence, not official "
            "quest/ending counts and not claims of completed playthrough."
        ),
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
