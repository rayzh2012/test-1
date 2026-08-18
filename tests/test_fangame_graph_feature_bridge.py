#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        features = td / "fangame_features.json"
        graph = td / "rpgmaker_graph.json"

        features.write_text(json.dumps({
            "schema_version": "fangame.features.v0.2",
            "domain": "fangame",
            "identity": {"title": "Graph Fixture", "archive_filename": "fixture.rar", "game_id": "sha256:test"},
            "observed": {}, "runtime": {}, "derived": {},
            "inferred": {"sidequest_confidence": "UNKNOWN", "ending_confidence": "UNKNOWN"},
            "ranking": {},
            "evidence": {"screenshots": []},
            "audit": {"generated_at_utc": "2026-08-18T00:00:00+00:00", "feature_emitter_version": "0.2.1"}
        }, ensure_ascii=False), encoding="utf-8")

        graph.write_text(json.dumps({
            "graph_version": "rpgmaker.graph.v0.3",
            "summary": {
                "maps_loaded": 2,
                "event_page_nodes": 3,
                "common_event_nodes": 1,
                "direct_map_edges": 2,
                "variable_map_edges": 0,
                "unique_direct_map_pairs": 2,
                "weak_component_count": 1,
                "largest_component_maps": 2,
                "isolated_maps_by_direct_transfer": 0,
                "maps_without_direct_outgoing": 0,
                "maps_without_direct_incoming": 0,
                "conditional_branch_nodes": 1,
                "choice_nodes": 1,
                "common_event_call_edges": 1,
                "battle_call_nodes": 1,
                "shop_call_nodes": 1,
                "switch_read_ids": 2,
                "switch_write_ids": 1,
                "variable_read_ids": 1,
                "variable_write_ids": 1,
                "local_switch_ids": 1,
                "shared_switch_ids": 1,
                "local_variable_ids": 1,
                "shared_variable_ids": 0,
                "terminal_signal_nodes": 1,
                "terminal_signals_by_type": {"return_to_title": 1},
                "label_nodes": 1,
                "label_jump_nodes": 1,
                "start_map_id": 1,
                "load_error_count": 0
            }
        }, ensure_ascii=False), encoding="utf-8")

        subprocess.run([
            sys.executable, str(ROOT / "tools" / "fangame_graph_feature_merge.py"),
            "--features", str(features), "--graph", str(graph), "--out", str(features)
        ], cwd=ROOT, check=True)

        rec = json.loads(features.read_text(encoding="utf-8"))
        assert rec["schema_version"] == "fangame.features.v0.3"
        assert rec["graph"]["status"] == "GRAPH_OBSERVED"
        assert rec["graph"]["graph_version"] == "rpgmaker.graph.v0.3"
        assert rec["graph"]["start_map_id"] == 1
        assert rec["graph"]["summary"]["direct_map_edges"] == 2
        assert rec["graph"]["summary"]["terminal_signal_nodes"] == 1
        assert rec["evidence"]["graph_report"] == "rpgmaker_graph.json"
        assert rec["audit"]["base_feature_emitter_version"] == "0.2.1"
        assert rec["audit"]["feature_emitter_version"] == "0.3.0"
        assert rec["audit"]["graph_bridge_version"] == "0.3.0"

        import jsonschema
        schema = json.loads((ROOT / "schemas" / "fangame_features_v03.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(rec, schema)

        # Missing graph remains a valid explicit uncertainty state.
        no_graph = td / "no_graph.json"
        no_graph.write_text(json.dumps({
            "schema_version": "fangame.features.v0.2", "domain": "fangame",
            "identity": {"title": "Opaque Fixture", "archive_filename": "opaque.rgss2a"},
            "observed": {}, "runtime": {}, "derived": {}, "inferred": {}, "ranking": {},
            "evidence": {"screenshots": []},
            "audit": {"generated_at_utc": "2026-08-18T00:00:00+00:00", "feature_emitter_version": "0.2.1"}
        }), encoding="utf-8")
        subprocess.run([
            sys.executable, str(ROOT / "tools" / "fangame_graph_feature_merge.py"),
            "--features", str(no_graph), "--out", str(no_graph)
        ], cwd=ROOT, check=True)
        rec2 = json.loads(no_graph.read_text(encoding="utf-8"))
        assert rec2["graph"]["status"] == "GRAPH_UNAVAILABLE"
        jsonschema.validate(rec2, schema)

    print("fangame graph feature bridge regression: PASS")


if __name__ == "__main__":
    main()
