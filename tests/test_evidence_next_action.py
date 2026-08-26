#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEXT = ROOT / "tools" / "evidence_next_action.py"
NEXT_POLICY = ROOT / "policies" / "fangame_next_action_v08.json"
AUDIT = ROOT / "tools" / "fangame_calibration_audit.py"
CAL_POLICY = ROOT / "policies" / "fangame_calibration_v07.json"
CAL_SCHEMA = ROOT / "schemas" / "fangame_calibration_label_v07.schema.json"


def feature(game_id, title, *, map_verified=True, progression="PROGRESSION_OBSERVED", vector="VECTOR_READY", rank=4.5):
    runtime = {"map_gameplay_verified": True} if map_verified else {}
    return {
        "identity": {"game_id": game_id, "title": title},
        "runtime": runtime,
        "progression": {"status": progression},
        "grind_vector": {"status": vector},
        "inferred": {"sidequest_confidence": "HIGH", "ending_confidence": "MEDIUM"},
        "ranking": {
            "ai_structural_score_5": rank,
            "ci_playability_score_5": rank,
            "historical_rating_5": rank,
            "personal_fit_score_5": rank,
        },
    }


def direct_label():
    return {
        "schema_version": "fangame.calibration.v0.7",
        "identity": {"game_id": "A", "title": "Alpha", "version": "1.0", "sha256": "a" * 64},
        "context": {
            "completion_scope": "MAIN_STORY_COMPLETE",
            "difficulty": "Normal",
            "speedup_used": False,
            "speed_multiplier": 1.0,
            "cheats_or_debug_used": False,
            "exp_or_difficulty_mode": None,
            "optional_content_scope": "main story",
            "platform_runtime": "Windows",
            "notes": None,
        },
        "labels": {
            "main_story_hours": {
                "status": "LABELED", "min_hours": None, "max_hours": None, "measured_hours": 18.0,
                "basis": "MEASURED_SESSION_SUM", "confidence": "HIGH", "evidence_refs": ["fixture://A/hours"]
            },
            "grind_pressure": {
                "status": "LABELED", "ordinal": 1, "basis": "PLAYTHROUGH_RATED", "confidence": "HIGH",
                "evidence_refs": ["fixture://A/grind"], "rationale": "fixture"
            },
            "verified_sidequest_count": None,
            "verified_ending_count": None,
        },
        "provenance": {
            "label_source_type": "MEASURED_PLAY_SESSION", "source_ref": "fixture://A", "rater_id": "fixture",
            "source_date": "2026-08-26", "notes": None
        },
        "audit": {
            "rubric_version": "fangame.calibration.rubric.v0.7", "created_at_utc": "2026-08-26T08:30:00Z",
            "label_record_id": "A-direct", "review_status": "ACCEPTED", "review_notes": None
        }
    }


def main():
    a = feature("A", "Alpha", map_verified=True, rank=4.8)
    b = feature("B", "Beta", map_verified=False, rank=4.7)
    c = feature("C", "Gamma", map_verified=True, progression="PROGRESSION_UNAVAILABLE", vector="VECTOR_UNAVAILABLE", rank=2.0)

    compare = {
        "engine_version": "evidence.feature.compare.v0.6",
        "policy_version": "fangame.compare.v0.6",
        "objects": [
            {
                "id": "A", "label": "Alpha", "cluster_id": "cluster:001", "anomaly_score": 0.2, "feature_coverage": 0.95,
                "ranking": {"score_5": 4.8, "coverage": 1.0},
                "nearest_neighbors": [{"id": "B", "label": "Beta", "similarity": 0.7, "coverage": 0.9}],
            },
            {
                "id": "B", "label": "Beta", "cluster_id": "cluster:001", "anomaly_score": 2.2, "feature_coverage": 0.80,
                "ranking": {"score_5": 4.7, "coverage": 1.0},
                "nearest_neighbors": [{"id": "A", "label": "Alpha", "similarity": 0.7, "coverage": 0.9}],
            },
            {
                "id": "C", "label": "Gamma", "cluster_id": "cluster:002", "anomaly_score": 0.1, "feature_coverage": 0.70,
                "ranking": {"score_5": 2.0, "coverage": 1.0},
                "nearest_neighbors": [{"id": "A", "label": "Alpha", "similarity": 0.9, "coverage": 0.9}],
            },
        ],
    }

    with tempfile.TemporaryDirectory() as td0:
        td = Path(td0)
        records = td / "records.ndjson"
        records.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in (a, b, c)) + "\n", encoding="utf-8")
        compare_path = td / "compare.json"
        compare_path.write_text(json.dumps(compare, ensure_ascii=False, indent=2), encoding="utf-8")

        labels = td / "labels"; labels.mkdir()
        (labels / "A.json").write_text(json.dumps(direct_label(), ensure_ascii=False, indent=2), encoding="utf-8")
        audit_path = td / "calibration_audit.json"
        subprocess.run([
            sys.executable, str(AUDIT), "--labels", str(labels), "--policy", str(CAL_POLICY),
            "--schema", str(CAL_SCHEMA), "--out", str(audit_path)
        ], cwd=ROOT, check=True)
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        assert audit["audit_version"] == "fangame.calibration.audit.v0.8"
        assert audit["game_index"]["A"]["has_direct_hours"] is True
        assert audit["game_index"]["A"]["has_direct_grind"] is True
        assert "B" not in audit["game_index"]

        outj = td / "next.json"; outc = td / "next.csv"
        subprocess.run([
            sys.executable, str(NEXT), "--records", str(records), "--policy", str(NEXT_POLICY),
            "--compare", str(compare_path), "--aux", str(audit_path), "--out-json", str(outj), "--out-csv", str(outc)
        ], cwd=ROOT, check=True)
        result = json.loads(outj.read_text(encoding="utf-8"))
        assert result["engine_version"] == "evidence.next.action.v0.8"
        assert result["policy_version"] == "fangame.next-action.v0.8"
        assert "proxy" in result["score_semantics"].lower()
        assert "bayesian" in result["score_semantics"].lower()

        by_pair = {(x["object_id"], x["action_id"]): x for x in result["candidates"]}
        assert ("A", "COLLECT_BASELINE_CALIBRATION_PLAYTHROUGH") not in by_pair, "direct-labeled game was wastefully reselected"
        assert ("B", "COLLECT_BASELINE_CALIBRATION_PLAYTHROUGH") in by_pair
        assert ("C", "COLLECT_BASELINE_CALIBRATION_PLAYTHROUGH") in by_pair
        assert by_pair[("B", "COLLECT_BASELINE_CALIBRATION_PLAYTHROUGH")]["priority_proxy_5"] > by_pair[("C", "COLLECT_BASELINE_CALIBRATION_PLAYTHROUGH")]["priority_proxy_5"]

        assert ("B", "VERIFY_MAP_GAMEPLAY") in by_pair
        assert ("A", "VERIFY_MAP_GAMEPLAY") not in by_pair
        assert ("C", "REPAIR_PROGRESSION_EVIDENCE") in by_pair
        assert ("B", "REPAIR_PROGRESSION_EVIDENCE") not in by_pair
        assert ("C", "REPAIR_GRIND_VECTOR") not in by_pair, "grind-vector repair ignored progression prerequisite"

        chosen = by_pair[("B", "VERIFY_MAP_GAMEPLAY")]
        assert chosen["components"]
        assert any(x["component"] == "uncertainty" for x in chosen["components"])
        assert chosen["matched_uncertainty_reasons"][0]["path"] == "record.runtime.map_gameplay_verified"
        assert chosen["execution_hint"]

        ranks = [x["rank"] for x in result["candidates"]]
        assert ranks == list(range(1, len(ranks) + 1))

    print("evidence next-action v0.8 regression: PASS")


if __name__ == "__main__":
    main()
