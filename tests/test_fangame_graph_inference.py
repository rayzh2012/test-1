#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "rpgmaker_graph_inference_v04.json"


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        inference = td / "fangame_inference.json"
        subprocess.run([
            sys.executable, str(ROOT / "tools" / "fangame_graph_inference.py"),
            "--graph", str(FIX), "--out", str(inference)
        ], cwd=ROOT, check=True)
        inf = json.loads(inference.read_text(encoding="utf-8"))

        assert inf["inference_version"] == "fangame.graph.inference.v0.4"
        side = inf["sidequests"]
        endings = inf["endings"]
        assert side["candidate_count"] == 1, side
        assert side["confidence"] == "HIGH"
        cand = side["candidates"][0]
        assert cand["maps"] == [2, 3]
        assert cand["state_keys"] == ["switch:5", "switch:6"]
        assert set(cand["evidence_node_ids"]) == {"map:2:event:10:page:0", "map:3:event:20:page:0"}
        assert "HAS_PLAYER_CHOICE" in cand["reason_codes"]
        assert "HAS_BATTLE_GATE" in cand["reason_codes"]

        assert endings["candidate_count"] == 2, endings
        assert endings["distinct_terminal_cluster_count"] == 2
        assert endings["confidence"] == "HIGH"
        nodes = {x["source_node_id"] for x in endings["candidates"]}
        assert nodes == {"map:4:event:30:page:0", "map:4:event:30:page:1"}
        for x in endings["candidates"]:
            assert "RETURN_TO_TITLE" in x["reason_codes"]
            assert "TERMINAL_TEXT" in x["reason_codes"]
            assert "CONDITIONAL_TERMINAL_PATH" in x["reason_codes"]
            assert x["source_map_id"] == 4

        # Merge into a minimal v0.3 feature record and validate v0.4 schema.
        features = td / "fangame_features.json"
        features.write_text(json.dumps({
            "schema_version": "fangame.features.v0.3",
            "domain": "fangame",
            "identity": {"title": "Inference Fixture", "archive_filename": "fixture.rar"},
            "observed": {}, "runtime": {}, "derived": {},
            "inferred": {"sidequest_confidence": "UNKNOWN", "ending_confidence": "UNKNOWN", "inference_version": "none.v0.2"},
            "ranking": {},
            "graph": {"status": "GRAPH_OBSERVED", "graph_version": "rpgmaker.graph.v0.3", "start_map_id": 1, "summary": {}},
            "evidence": {},
            "audit": {
                "generated_at_utc": "2026-08-18T00:00:00+00:00",
                "feature_emitter_version": "0.3.0",
                "graph_bridge_version": "0.3.0"
            }
        }), encoding="utf-8")
        subprocess.run([
            sys.executable, str(ROOT / "tools" / "fangame_inference_feature_merge.py"),
            "--features", str(features), "--inference", str(inference), "--out", str(features)
        ], cwd=ROOT, check=True)
        rec = json.loads(features.read_text(encoding="utf-8"))
        assert rec["schema_version"] == "fangame.features.v0.4"
        assert rec["inferred"]["sidequest_candidate_count"] == 1
        assert rec["inferred"]["ending_candidate_count"] == 2
        assert len(rec["inferred"]["sidequest_candidates"]) == 1
        assert len(rec["inferred"]["ending_candidates"]) == 2
        assert rec["evidence"]["inference_report"] == "fangame_inference.json"
        assert rec["audit"]["pre_inference_feature_version"] == "fangame.features.v0.3"
        assert rec["audit"]["inference_version"] == "fangame.graph.inference.v0.4"

        import jsonschema
        schema = json.loads((ROOT / "schemas" / "fangame_features_v04.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(rec, schema)

    print("fangame graph inference regression: PASS")


if __name__ == "__main__":
    main()
