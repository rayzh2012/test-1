#!/usr/bin/env python3
"""Normalize inspectable RPG Maker evidence into fangame.normalized_profile.v0.1.

This adapter is intentionally conservative. It harmonizes fields that mean the
same thing across engine families, preserves UNKNOWN as null, and records the
parser family so later baselines cannot silently mix incompatible evidence.
"""

import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "fangame.normalized_profile.v0.1"
BASELINE_PENDING = "REAL_ORDINARY_RPG_BASELINE_PENDING"


def load(path):
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def first(*vals):
    for v in vals:
        if v is not None and v != "":
            return v
    return None


def n(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        return float(v)
    except Exception:
        return None


def div(a, b):
    a, b = n(a), n(b)
    if a is None or b in (None, 0):
        return None
    return float(a) / float(b)


def median(stat):
    return (stat or {}).get("median") if isinstance(stat, dict) else None


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def target_identity(target):
    sources = target.get("sources") if isinstance(target.get("sources"), list) else []
    return {
        "game_id": first(target.get("game_id"), target.get("id")),
        "title": first(target.get("name"), target.get("title")),
        "version": first(target.get("version"), target.get("release_version")),
        "engine": target.get("engine"),
        "source_url": first(target.get("source_url"), target.get("source"), sources[0] if sources else None),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-json")
    ap.add_argument("--dialogue-corpus")
    ap.add_argument("--map-graph")
    ap.add_argument("--content-inference")
    ap.add_argument("--game-id")
    args = ap.parse_args()

    st = load(args.static)
    target = load(args.target_json)
    dialogue = load(args.dialogue_corpus).get("summary", {}) or {}
    graph = load(args.map_graph).get("summary", {}) or {}
    infer = load(args.content_inference).get("summary", {}) or {}
    mc = st.get("marshal_content") if isinstance(st.get("marshal_content"), dict) else {}
    prog_wrap = st.get("progression_evidence") if isinstance(st.get("progression_evidence"), dict) else {}
    prog = prog_wrap.get("summary") if isinstance(prog_wrap.get("summary"), dict) else {}
    graph_wrap = st.get("graph_evidence") if isinstance(st.get("graph_evidence"), dict) else {}
    graph_probe_summary = graph_wrap.get("summary") if isinstance(graph_wrap.get("summary"), dict) else {}

    pkg = Path(args.package)
    tid = target_identity(target)
    engine = first(st.get("engine"), tid.get("engine"), "UNKNOWN")
    parser_family = "RGSS_MARSHAL" if engine in {"RPG Maker XP", "RPG Maker VX", "RPG Maker VX Ace"} else "STATIC_INSPECT"

    maps = first(mc.get("maps_loaded"), graph.get("map_nodes"), st.get("map_count_verified_by_marshal"), st.get("map_count"))
    events = mc.get("events")
    event_pages = mc.get("event_pages")
    event_commands = mc.get("event_commands")
    dialogue_blocks = dialogue.get("dialogue_blocks")
    dialogue_lines = first(dialogue.get("dialogue_lines"), mc.get("dialogue_lines"))
    dialogue_chars = first(dialogue.get("dialogue_chars"), mc.get("dialogue_chars"))
    choice_options = mc.get("choice_options")
    conditional_branches = first(graph_probe_summary.get("conditional_branch_nodes"), graph.get("conditional_branch_nodes"))
    transfers = first(mc.get("map_transfers"), graph.get("transfer_edges"))

    metrics = {
        "maps": n(maps),
        "events": n(events),
        "event_pages": n(event_pages),
        "event_commands": n(event_commands),
        "dialogue_blocks": n(dialogue_blocks),
        "dialogue_lines": n(dialogue_lines),
        "dialogue_chars": n(dialogue_chars),
        "choice_options": n(choice_options),
        "conditional_branches": n(conditional_branches),
        "transfers": n(transfers),
        "battle_calls": n(mc.get("battle_calls")),
        "shops": n(mc.get("shop_calls")),
        "common_events": n(mc.get("common_events")),
        "actors": n(mc.get("actors")),
        "classes": n(mc.get("classes")),
        "skills": n(mc.get("skills")),
        "items": n(mc.get("items")),
        "weapons": n(mc.get("weapons")),
        "armors": n(mc.get("armors")),
        "enemies": n(mc.get("enemies")),
        "troops": n(mc.get("troops")),
        "states": n(mc.get("states")),
        "image_count": n(st.get("image_count")),
        "audio_count": n(st.get("audio_count")),
    }
    metrics = {k: v for k, v in metrics.items() if v is not None}

    m_maps = metrics.get("maps")
    derived = {
        "events_per_map": div(metrics.get("events"), m_maps),
        "event_commands_per_map": div(metrics.get("event_commands"), m_maps),
        "dialogue_chars_per_map": div(metrics.get("dialogue_chars"), m_maps),
        "dialogue_chars_per_event": div(metrics.get("dialogue_chars"), metrics.get("events")),
        "choice_options_per_map": div(metrics.get("choice_options"), m_maps),
        "conditional_branches_per_map": div(metrics.get("conditional_branches"), m_maps),
        "transfers_per_map": div(metrics.get("transfers"), m_maps),
        "battle_calls_per_map": div(metrics.get("battle_calls"), m_maps),
        "shops_per_100_maps": (div(metrics.get("shops"), m_maps) * 100.0) if div(metrics.get("shops"), m_maps) is not None else None,
    }
    derived = {k: v for k, v in derived.items() if v is not None}

    progression = {
        "random_encounter_map_ratio": prog.get("random_encounter_map_ratio"),
        "encounter_step_median": median(prog.get("encounter_step_stats")),
        "enemy_exp_median": median(prog.get("enemy_exp_stats")),
        "enemy_gold_median": median(prog.get("enemy_gold_stats")),
        "equipment_price_median": median(prog.get("equipment_price_stats")),
    }

    profile = {
        "schema": SCHEMA,
        "parser_family": parser_family,
        "game_id": first(args.game_id, tid.get("game_id"), f"sha256:{sha256_file(pkg)}"),
        "title": first(tid.get("title"), pkg.stem),
        "version": tid.get("version"),
        "engine": engine,
        "sha256": sha256_file(pkg),
        "bytes": pkg.stat().st_size,
        "source_url": tid.get("source_url"),
        "metrics": metrics,
        "derived": derived,
        "progression": progression,
        "system_evidence": {
            "rgss_marshal_probe": bool(mc.get("marshal_probe")),
            "graph_probe": bool(graph_wrap.get("graph_probe")),
            "progression_probe": bool(prog_wrap.get("progression_probe")),
            "content_inference": bool(infer),
        },
        "baseline_status": BASELINE_PENDING,
        "analysis_evidence": {
            "sidequest_candidate_maps": infer.get("sidequest_candidate_maps"),
            "explicit_sidequest_maps": infer.get("explicit_sidequest_maps"),
            "optional_content_maps": infer.get("optional_content_maps"),
            "ending_candidate_maps": infer.get("ending_candidate_maps"),
            "release_completion_status": infer.get("release_completion_status"),
        },
        "limitations": [
            "Legacy RGSS values come from inspectable Marshal data and graph/progression probes; custom scripts may add runtime behavior not visible to static event counts.",
            "Cross-engine percentile claims remain disabled until metric semantics are calibrated across parser families with a real ordinary-RPG corpus.",
        ],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "parser_family": parser_family, "game_id": profile["game_id"], "metrics": metrics, "baseline_status": BASELINE_PENDING}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
