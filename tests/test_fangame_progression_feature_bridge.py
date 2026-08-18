#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def base_v04():
    return {
        "schema_version": "fangame.features.v0.4",
        "domain": "fangame",
        "identity": {"title": "Progression Fixture", "archive_filename": "fixture.rar"},
        "observed": {},
        "runtime": {},
        "derived": {},
        "inferred": {
            "sidequest_confidence": "UNKNOWN",
            "ending_confidence": "UNKNOWN",
            "estimated_hours_range": None,
            "grind_pressure": None,
            "inference_version": "fangame.graph.inference.v0.4.1"
        },
        "ranking": {},
        "graph": {
            "status": "GRAPH_OBSERVED",
            "graph_version": "rpgmaker.graph.v0.3",
            "start_map_id": 1,
            "summary": {}
        },
        "evidence": {},
        "audit": {
            "generated_at_utc": "2026-08-18T00:00:00+00:00",
            "feature_emitter_version": "0.3.0",
            "schema_merge_version": "0.4.1",
            "inference_version": "fangame.graph.inference.v0.4.1"
        }
    }


def run_bridge(features, progression, out):
    args = [
        sys.executable, str(ROOT / "tools" / "fangame_progression_feature_merge.py"),
        "--features", str(features), "--out", str(out)
    ]
    if progression is not None:
        args += ["--progression", str(progression)]
    subprocess.run(args, cwd=ROOT, check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def validate(rec):
    import jsonschema
    schema = json.loads((ROOT / "schemas" / "fangame_features_v05a.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(rec, schema)


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        features = td / "features.json"
        progression = td / "rpgmaker_progression.json"
        out = td / "out.json"

        features.write_text(json.dumps(base_v04()), encoding="utf-8")
        progression.write_text(json.dumps({
            "evidence_version": "rpgmaker.progression.v0.5a",
            "observed": {
                "maps_loaded": 10,
                "maps_with_random_encounters": 4,
                "random_encounter_map_ratio": 0.4,
                "encounter_step_stats": {"count": 4, "median": 25.0},
                "enemy_exp_stats": {"count": 20, "median": 80.0},
                "enemy_gold_stats": {"count": 20, "median": 30.0},
                "equipment_price_stats": {"count": 10, "median": 500.0},
                "event_commands": {"battle_processing_ops": 6, "shop_processing_ops": 5, "recover_all_ops": 3}
            },
            "derived": {
                "median_equipment_price_to_enemy_gold_ratio": 16.6667,
                "median_class_exp_basis_to_enemy_exp_ratio": 4.25
            },
            "limitations": ["fixture limitation"],
            "load_errors": []
        }), encoding="utf-8")

        rec = run_bridge(features, progression, out)
        assert rec["schema_version"] == "fangame.features.v0.5a"
        p = rec["progression"]
        assert p["status"] == "PROGRESSION_OBSERVED"
        assert p["evidence_version"] == "rpgmaker.progression.v0.5a"
        assert p["observed"]["random_encounter_map_ratio"] == 0.4
        assert p["derived"]["median_equipment_price_to_enemy_gold_ratio"] == 16.6667
        assert p["load_error_count"] == 0
        assert rec["inferred"]["estimated_hours_range"] is None
        assert rec["inferred"]["grind_pressure"] is None
        assert rec["inferred"]["progression_inference_status"] == "NOT_RUN_V0.5A_EVIDENCE_ONLY"
        assert rec["evidence"]["progression_report"] == "rpgmaker_progression.json"
        assert rec["audit"]["pre_progression_feature_version"] == "fangame.features.v0.4"
        assert rec["audit"]["progression_bridge_version"] == "0.5a.0"
        assert rec["audit"]["progression_evidence_version"] == "rpgmaker.progression.v0.5a"
        validate(rec)

        # Missing progression evidence must remain explicit, not turn into zeroes or fake policy output.
        features2 = td / "features2.json"
        out2 = td / "out2.json"
        features2.write_text(json.dumps(base_v04()), encoding="utf-8")
        rec2 = run_bridge(features2, None, out2)
        assert rec2["progression"]["status"] == "PROGRESSION_UNAVAILABLE"
        assert rec2["progression"]["evidence_version"] is None
        assert rec2["progression"]["observed"] == {}
        assert rec2["progression"]["derived"] == {}
        assert rec2["evidence"]["progression_report"] is None
        assert rec2["inferred"]["estimated_hours_range"] is None
        assert rec2["inferred"]["grind_pressure"] is None
        validate(rec2)

    print("fangame progression feature bridge v0.5a: PASS")


if __name__ == "__main__":
    main()
