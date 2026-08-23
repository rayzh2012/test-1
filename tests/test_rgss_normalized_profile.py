import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dump(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def run_normalizer(tmp_path, static_obj, *, target_engine="RPG Maker VX Ace"):
    package = tmp_path / "fixture_rgss.zip"
    package.write_bytes(b"rgss-fixture-payload")
    static = tmp_path / "static.json"
    dump(static, static_obj)
    dialogue = tmp_path / "dialogue.json"
    dump(dialogue, {"summary": {"dialogue_blocks": 17, "dialogue_lines": 20, "dialogue_chars": 500}})
    graph = tmp_path / "graph.json"
    dump(graph, {"summary": {"map_nodes": 3, "transfer_edges": 6}})
    inference = tmp_path / "inference.json"
    dump(inference, {"summary": {"sidequest_candidate_maps": 2, "explicit_sidequest_maps": 1, "optional_content_maps": 2, "ending_candidate_maps": 1, "release_completion_status": "COMPLETE_OR_UNKNOWN"}})
    target = tmp_path / "target.json"
    dump(target, {"game_id": "fixture-rgss", "name": "Fixture RGSS", "version": "1.2", "engine": target_engine, "sources": ["https://example.invalid/rgss"]})
    out = tmp_path / "normalized.json"
    proc = subprocess.run([
        sys.executable, str(ROOT / "tools" / "fangame_normalized_profile.py"),
        "--static", str(static), "--package", str(package), "--out", str(out),
        "--target-json", str(target), "--dialogue-corpus", str(dialogue),
        "--map-graph", str(graph), "--content-inference", str(inference),
    ], text=True, capture_output=True)
    return proc, out


def valid_static():
    return {
        "engine": "RPG Maker VX Ace",
        "map_count": 3,
        "image_count": 12,
        "audio_count": 7,
        "marshal_content": {
            "marshal_probe": True,
            "maps_loaded": 3,
            "events": 9,
            "event_pages": 12,
            "event_commands": 120,
            "dialogue_lines": 20,
            "dialogue_chars": 500,
            "choice_options": 8,
            "map_transfers": 6,
            "battle_calls": 5,
            "shop_calls": 2,
            "common_events": 4,
            "actors": 6,
            "classes": 3,
            "skills": 40,
            "items": 30,
            "weapons": 10,
            "armors": 8,
            "enemies": 20,
            "troops": 15,
            "states": 12,
        },
        "graph_evidence": {
            "graph_probe": True,
            "summary": {"conditional_branch_nodes": 11},
        },
        "progression_evidence": {
            "progression_probe": True,
            "summary": {
                "random_encounter_map_ratio": 0.3333333333,
                "encounter_step_stats": {"median": 40},
                "enemy_exp_stats": {"median": 25},
                "enemy_gold_stats": {"median": 8},
                "equipment_price_stats": {"median": 900},
            },
        },
    }


def test_rgss_static_to_normalized_profile(tmp_path):
    proc, out = run_normalizer(tmp_path, valid_static())
    assert proc.returncode == 0, proc.stderr or proc.stdout

    p = json.loads(out.read_text(encoding="utf-8"))
    assert p["schema"] == "fangame.normalized_profile.v0.1"
    assert p["parser_family"] == "RGSS_MARSHAL"
    assert p["game_id"] == "fixture-rgss"
    assert p["title"] == "Fixture RGSS"
    assert p["metrics"]["maps"] == 3
    assert p["metrics"]["events"] == 9
    assert p["metrics"]["dialogue_blocks"] == 17
    assert p["metrics"]["conditional_branches"] == 11
    assert p["derived"]["event_commands_per_map"] == 40
    assert p["derived"]["dialogue_chars_per_map"] == 500 / 3
    assert p["progression"]["encounter_step_median"] == 40
    assert p["progression"]["enemy_exp_median"] == 25
    assert p["system_evidence"]["rgss_marshal_probe"] is True
    assert p["analysis_evidence"]["explicit_sidequest_maps"] == 1
    assert p["baseline_status"] == "REAL_ORDINARY_RPG_BASELINE_PENDING"
    assert "enabled_plugins" not in p["metrics"]  # UNKNOWN must not become zero.


def test_unknown_layout_cannot_be_upgraded_by_target_metadata(tmp_path):
    st = valid_static()
    st["engine"] = "UNKNOWN"
    st["marshal_content"] = {}
    proc, out = run_normalizer(tmp_path, st, target_engine="RPG Maker XP")
    assert proc.returncode != 0
    assert not out.exists()
    assert "static engine/layout is 'UNKNOWN'" in (proc.stderr + proc.stdout)


def test_rgss_without_loaded_marshal_maps_is_rejected(tmp_path):
    st = valid_static()
    st["engine"] = "RPG Maker XP"
    st["marshal_content"] = {"marshal_probe": True, "maps_loaded": 0}
    proc, out = run_normalizer(tmp_path, st, target_engine="RPG Maker XP")
    assert proc.returncode != 0
    assert not out.exists()
    assert "did not successfully load at least one map" in (proc.stderr + proc.stdout)
