#!/usr/bin/env python3
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "tests" / "fixtures" / "nlzj3_feature_v05a_grind.json"


def run(features, out):
    subprocess.run([
        sys.executable, str(ROOT / "tools" / "fangame_grind_vector.py"),
        "--features", str(features), "--out", str(out)
    ], cwd=ROOT, check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def close(a, b, eps=1e-6):
    return abs(a - b) <= eps


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        out = td / "grind_vector.json"
        vec = run(REAL, out)

        assert vec["vector_version"] == "fangame.grind.vector.v0.5b"
        assert vec["source_feature_schema"] == "fangame.features.v0.5a"
        assert vec["status"] == "VECTOR_READY"
        assert vec["coverage"] == 1.0
        assert vec["missing_core_inputs"] == []
        assert vec["calibration_status"] == "UNLABELED_VECTOR_ONLY"
        assert vec["grind_pressure"] is None
        assert vec["policy"]["weighted_score_emitted"] is False
        assert vec["policy"]["hours_estimate_emitted"] is False

        f = vec["features"]
        assert close(f["random_encounter_map_ratio"], 0.26618705035971224)
        assert close(f["encounter_checks_proxy_per_100_steps"], 5.0)
        assert close(f["median_equipment_price_to_enemy_gold_ratio"], 0.5833333333333334)
        assert close(f["log1p_equipment_price_to_enemy_gold_ratio"], math.log1p(0.5833333333333334))
        assert close(f["positive_reward_ops_per_1000_event_commands"], 809 / 15837 * 1000)
        assert close(f["positive_reward_ops_per_map"], 809 / 139)
        assert close(f["change_exp_ops_per_1000_event_commands"], 7 / 15837 * 1000)
        assert close(f["recover_all_ops_per_100_maps"], 7 / 139 * 100)
        assert close(f["battle_processing_ops_per_100_maps"], 21 / 139 * 100)
        assert close(f["shop_processing_ops_per_100_maps"], 13 / 139 * 100)
        assert close(f["transfer_ops_per_100_maps"], 490 / 139 * 100)

        # The suspicious EXP-basis ratio is preserved as context, not silently given a weight.
        assert vec["context_only"]["median_progression_exp_basis_to_enemy_exp_ratio"] == 0.003625
        assert vec["context_only"]["enemy_exp_median"] == 8000.0
        assert vec["context_only"]["enemy_gold_median"] == 12000.0
        assert vec["context_only"]["equipment_price_median"] == 7000.0

        # Missing progression evidence must not become a low-grind zero vector.
        missing = td / "missing.json"
        missing.write_text(json.dumps({
            "schema_version": "fangame.features.v0.5a",
            "progression": {
                "status": "PROGRESSION_UNAVAILABLE",
                "evidence_version": None,
                "observed": {},
                "derived": {},
                "limitations": [],
                "load_error_count": 0
            }
        }), encoding="utf-8")
        vec2 = run(missing, td / "missing_vector.json")
        assert vec2["status"] == "VECTOR_UNAVAILABLE"
        assert vec2["coverage"] == 0.0
        assert vec2["grind_pressure"] is None
        assert len(vec2["missing_core_inputs"]) == 5

    print("fangame grind vector v0.5b real-evidence regression: PASS")


if __name__ == "__main__":
    main()
