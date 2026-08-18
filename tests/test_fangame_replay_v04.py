#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "fangame_nlzj3_feature_v02"


def run(*args):
    subprocess.run([str(x) for x in args], cwd=ROOT, check=True)


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        features = td / "fangame_features.json"

        # Replay the real legacy NLZJ3 evidence bundle without a game binary.
        run(
            sys.executable, ROOT / "tools" / "fangame_feature_emitter.py",
            "--fetch", FIX / "fetch_report.json",
            "--static", FIX / "playability_static.json",
            "--smoke", FIX / "playability_smoke.json",
            "--review", FIX / "fangame_review_card.json",
            "--sha256", FIX / "SHA256.txt",
            "--out", features,
        )

        # This historical evidence predates graph collection. v0.3 must preserve that boundary.
        run(
            sys.executable, ROOT / "tools" / "fangame_graph_feature_merge.py",
            "--features", features,
            "--out", features,
        )

        # No graph means no inference report. v0.4 must stay UNKNOWN rather than inventing counts.
        run(
            sys.executable, ROOT / "tools" / "fangame_inference_feature_merge.py",
            "--features", features,
            "--out", features,
        )

        rec = json.loads(features.read_text(encoding="utf-8"))
        assert rec["schema_version"] == "fangame.features.v0.4"
        assert rec["identity"]["archive_filename"] == "nlzj3.rar"
        assert rec["identity"]["sha256"] == "761ea5dd2510ee04658751865a827f6a8a4ae644270d094a7ebd21963919c5c1"
        assert rec["observed"]["maps"] == 140
        assert rec["observed"]["event_commands"] == 15837
        assert rec["graph"]["status"] == "GRAPH_UNAVAILABLE"
        assert rec["graph"]["graph_version"] is None
        assert rec["inferred"]["sidequest_candidate_count"] is None
        assert rec["inferred"]["sidequest_confidence"] == "UNKNOWN"
        assert rec["inferred"]["ending_candidate_count"] is None
        assert rec["inferred"]["ending_confidence"] == "UNKNOWN"
        assert rec["inferred"]["inference_version"] == "none.v0.4"
        assert rec["evidence"]["graph_report"] is None
        assert rec["evidence"]["inference_report"] is None
        assert rec["audit"]["base_feature_emitter_version"] == "0.2.1"
        assert rec["audit"]["pre_inference_feature_version"] == "fangame.features.v0.3"

        import jsonschema
        schema = json.loads((ROOT / "schemas" / "fangame_features_v04.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(rec, schema)

    print("legacy NLZJ3 evidence replay to v0.4: PASS")


if __name__ == "__main__":
    main()
