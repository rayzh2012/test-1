#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path

EMITTER_VERSION = "0.2.0"
SCHEMA_VERSION = "fangame.features.v0.2"


def load_json(path):
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def first(*vals):
    for v in vals:
        if v is not None and v != "":
            return v
    return None


def num(v):
    if v is None:
        return None
    try:
        return int(v)
    except Exception:
        try:
            return float(v)
        except Exception:
            return None


def safe_div(a, b, scale=1.0):
    a = num(a)
    b = num(b)
    if a is None or b in (None, 0):
        return None
    return round((float(a) / float(b)) * scale, 4)


def parse_sha256(path):
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    text = p.read_text(encoding="utf-8", errors="ignore")
    for token in text.replace("*", " ").split():
        t = token.strip().lower()
        if len(t) == 64 and all(c in "0123456789abcdef" for c in t):
            return t
    return None


def infer_package_size(fetch, fetch_path):
    for k in ("bytes", "size", "file_size", "downloaded_bytes", "content_length"):
        v = num(fetch.get(k))
        if isinstance(v, (int, float)):
            return int(v)
    filename = fetch.get("file")
    if filename and fetch_path:
        p = Path(fetch_path).resolve().parent / filename
        if p.exists():
            return p.stat().st_size
    return None


def choose_mc(static):
    mc = static.get("marshal_content")
    return mc if isinstance(mc, dict) else {}


def mc_value(mc, static, mc_keys, static_keys=()):
    for key in mc_keys:
        if key in mc and mc.get(key) is not None:
            return num(mc.get(key))
    for key in static_keys:
        if key in static and static.get(key) is not None:
            return num(static.get(key))
    return None


def bool_or_none(v):
    if isinstance(v, bool):
        return v
    return None


def runtime_semantic_defaults(smoke):
    # Mechanical smoke is deliberately not promoted to semantic gameplay claims.
    status = smoke.get("status")
    input_verified = True if status == "INPUT_FLOW_VERIFIED" else None
    return {
        "title_verified": None,
        "new_game_verified": None,
        "input_flow_verified": input_verified,
        "map_gameplay_verified": None,
        "semantic_review_state": "PENDING_SCREENSHOT_SEMANTIC_REVIEW" if smoke else "NOT_RUN",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", required=True)
    ap.add_argument("--static")
    ap.add_argument("--smoke")
    ap.add_argument("--review")
    ap.add_argument("--target")
    ap.add_argument("--sha256")
    ap.add_argument("--out", default="fangame_features.json")
    args = ap.parse_args()

    fetch = load_json(args.fetch)
    static = load_json(args.static)
    smoke = load_json(args.smoke)
    review = load_json(args.review)
    target = load_json(args.target)
    mc = choose_mc(static)

    archive_filename = first(fetch.get("file"), static.get("archive"))
    title = first(target.get("name"), target.get("title"), review.get("name"), archive_filename)
    engine = first(static.get("engine"), review.get("engine"), target.get("engine"))
    sha256 = first(parse_sha256(args.sha256), fetch.get("sha256"), target.get("sha256"))
    package_bytes = infer_package_size(fetch, args.fetch)

    maps = mc_value(mc, static, ("maps_loaded",), ("map_count_verified_by_marshal", "map_count"))
    events = mc_value(mc, static, ("events", "event_count"))
    event_pages = mc_value(mc, static, ("event_pages", "pages"))
    event_commands = mc_value(mc, static, ("event_commands",))
    dialogue_lines = mc_value(mc, static, ("dialogue_lines",))
    dialogue_chars = mc_value(mc, static, ("dialogue_chars", "story_text_chars_proxy"), ("story_text_chars_proxy", "literal_text_chars"))
    choices = mc_value(mc, static, ("choice_options", "choices"))
    common_events = mc_value(mc, static, ("common_events",))
    transfers = mc_value(mc, static, ("map_transfers", "transfers"))
    battle_calls = mc_value(mc, static, ("battle_calls",))
    shops = mc_value(mc, static, ("shop_calls", "shops"))
    switches = mc_value(mc, static, ("switches",))
    variables = mc_value(mc, static, ("variables",))
    actors = mc_value(mc, static, ("actors",))
    classes = mc_value(mc, static, ("classes",))
    skills = mc_value(mc, static, ("skills",))
    items = mc_value(mc, static, ("items",))
    weapons = mc_value(mc, static, ("weapons",))
    armors = mc_value(mc, static, ("armors",))
    enemies = mc_value(mc, static, ("enemies",))
    troops = mc_value(mc, static, ("troops",))
    states = mc_value(mc, static, ("states",))
    scripts = mc_value(mc, static, ("scripts", "script_sections"))
    image_count = num(static.get("image_count"))
    image_bytes = num(static.get("image_bytes"))
    audio_count = num(static.get("audio_count"))
    audio_bytes = num(static.get("audio_bytes"))

    structural_scores = review.get("ai_structural_scores_5") if isinstance(review.get("ai_structural_scores_5"), dict) else {}
    content_richness = num(structural_scores.get("content_richness"))
    ai_interest = num(structural_scores.get("ai_interest_prediction"))

    system_values = [actors, classes, skills, items, weapons, armors, enemies, troops, states, common_events]
    system_object_count = int(sum(v for v in system_values if isinstance(v, (int, float)))) if any(v is not None for v in system_values) else None
    asset_count = int(sum(v for v in (image_count, audio_count) if isinstance(v, (int, float)))) if image_count is not None or audio_count is not None else None

    semantic = runtime_semantic_defaults(smoke)
    runtime = {
        "mechanical_status": smoke.get("status") if smoke else None,
        "playability_class": smoke.get("playability_class") if smoke else None,
        "runtime_name": smoke.get("runtime") if smoke else None,
        "process_alive_boot": bool_or_none(smoke.get("process_alive_boot")) if smoke else None,
        "visible_windows_boot": num(smoke.get("visible_windows_boot")) if smoke else None,
        "boot_to_confirm_changed_pixels": num(smoke.get("boot_to_confirm_changed_pixels")) if smoke else None,
        "confirm_to_movement_changed_pixels": num(smoke.get("confirm_to_movement_changed_pixels")) if smoke else None,
        "runtime_error_class": first(smoke.get("runtime_error_class"), smoke.get("status") if smoke.get("status") in {"BOOT_FAILED", "SMOKE_ERROR", "CI_RUNTIME_SETUP_FAILED", "CI_AUDIO_SETUP_FAILED"} else None),
        **semantic,
    }

    hist = target.get("historical_reputation") if isinstance(target.get("historical_reputation"), dict) else {}
    historical_rating = first(hist.get("rating_5"), review.get("historical_player_rating_5"))
    if historical_rating is None and target.get("historical_rating_10") is not None:
        try:
            historical_rating = float(target.get("historical_rating_10")) / 2.0
        except Exception:
            pass

    record = {
        "schema_version": SCHEMA_VERSION,
        "domain": "fangame",
        "identity": {
            "game_id": first(target.get("game_id"), target.get("id")),
            "title": title,
            "version": first(target.get("version"), target.get("release_version")),
            "engine": engine,
            "archive_filename": archive_filename,
            "package_bytes": package_bytes,
            "sha256": sha256,
            "lineage": first(target.get("lineage"), target.get("provenance")),
            "source": first(target.get("source"), target.get("source_url"), fetch.get("source_url"), fetch.get("url")),
        },
        "observed": {
            "extract_ok": bool_or_none(static.get("extract_ok")) if static else None,
            "structural_status": static.get("playability_structural") if static else None,
            "encrypted_game_archive": bool_or_none(static.get("encrypted_game_archive")) if static else None,
            "clean_launcher_present": bool_or_none(static.get("clean_launcher_present")) if static else None,
            "maps": maps,
            "events": events,
            "event_pages": event_pages,
            "event_commands": event_commands,
            "dialogue_lines": dialogue_lines,
            "dialogue_chars": dialogue_chars,
            "choices": choices,
            "common_events": common_events,
            "transfers": transfers,
            "battle_calls": battle_calls,
            "shops": shops,
            "switches": switches,
            "variables": variables,
            "actors": actors,
            "classes": classes,
            "skills": skills,
            "items": items,
            "weapons": weapons,
            "armors": armors,
            "enemies": enemies,
            "troops": troops,
            "states": states,
            "scripts": scripts,
            "image_count": image_count,
            "image_bytes": image_bytes,
            "audio_count": audio_count,
            "audio_bytes": audio_bytes,
            "content_scale": static.get("content_scale") if static else None,
        },
        "runtime": runtime,
        "derived": {
            "dialogue_density_per_map": safe_div(dialogue_lines, maps),
            "event_command_density_per_map": safe_div(event_commands, maps),
            "choice_density_per_1000_commands": safe_div(choices, event_commands, 1000.0),
            "transfer_density_per_map": safe_div(transfers, maps),
            "asset_count": asset_count,
            "system_object_count": system_object_count,
            "content_richness_score_5": content_richness,
        },
        "inferred": {
            "sidequest_candidate_count": None,
            "sidequest_confidence": "UNKNOWN",
            "ending_candidate_count": None,
            "ending_confidence": "UNKNOWN",
            "estimated_hours_range": None,
            "grind_pressure": None,
            "inference_version": "none.v0.2",
            "evidence_summary": "v0.2 emits normalized observed/derived features only; sidequest/ending/time/grind inference is intentionally deferred to graph/inference modules.",
        },
        "ranking": {
            "historical_rating_5": num(historical_rating),
            "historical_votes": num(first(hist.get("votes"), review.get("historical_votes"))),
            "historical_downloads": num(first(hist.get("downloads"), review.get("historical_downloads"))),
            "ci_playability_score_5": num(review.get("ci_playability_score_5")),
            "ai_structural_score_5": ai_interest,
            "personal_fit_score_5": None,
            "final_priority_score_5": None,
            "verdict": review.get("verdict") if review else None,
        },
        "evidence": {
            "fetch_report": str(Path(args.fetch).name) if args.fetch else None,
            "static_report": str(Path(args.static).name) if args.static and Path(args.static).exists() else None,
            "smoke_report": str(Path(args.smoke).name) if args.smoke and Path(args.smoke).exists() else None,
            "review_card": str(Path(args.review).name) if args.review and Path(args.review).exists() else None,
            "screenshots": [str(p.name) for p in sorted(Path(args.smoke).resolve().parent.glob("*.png"))] if args.smoke and Path(args.smoke).exists() else [],
            "drive_evidence_id": None,
        },
        "audit": {
            "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "feature_emitter_version": EMITTER_VERSION,
            "inference_version": "none.v0.2",
            "github_run_id": os.environ.get("GITHUB_RUN_ID"),
            "github_sha": os.environ.get("GITHUB_SHA"),
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
