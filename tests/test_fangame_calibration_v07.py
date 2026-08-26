#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "fangame_calibration_label_v07.schema.json"
POLICY = ROOT / "policies" / "fangame_calibration_v07.json"
AUDIT = ROOT / "tools" / "fangame_calibration_audit.py"


def record(rid, game, *, speedup=False, hours_basis="MEASURED_SESSION_SUM", grind_basis="PLAYTHROUGH_RATED", grind=1):
    return {
        "schema_version": "fangame.calibration.v0.7",
        "identity": {
            "game_id": game,
            "title": f"Game {game}",
            "version": "1.0",
            "sha256": "a" * 64,
        },
        "context": {
            "completion_scope": "MAIN_STORY_COMPLETE",
            "difficulty": "Normal",
            "speedup_used": speedup,
            "speed_multiplier": 2.0 if speedup else 1.0,
            "cheats_or_debug_used": False,
            "exp_or_difficulty_mode": None,
            "optional_content_scope": "main story",
            "platform_runtime": "Windows",
            "notes": None,
        },
        "labels": {
            "main_story_hours": {
                "status": "LABELED",
                "min_hours": None,
                "max_hours": None,
                "measured_hours": 20.0,
                "basis": hours_basis,
                "confidence": "HIGH",
                "evidence_refs": [f"evidence://{rid}/hours"],
            },
            "grind_pressure": {
                "status": "LABELED",
                "ordinal": grind,
                "basis": grind_basis,
                "confidence": "HIGH",
                "evidence_refs": [f"evidence://{rid}/grind"],
                "rationale": "fixture",
            },
            "verified_sidequest_count": None,
            "verified_ending_count": None,
        },
        "provenance": {
            "label_source_type": "MEASURED_PLAY_SESSION" if hours_basis == "MEASURED_SESSION_SUM" else "AUTHOR_STATEMENT",
            "source_ref": f"fixture://{rid}",
            "rater_id": "fixture-rater",
            "source_date": "2026-08-26",
            "notes": None,
        },
        "audit": {
            "rubric_version": "fangame.calibration.rubric.v0.7",
            "created_at_utc": "2026-08-26T08:00:00Z",
            "label_record_id": rid,
            "review_status": "ACCEPTED",
            "review_notes": None,
        },
    }


def main():
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    direct = record("L1", "G1", speedup=False)
    contextual = record("L2", "G2", speedup=True)
    reference = record("L3", "G3", speedup=False, hours_basis="AUTHOR_STATED_RANGE", grind_basis="AUTHOR_DESCRIPTION", grind=0)
    reference["labels"]["main_story_hours"].update({"measured_hours": None, "min_hours": 15.0, "max_hours": 25.0})
    reference["provenance"]["label_source_type"] = "AUTHOR_STATEMENT"

    for rec in (direct, contextual, reference):
        jsonschema.validate(rec, schema, format_checker=jsonschema.FormatChecker())

    contaminated = json.loads(json.dumps(direct))
    contaminated["observed"] = {"maps": 999}
    try:
        jsonschema.validate(contaminated, schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise AssertionError("calibration schema accepted observed evidence contamination")

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        labels = td / "labels"; labels.mkdir()
        for i, rec in enumerate((direct, contextual, reference), 1):
            (labels / f"l{i}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        out = td / "audit.json"
        subprocess.run([
            sys.executable, str(AUDIT), "--labels", str(labels), "--policy", str(POLICY),
            "--schema", str(SCHEMA), "--out", str(out)
        ], cwd=ROOT, check=True)
        audit = json.loads(out.read_text(encoding="utf-8"))
        assert audit["valid_records"] == 3
        assert audit["invalid_records"] == 0
        assert audit["label_classes"]["hours"]["DIRECT_TRAINING"] == 1
        assert audit["label_classes"]["hours"]["CONTEXTUAL_ONLY"] == 1
        assert audit["label_classes"]["hours"]["REFERENCE_ONLY"] == 1
        assert audit["label_classes"]["grind"]["DIRECT_TRAINING"] == 1
        assert audit["label_classes"]["grind"]["CONTEXTUAL_ONLY"] == 1
        assert audit["label_classes"]["grind"]["REFERENCE_ONLY"] == 1
        assert audit["hours_readiness"]["status"] == "NOT_READY_BY_POLICY"
        assert audit["grind_readiness"]["status"] == "NOT_READY_BY_POLICY"
        assert audit["hours_readiness"]["direct_label_records"] == 1
        assert audit["grind_readiness"]["direct_label_records"] == 1

    print("fangame calibration v0.7 regression: PASS")


if __name__ == "__main__":
    main()
