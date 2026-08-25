import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dump(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def profile(i, parser="MV_JSON", engine="RPG Maker MV", density=None):
    return {
        "schema": "fangame.normalized_profile.v0.1",
        "parser_family": parser,
        "game_id": f"g{i}",
        "title": f"Game {i}",
        "engine": engine,
        "metrics": {"maps": 10 + i, "event_commands": 1000 + i * 10, "actors": 5, "classes": 3, "skills": 20, "items": 30, "enemies": 15},
        "derived": {"events_per_map": 2.0, "event_commands_per_map": density if density is not None else 100 + i, "dialogue_chars_per_map": 200 + i, "choice_options_per_map": 1 + i / 10},
        "progression": {"random_encounter_map_ratio": 0.5, "encounter_step_median": 30, "enemy_exp_median": 20, "equipment_price_median": 500},
    }


def run_compare(tmp_path, game, rows, min_n=20):
    g = tmp_path / "game.json"; b = tmp_path / "baseline.json"; out = tmp_path / "out.json"
    dump(g, game)
    dump(b, {
        "schema": "ordinary_rpg_baseline_corpus.v0.1",
        "corpus_id": "fixture",
        "corpus_version": "0.1",
        "provenance_status": "VERIFIED",
        "measurement_contract": {"normalized_schema": "fangame.normalized_profile.v0.1", "parser_family_rule": "EXACT_MATCH", "production_percentile_min_n": min_n},
        "games": rows,
    })
    subprocess.run([sys.executable, str(ROOT / "tools" / "fangame_baseline_compare.py"), "--game", str(g), "--baseline", str(b), "--min-production-n", str(min_n), "--out", str(out)], check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def test_incompatible_parser_rejected_and_min_n_enforced(tmp_path):
    game = profile(99, density=999)
    rows = [profile(i) for i in range(20)]
    rows.append(profile(500, parser="RGSS_MARSHAL", engine="RPG Maker VX Ace"))
    out = run_compare(tmp_path, game, rows)
    assert out["compatibility"]["compatible_rows"] == 20
    assert out["compatibility"]["rejected_incompatible_rows"] == 1
    assert out["production_label_status"] == "ENABLED_FOR_SOME_METRICS"
    metric = next(x for x in out["strata"][0]["metrics"] if x["metric"] == "event_commands_per_map")
    assert metric["percentile_status"] == "PRODUCTION_ELIGIBLE"
    assert metric["percentile"] == 100.0


def test_small_corpus_is_exploratory_only(tmp_path):
    game = profile(99, density=999)
    out = run_compare(tmp_path, game, [profile(i) for i in range(3)])
    assert out["production_label_status"] == "DISABLED_INSUFFICIENT_COMPATIBLE_N"
    assert out["signals"] == []
    assert all(x["percentile_status"] == "EXPLORATORY_ONLY_INSUFFICIENT_N" for x in out["strata"][0]["metrics"])
