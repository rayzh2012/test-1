#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def flatten(obj, prefix=""):
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out.update(flatten(v, key))
    elif isinstance(obj, list):
        out[prefix] = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    else:
        out[prefix] = obj
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="Directory containing fangame_features.json files")
    ap.add_argument("--ndjson", default="fangame_feature_store.ndjson")
    ap.add_argument("--csv", dest="csv_path", default="fangame_feature_store.csv")
    args = ap.parse_args()

    files = sorted(Path(args.root).rglob("fangame_features.json"))
    records = []
    for p in files:
        try:
            records.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"skip {p}: {e}")

    Path(args.ndjson).write_text(
        "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in records),
        encoding="utf-8",
    )

    flat = [flatten(r) for r in records]
    preferred = [
        "schema_version",
        "identity.game_id", "identity.title", "identity.version", "identity.engine",
        "identity.archive_filename", "identity.package_bytes", "identity.sha256", "identity.source",
        "observed.maps", "observed.events", "observed.event_pages", "observed.event_commands",
        "observed.dialogue_lines", "observed.dialogue_chars", "observed.choices", "observed.common_events",
        "observed.transfers", "observed.battle_calls", "observed.shops", "observed.switches", "observed.variables",
        "observed.actors", "observed.classes", "observed.skills", "observed.items", "observed.weapons",
        "observed.armors", "observed.enemies", "observed.troops", "observed.states", "observed.scripts",
        "observed.image_count", "observed.audio_count", "observed.content_scale",
        "runtime.mechanical_status", "runtime.playability_class", "runtime.title_verified",
        "runtime.new_game_verified", "runtime.input_flow_verified", "runtime.map_gameplay_verified",
        "derived.dialogue_density_per_map", "derived.event_command_density_per_map",
        "derived.choice_density_per_1000_commands", "derived.transfer_density_per_map",
        "derived.system_object_count", "derived.content_richness_score_5",
        "inferred.sidequest_candidate_count", "inferred.sidequest_confidence",
        "inferred.ending_candidate_count", "inferred.ending_confidence",
        "inferred.estimated_hours_range", "inferred.grind_pressure", "inferred.inference_version",
        "ranking.historical_rating_5", "ranking.historical_votes", "ranking.historical_downloads",
        "ranking.ci_playability_score_5", "ranking.ai_structural_score_5",
        "ranking.personal_fit_score_5", "ranking.final_priority_score_5", "ranking.verdict",
        "evidence.drive_evidence_id", "audit.generated_at_utc", "audit.feature_emitter_version",
    ]
    all_keys = set()
    for r in flat:
        all_keys.update(r.keys())
    columns = [c for c in preferred if c in all_keys] + sorted(all_keys - set(preferred))

    with Path(args.csv_path).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(flat)

    print(json.dumps({"records": len(records), "ndjson": args.ndjson, "csv": args.csv_path, "columns": len(columns)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
