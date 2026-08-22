#!/usr/bin/env python3
"""Generate a sanitized public fangame analysis report from a normalized profile.

Public output is whitelist-based: reproducible identity, observed structural
metrics, deterministic derived features, explicit system evidence, and clearly
versioned heuristics. Private Drive IDs, personal-fit fields, private notes, and
binary payloads are never copied through.
"""

import argparse
import json
from pathlib import Path

PUBLIC_SCHEMA = "fangame.public_analysis.v0.1"
DESCRIPTOR_VERSION = "fangame.public_descriptors.v0.1"
INDEX_SCHEMA = "fangame.public_report_index_entry.v0.1"

OBSERVED_KEYS = [
    "maps", "events", "event_pages", "event_commands", "dialogue_blocks",
    "dialogue_lines", "dialogue_chars", "choice_commands", "choice_options",
    "conditional_branches", "transfers", "battle_calls", "shops",
    "common_events", "actors", "classes", "skills", "items", "weapons",
    "armors", "enemies", "troops", "states", "enabled_plugins", "total_plugins",
    "image_count", "audio_count",
]
DERIVED_KEYS = [
    "events_per_map", "event_commands_per_map", "dialogue_chars_per_map",
    "dialogue_chars_per_event", "choice_options_per_map",
    "conditional_branches_per_map", "transfers_per_map", "battle_calls_per_map",
    "shops_per_100_maps", "maps_with_events_ratio",
]
PROGRESSION_KEYS = [
    "random_encounter_map_ratio", "encounter_step_median", "enemy_exp_median",
    "enemy_gold_median", "equipment_price_median",
]


def pick(d, keys):
    return {k: d.get(k) for k in keys if k in d}


def build_descriptors(profile):
    m = profile.get("metrics", {}) or {}
    d = profile.get("derived", {}) or {}
    p = profile.get("progression", {}) or {}
    s = profile.get("system_evidence", {}) or {}
    out = []

    # Absolute, versioned descriptive thresholds. These are NOT corpus percentiles.
    if (m.get("maps") or 0) >= 300:
        out.append({"id": "large_map_surface", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"maps={m.get('maps')}"})
    if (m.get("event_commands") or 0) >= 100000:
        out.append({"id": "heavy_event_scripting", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"event_commands={m.get('event_commands')}"})
    if (m.get("enabled_plugins") or 0) >= 100:
        out.append({"id": "broad_plugin_surface", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"enabled_plugins={m.get('enabled_plugins')}"})
    db_total = sum((m.get(k) or 0) for k in ("actors", "classes", "skills", "items", "weapons", "armors", "enemies", "troops", "states", "common_events"))
    if db_total >= 3000:
        out.append({"id": "broad_database_surface", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"database_objects={db_total}"})
    if p.get("random_encounter_map_ratio") == 0:
        out.append({"id": "no_native_random_encounter_maps", "kind": "OBSERVED_STRUCTURE", "evidence": "random_encounter_map_ratio=0"})
    if (m.get("battle_calls") or 0) > 0 and p.get("random_encounter_map_ratio") == 0:
        out.append({"id": "scripted_or_event_driven_combat_structure", "kind": "DERIVED_STRUCTURE", "evidence": f"battle_calls={m.get('battle_calls')}; random_encounter_map_ratio=0"})
    if (d.get("dialogue_chars_per_map") or 0) >= 500:
        out.append({"id": "dialogue_dense_absolute", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"dialogue_chars_per_map={d.get('dialogue_chars_per_map'):.2f}"})
    if (d.get("choice_options_per_map") or 0) >= 10:
        out.append({"id": "choice_dense_absolute", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"choice_options_per_map={d.get('choice_options_per_map'):.2f}"})

    known_systems = [k for k, v in s.items() if isinstance(v, bool) and v]
    if len(known_systems) >= 4:
        out.append({"id": "multiple_explicit_qol_or_meta_systems", "kind": "OBSERVED_SYSTEM_EVIDENCE", "evidence": sorted(known_systems)})
    return out


def sanitize(profile, source_url=None, parser_version=None, analysis_version=None, baseline=None):
    source = source_url or profile.get("source_url")
    return {
        "schema": PUBLIC_SCHEMA,
        "descriptor_version": DESCRIPTOR_VERSION,
        "identity": {
            **pick(profile, ["game_id", "title", "version", "engine", "sha256", "bytes"]),
            "source_url": source,
        },
        "reproducibility": {
            "input_schema": profile.get("schema"),
            "parser_version": parser_version,
            "analysis_version": analysis_version or DESCRIPTOR_VERSION,
        },
        "observed": pick(profile.get("metrics", {}) or {}, OBSERVED_KEYS),
        "derived": pick(profile.get("derived", {}) or {}, DERIVED_KEYS),
        "progression": pick(profile.get("progression", {}) or {}, PROGRESSION_KEYS),
        "system_evidence": profile.get("system_evidence", {}) or {},
        "descriptors": build_descriptors(profile),
        "baseline": {"status": profile.get("baseline_status", "UNKNOWN"), "comparison": baseline},
        "publication_policy": {
            "contains_game_binary": False,
            "contains_private_drive_ids": False,
            "contains_personal_fit": False,
            "percentile_claims_require_compatible_baseline": True,
        },
    }


def fmt(v, digits=2):
    if v is None: return "—"
    if isinstance(v, float): return f"{v:.{digits}f}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def render_markdown(r):
    i, o, d, p, s = r["identity"], r["observed"], r["derived"], r["progression"], r["system_evidence"]
    lines = [
        f"# {i.get('title', 'Unknown game')} — Public Genome", "",
        f"**Version:** {i.get('version', '—')}  ", f"**Engine:** {i.get('engine', '—')}  ",
        f"**Package bytes:** {fmt(i.get('bytes'))}  ", f"**SHA256:** `{i.get('sha256', '—')}`  ",
    ]
    if i.get("source_url"): lines.append(f"**Public source:** {i['source_url']}  ")
    lines += ["", "## Structural feature vector", "", "| Feature | Value |", "|---|---:|"]
    preferred = [
        ("Maps", "maps"), ("Events", "events"), ("Event pages", "event_pages"),
        ("Event commands", "event_commands"), ("Dialogue blocks", "dialogue_blocks"),
        ("Dialogue lines", "dialogue_lines"), ("Dialogue characters", "dialogue_chars"),
        ("Choice commands", "choice_commands"), ("Choice options", "choice_options"),
        ("Conditional branches", "conditional_branches"), ("Transfers", "transfers"),
        ("Battle calls", "battle_calls"), ("Shops", "shops"), ("Common events", "common_events"),
        ("Actors", "actors"), ("Classes", "classes"), ("Skills", "skills"), ("Items", "items"),
        ("Enemies", "enemies"), ("Troops", "troops"), ("States", "states"),
        ("Enabled plugins", "enabled_plugins"), ("Total plugins", "total_plugins"),
        ("Images", "image_count"), ("Audio", "audio_count"),
    ]
    for label, key in preferred:
        if key in o: lines.append(f"| {label} | {fmt(o.get(key))} |")
    derived_rows = [
        ("Events / map", "events_per_map"), ("Event commands / map", "event_commands_per_map"),
        ("Dialogue chars / map", "dialogue_chars_per_map"), ("Choice options / map", "choice_options_per_map"),
        ("Conditional branches / map", "conditional_branches_per_map"), ("Transfers / map", "transfers_per_map"),
        ("Battle calls / map", "battle_calls_per_map"), ("Maps with events ratio", "maps_with_events_ratio"),
    ]
    for label, key in derived_rows:
        if key in d: lines.append(f"| {label} | {fmt(d.get(key))} |")
    if "random_encounter_map_ratio" in p:
        lines.append(f"| Random encounter map ratio | {fmt(p.get('random_encounter_map_ratio'))} |")

    lines += ["", "## Explicit system evidence", ""]
    for k, v in sorted(s.items()): lines.append(f"- `{k}`: `{v}`")
    lines += ["", "## Machine-generated descriptors", ""]
    if r["descriptors"]:
        for x in r["descriptors"]: lines.append(f"- **{x['id']}** — {x['kind']}; evidence: `{x['evidence']}`")
    else:
        lines.append("- No descriptor fired under the current absolute heuristic version.")
    lines += [
        "", "## Baseline status", "", f"`{r['baseline']['status']}`", "",
        "No production percentile or `top X%` claim is made unless a compatible ordinary-RPG corpus was measured with the same schema/parser family.",
        "", "## Publication boundary", "",
        "This report publishes structural analysis only. It contains no game binary, private Drive identifier, or personal-fit score.",
    ]
    return "\n".join(lines) + "\n"


def registry_entry(report, json_path=None, markdown_path=None):
    i = report["identity"]
    return {
        "schema": INDEX_SCHEMA,
        "game_id": i.get("game_id"), "title": i.get("title"), "version": i.get("version"),
        "engine": i.get("engine"), "sha256": i.get("sha256"),
        "json": json_path, "markdown": markdown_path,
        "baseline_status": report["baseline"]["status"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--registry-entry-out")
    ap.add_argument("--source-url")
    ap.add_argument("--parser-version")
    ap.add_argument("--analysis-version")
    ap.add_argument("--baseline-json")
    args = ap.parse_args()

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    baseline = json.loads(Path(args.baseline_json).read_text(encoding="utf-8")) if args.baseline_json else None
    report = sanitize(profile, args.source_url, args.parser_version, args.analysis_version, baseline)
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.out_md).write_text(render_markdown(report), encoding="utf-8")
    if args.registry_entry_out:
        entry = registry_entry(report, Path(args.out_json).name, Path(args.out_md).name)
        Path(args.registry_entry_out).write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
