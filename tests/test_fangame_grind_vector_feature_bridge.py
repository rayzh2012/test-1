#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "tests" / "fixtures" / "nlzj3_feature_v05a_grind.json"


def run(*args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def validate(rec):
    import jsonschema
    schema = json.loads((ROOT / "schemas" / "fangame_features_v05b.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(rec, schema)


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        features = td / "features.json"
        features.write_text(REAL.read_text(encoding="utf-8"), encoding="utf-8")
        vector = td / "fangame_grind_vector.json"
        run(sys.executable, ROOT / "tools" / "fangame_grind_vector.py", "--features", features, "--out", vector)
        run(sys.executable, ROOT / "tools" / "fangame_grind_vector_feature_merge.py", "--features", features, "--vector", vector, "--out", features)

        rec = json.loads(features.read_text(encoding="utf-8"))
        assert rec["schema_version"] == "fangame.features.v0.5b"
        gv = rec["grind_vector"]
        assert gv["status"] == "VECTOR_READY"
        assert gv["vector_version"] == "fangame.grind.vector.v0.5b"
        assert gv["coverage"] == 1.0
        assert gv["calibration_status"] == "UNLABELED_VECTOR_ONLY"
        assert gv["policy"]["weighted_score_emitted"] is False
        assert gv["policy"]["hours_estimate_emitted"] is False
        assert rec["inferred"]["grind_pressure"] is None
        assert rec["inferred"]["estimated_hours_range"] is None
        assert rec["inferred"]["grind_inference_status"] == "CALIBRATION_NOT_RUN"
        assert rec["evidence"]["grind_vector_report"] == "fangame_grind_vector.json"
        assert rec["audit"]["pre_grind_vector_feature_version"] == "fangame.features.v0.5a"
        assert rec["audit"]["grind_vector_bridge_version"] == "0.5b.0"
        assert rec["audit"]["grind_vector_version"] == "fangame.grind.vector.v0.5b"
        validate(rec)

        # Absence of a vector is explicit and still cannot silently become a low-grind score.
        missing = td / "missing_features.json"
        missing.write_text(REAL.read_text(encoding="utf-8"), encoding="utf-8")
        run(sys.executable, ROOT / "tools" / "fangame_grind_vector_feature_merge.py", "--features", missing, "--out", missing)
        rec2 = json.loads(missing.read_text(encoding="utf-8"))
        assert rec2["grind_vector"]["status"] == "VECTOR_UNAVAILABLE"
        assert rec2["grind_vector"]["coverage"] == 0.0
        assert rec2["grind_vector"]["vector_version"] is None
        assert rec2["inferred"]["grind_pressure"] is None
        assert rec2["inferred"]["estimated_hours_range"] is None
        assert rec2["inferred"]["grind_inference_status"] == "CALIBRATION_NOT_RUN"
        validate(rec2)

    print("fangame grind-vector Feature Store v0.5b: PASS")


if __name__ == "__main__":
    main()
