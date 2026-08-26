#!/usr/bin/env python3
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "evidence_feature_compare.py"
POLICY = ROOT / "policies" / "fangame_compare_v06.json"


def rec(game_id, title, maps, commands, dialogue, ai, ci, hist, fit, encounter=0.5):
    return {
        "identity": {"game_id": game_id, "title": title},
        "observed": {
            "maps": maps,
            "event_commands": commands,
            "dialogue_lines": dialogue,
            "common_events": 40,
        },
        "derived": {
            "choice_density_per_1000_commands": 20.0,
            "transfer_density_per_map": 3.0,
        },
        "graph": {"summary": {"unique_direct_map_pairs": 90, "conditional_branch_nodes": 70}},
        "inferred": {"optional_cluster_candidate_count": 8, "ending_candidate_count": 2},
        "grind_vector": {"features": {
            "random_encounter_map_ratio": encounter,
            "encounter_checks_proxy_per_100_steps": 3.5,
            "log1p_equipment_price_to_enemy_gold_ratio": 2.0,
            "positive_reward_ops_per_1000_event_commands": 5.0,
            "battle_processing_ops_per_100_maps": 8.0,
        }},
        "ranking": {
            "ai_structural_score_5": ai,
            "ci_playability_score_5": ci,
            "historical_rating_5": hist,
            "personal_fit_score_5": fit,
        },
    }


def main():
    a = rec("A", "Alpha", 100, 10000, 3000, 4.8, 4.8, 4.5, 4.9)
    b = rec("B", "Beta", 100, 10000, 3000, 4.2, 4.2, 4.0, 4.3)
    c = rec("C", "Gamma", 12, 700, 100, 2.0, 2.5, 2.0, 1.5, encounter=0.05)
    c["observed"]["common_events"] = 2
    c["derived"]["choice_density_per_1000_commands"] = 1.0
    c["derived"]["transfer_density_per_map"] = 0.4
    c["graph"]["summary"] = {"unique_direct_map_pairs": 5, "conditional_branch_nodes": 2}
    c["inferred"] = {"optional_cluster_candidate_count": 0, "ending_candidate_count": 1}
    c["grind_vector"]["features"].update({
        "encounter_checks_proxy_per_100_steps": 0.5,
        "log1p_equipment_price_to_enemy_gold_ratio": 0.2,
        "positive_reward_ops_per_1000_event_commands": 0.2,
        "battle_processing_ops_per_100_maps": 1.0,
    })

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        ndjson = td / "records.ndjson"
        ndjson.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in (a, b, c)) + "\n", encoding="utf-8")
        outj = td / "compare.json"
        outc = td / "compare.csv"
        subprocess.run([
            sys.executable, str(TOOL), "--records", str(ndjson), "--policy", str(POLICY),
            "--out-json", str(outj), "--out-csv", str(outc)
        ], cwd=ROOT, check=True)

        result = json.loads(outj.read_text(encoding="utf-8"))
        assert result["engine_version"] == "evidence.feature.compare.v0.6"
        assert result["policy_version"] == "fangame.compare.v0.6"
        assert result["record_count"] == 3
        by_id = {x["id"]: x for x in result["objects"]}

        assert by_id["A"]["nearest_neighbors"][0]["id"] == "B"
        assert by_id["B"]["nearest_neighbors"][0]["id"] == "A"
        assert by_id["A"]["nearest_neighbors"][0]["similarity"] > 0.9
        assert by_id["A"]["cluster_id"] == by_id["B"]["cluster_id"]
        assert by_id["C"]["cluster_id"] != by_id["A"]["cluster_id"]
        assert by_id["C"]["anomaly_score"] > by_id["A"]["anomaly_score"]

        assert by_id["A"]["rank"] == 1
        assert by_id["A"]["ranking"]["score_5"] > by_id["B"]["ranking"]["score_5"] > by_id["C"]["ranking"]["score_5"]
        contrib_paths = {x["path"] for x in by_id["A"]["ranking"]["contributions"]}
        assert "ranking.ai_structural_score_5" in contrib_paths
        assert "ranking.ci_playability_score_5" in contrib_paths
        assert not any("grind_vector" in p for p in contrib_paths), "uncalibrated grind vector leaked into ranking"

        rows = list(csv.DictReader(outc.open(encoding="utf-8-sig")))
        assert len(rows) == 3
        assert rows[0]["id"] == "A"
        assert rows[0]["nearest_peer"] == "Beta"

    print("evidence feature compare regression: PASS")


if __name__ == "__main__":
    main()
