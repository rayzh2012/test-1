#!/usr/bin/env python3
"""Generate a sanitized public fangame analysis report from a normalized profile.

The public layer deliberately excludes private Drive IDs, personal-fit fields,
private notes, and binary payloads. It publishes reproducible identity, observed
metrics, deterministic derived metrics, system evidence, and clearly-labelled
heuristic descriptors. Percentile claims are emitted only when a compatible
baseline-comparison object is explicitly supplied.
"""

import argparse
import json
from pathlib import Path

PUBLIC_SCHEMA = "fangame.public_analysis.v0.1"
DESCRIPTOR_VERSION = "fangame.public_descriptors.v0.1"


def pick(d, keys):
    return {k: d.get(k) for k in keys if k in d}


def build_descriptors(profile):
    m = profile.get("metrics", {}) or {}
    d = profile.get("derived", {}) or {}
    p = profile.get("progression", {}) or {}
    s = profile.get("system_evidence", {}) or {}
    out = []

    # These are absolute, versioned descriptive thresholds, not corpus percentiles.
    if (m.get("maps") or 0) >= 300:
        out.append({"id": "large_map_surface", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"maps={m.get('maps')}"})
    if (m.get("event_commands") or 0) >= 100000:
        out.append({"id": "heavy_event_scripting", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"event_commands={m.get('event_commands')}"})
    if (m.get("enabled_plugins") or 0) >= 100:
        out.append({"id": "broad_plugin_surface", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"enabled_plugins={m.get('enabled_plugins')}"})
    if p.get("random_encounter_map_ratio") == 0:
        out.append({"id": "no_native_random_encounter_maps", "kind": "OBSERVED_STRUCTURE", "evidence": "random_encounter_map_ratio=0"})
    if (m.get("battle_calls") or 0) > 0 and p.get("random_encounter_map_ratio") == 0:
        out.append({"id": "scripted_or_event_driven_combat_structure", "kind": "DERIVED_STRUCTURE", "evidence": f"battle_calls={m.get('battle_calls')}; random_encounter_map_ratio=0"})
    if (d.get("dialogue_chars_per_map") or 0) >= 500:
        out.append({"id": "dialogue_dense_absolute", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"dialogue_chars_per_map={d.get('dialogue_chars_per_map'):.2f}"})
    if (d.get("choice_options_per_map") or 0) >= 10:
        out.append({"id": "choice_dense_absolute", "kind": "ABSOLUTE_HEURISTIC", "evidence": f"choice_options_per_map={d.get('choice_options_per_map'):.2f}"})

    known_systems = [
        k for k, v in s.items()
        if isinstance(v, bool) and v
    ]
    if len(known_systems) >= 4:
        out.append({"id": "multiple_explicit_qol_or_meta_systems", "kind": "OBSERVED_SYSTEM_EVIDENCE", "evidence": sorted(known_systems)})
    return out


def sanitize(profile, source_url=None, parser_version=None, analysis_version=None, baseline=None):
    report = {
        "schema": PUBLIC_SCHEMA,
        "descriptor_version": DESCRIPTOR_VERSION,
        "identity": {
            **pick(profile, ["game_id", "title", "version", "engine", "sha256", "bytes"]),
            "source_url": source_url,
        },
        "reproducibility": {
            "input_schema": profile.get("schema"),
            "parser_version": parser_version,
            "analysis_version": analysis_version or DESCRIPTOR_VERSION,
        },
        "observed": pick(profile.get("metrics", {}) or {}, [
            "maps", "events", "event_pages", "event_commands", "dialogue_blocks",
            "dialogue_chars", "choice_options", "battle_calls", "shops", "enabled_plugins"
        ]),
        "derived": pick(profile.get("derived", {}) or {}, [
            "events_per_map", "event_commands_per_map", "dialogue_chars_per_map", "choice_options_per_map"
        ]),
        "progression": pick(profile.get("progression", {}) or {}, [
            "random_encounter_map_ratio", "encounter_step_median", "enemy_exp_median",
            "enemy_gold_median", "equipment_price_median"
        ]),
        "system_evidence": profile.get("system_evidence", {}) or {},
        "descriptors": build_descriptors(profile),
        "baseline": {
            "status": profile.get("baseline_status", "UNKNOWN"),
            "comparison": baseline,
        },
        "publication_policy": {
            "contains_game_binary": False,
            "contains_private_drive_ids": False,
            "contains_personal_fit": False,
            "percentile_claims_require_compatible_baseline": True,
        },
    }
    return report


def fmt(v, digits=2):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{digits}f}"
    return f"{v:,}" if isinstance(v, int) else str(v)


def render_markdown(r):
    i, o, d, p, s = r["identity"], r["observed"], r["derived"], r["progression"], r["system_evidence"]
    lines = [
        f"# {i.get('title', 'Unknown game')} — Public Genome",
        "",
        f"**Version:** {i.get('version', '—')}  ",
        f"**Engine:** {i.get('engine', '—')}  ",
        f"**Package bytes:** {fmt(i.get('bytes'))}  ",
        f"**SHA256:** `{i.get('sha256', '—')}`  ",
    ]
    if i.get("source_url"):
        lines.append(f"**Public source:** {i['source_url']}  ")
    lines += [
        "",
        "## Structural feature vector",
        "",
        "| Feature | Value |",
        "|---|---:|",
    ]
    rows = [
        ("Maps", o.get("maps")), ("Events", o.get("events")), ("Event pages", o.get("event_pages")),
        ("Event commands", o.get("event_commands")), ("Dialogue blocks", o.get("dialogue_blocks")),
        ("Dialogue characters", o.get("dialogue_chars")), ("Choice options", o.get("choice_options")),
        ("Battle calls", o.get("battle_calls")), ("Shops", o.get("shops")), ("Enabled plugins", o.get("enabled_plugins")),
        ("Events / map", d.get("events_per_map")), ("Event commands / map", d.get("event_commands_per_map")),
        ("Dialogue chars / map", d.get("dialogue_chars_per_map")), ("Choice options / map", d.get("choice_options_per_map")),
        ("Random encounter map ratio", p.get("random_encounter_map_ratio")),
    ]
    lines += [f"| {name} | {fmt(value)} |" for name, value in rows]
    lines += ["", "## Explicit system evidence", ""]
    for k, v in sorted(s.items()):
        lines.append(f"- `{k}`: `{v}`")
    lines += ["", "## Machine-generated descriptors", ""]
    if r["descriptors"]:
        for x in r["descriptors"]:
            lines.append(f"- **{x['id']}** — {x['kind']}; evidence: `{x['evidence']}`")
    else:
        lines.append("- No descriptor fired under the current absolute heuristic version.")
    lines += [
        "",
        "## Baseline status",
        "",
        f"`{r['baseline']['status']}`",
        "",
        "No production percentile or 'top X%' claim is made unless a compatible ordinary-RPG corpus was measured with the same schema/parser family.",
        "",
        "## Publication boundary",
        "",
        "This report publishes structural analysis only. It contains no game binary, private Drive identifier, or personal-fit score.",
    ]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--source-url")
    ap.add_argument("--parser-version")
    ap.add_argument("--analysis-version")
    ap.add_argument("--baseline-json")
    args = ap.parse_args()

    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    baseline = None
    if args.baseline_json:
        baseline = json.loads(Path(args.baseline_json).read_text(encoding="utf-8"))
    report = sanitize(profile, args.source_url, args.parser_version, args.analysis_version, baseline)
    Path(args.out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_json).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.out_md).write_text(render_markdown(report), encoding="utf-8")


if __name__ == "__main__":
    main()
