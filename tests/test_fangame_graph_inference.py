#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "rpgmaker_graph_inference_v04.json"
FALSE_POSITIVE = ROOT / "tests" / "fixtures" / "rpgmaker_graph_inference_v041_false_positive.json"


def run_inference(graph_path, out_path):
    subprocess.run([
        sys.executable, str(ROOT / "tools" / "fangame_graph_inference.py"),
        "--graph", str(graph_path), "--out", str(out_path)
    ], cwd=ROOT, check=True)
    return json.loads(out_path.read_text(encoding="utf-8"))


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        inference = td / "fangame_inference.json"
        inf = run_inference(FIX, inference)

        assert inf["inference_version"] == "fangame.graph.inference.v0.4.1"
        optional = inf["optional_clusters"]
        side = inf["sidequests"]
        endings = inf["endings"]

        assert optional["candidate_count"] == 1, optional
        assert optional["confidence"] == "HIGH"
        opt = optional["candidates"][0]
        assert opt["maps"] == [2, 3]
        assert opt["state_keys"] == ["switch:5", "switch:6"]
        assert set(opt["evidence_node_ids"]) == {"map:2:event:10:page:0", "map:3:event:20:page:0"}
        assert "HAS_PLAYER_CHOICE" in opt["reason_codes"]
        assert "HAS_BATTLE_GATE" in opt["reason_codes"]

        assert side["candidate_count"] == 1, side
        assert side["confidence"] == "HIGH"
        assert side["unpromoted_optional_cluster_count"] == 0
        cand = side["candidates"][0]
        assert cand["maps"] == [2, 3]
        assert cand["state_keys"] == ["switch:5", "switch:6"]
        assert set(cand["evidence_node_ids"]) == {"map:2:event:10:page:0", "map:3:event:20:page:0"}
        assert "TASK_TEXT_SIGNAL" in cand["reason_codes"]
        assert "REWARD_TEXT_SIGNAL" in cand["reason_codes"]
        assert cand["source_optional_candidate_id"] == "optional:1"
        assert cand["semantic_signal_samples"]

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

        # A puzzle/combat state machine can be optional without being a quest.
        false_out = td / "false_positive_inference.json"
        false_inf = run_inference(FALSE_POSITIVE, false_out)
        assert false_inf["optional_clusters"]["candidate_count"] == 1, false_inf
        assert false_inf["sidequests"]["candidate_count"] == 0, false_inf
        assert false_inf["sidequests"]["unpromoted_optional_cluster_count"] == 1
        assert false_inf["sidequests"]["confidence"] == "LOW"

        # Merge into a minimal v0.3 feature record and validate the compatible v0.4 schema.
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
        assert rec["inferred"]["optional_cluster_candidate_count"] == 1
        assert rec["inferred"]["optional_cluster_confidence"] == "HIGH"
        assert rec["inferred"]["sidequest_candidate_count"] == 1
        assert rec["inferred"]["unpromoted_optional_cluster_count"] == 0
        assert rec["inferred"]["ending_candidate_count"] == 2
        assert len(rec["inferred"]["optional_cluster_candidates"]) == 1
        assert len(rec["inferred"]["sidequest_candidates"]) == 1
        assert len(rec["inferred"]["ending_candidates"]) == 2
        assert rec["evidence"]["inference_report"] == "fangame_inference.json"
        assert rec["audit"]["pre_inference_feature_version"] == "fangame.features.v0.3"
        assert rec["audit"]["schema_merge_version"] == "0.4.1"
        assert rec["audit"]["inference_version"] == "fangame.graph.inference.v0.4.1"

        import jsonschema
        schema = json.loads((ROOT / "schemas" / "fangame_features_v04.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(rec, schema)

    print("fangame graph inference v0.4.1 regression: PASS")


if __name__ == "__main__":
    main()
