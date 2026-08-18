#!/usr/bin/env python3
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "fangame_nlzj3_feature_v02"


def run(*cmd):
    subprocess.run([str(x) for x in cmd], cwd=ROOT, check=True)


def main():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        recdir = td / "records" / "nlzj3"
        recdir.mkdir(parents=True)
        record_path = recdir / "fangame_features.json"

        run(
            sys.executable, ROOT / "tools" / "fangame_feature_emitter.py",
            "--fetch", FIX / "fetch_report.json",
            "--static", FIX / "playability_static.json",
            "--smoke", FIX / "playability_smoke.json",
            "--review", FIX / "fangame_review_card.json",
            "--sha256", FIX / "SHA256.txt",
            "--out", record_path,
        )
        record = json.loads(record_path.read_text(encoding="utf-8"))

        assert record["schema_version"] == "fangame.features.v0.2"
        ident = record["identity"]
        assert ident["game_id"] == "sha256:761ea5dd2510ee04658751865a827f6a8a4ae644270d094a7ebd21963919c5c1"
        assert ident["title"] == "怒龙战记3｜962旧镜像系谱"
        assert ident["version"] == "2011-12 / 199-246MB lineage"
        assert ident["engine"] == "RPG Maker VX"
        assert ident["archive_filename"] == "nlzj3.rar"
        assert ident["package_bytes"] == 248760932
        assert ident["sha256"] == "761ea5dd2510ee04658751865a827f6a8a4ae644270d094a7ebd21963919c5c1"
        assert ident["source"] == "https://99dj.197784.com/9dj2/nlzj3.rar"
        assert "https://99dj.197784.com/9dj2/nulongzhanji3.rar" in ident["source_candidates"]

        obs = record["observed"]
        expected = {
            "maps": 140, "events": 1427, "event_pages": 1815,
            "event_commands": 15837, "dialogue_lines": 4778,
            "choices": 440, "common_events": 190, "transfers": 490,
            "battle_calls": 21, "shops": 13, "switches": 27,
            "variables": 22, "actors": 100, "classes": 50,
            "skills": 150, "items": 210, "weapons": 60,
            "armors": 60, "enemies": 90, "troops": 130, "states": 16,
            "image_count": 812, "audio_count": 466,
        }
        for key, value in expected.items():
            assert obs[key] == value, (key, obs[key], value)

        assert record["runtime"]["mechanical_status"] == "GAMEPLAY_LIKELY"
        assert record["runtime"]["title_verified"] is None
        assert record["runtime"]["new_game_verified"] is None
        assert record["runtime"]["map_gameplay_verified"] is None
        assert record["runtime"]["semantic_review_state"] == "PENDING_SCREENSHOT_SEMANTIC_REVIEW"

        assert record["derived"]["dialogue_density_per_map"] == round(4778 / 140, 4)
        assert record["derived"]["event_command_density_per_map"] == round(15837 / 140, 4)
        assert record["derived"]["choice_density_per_1000_commands"] == round(440 / 15837 * 1000, 4)
        assert record["derived"]["transfer_density_per_map"] == round(490 / 140, 4)
        assert record["derived"]["asset_count"] == 1278
        assert record["derived"]["system_object_count"] == 1096
        assert record["derived"]["content_richness_score_5"] == 4.72
        assert record["inferred"]["sidequest_confidence"] == "UNKNOWN"
        assert record["inferred"]["ending_confidence"] == "UNKNOWN"
        assert record["audit"]["feature_emitter_version"] == "0.2.1"

        # Schema validation is optional locally but mandatory when jsonschema is available in CI.
        try:
            import jsonschema
        except ImportError:
            pass
        else:
            schema = json.loads((ROOT / "schemas" / "fangame_features.schema.json").read_text(encoding="utf-8"))
            jsonschema.validate(record, schema)

        ndjson = td / "store.ndjson"
        csv_path = td / "store.csv"
        run(sys.executable, ROOT / "tools" / "fangame_feature_batch.py", td / "records", "--ndjson", ndjson, "--csv", csv_path)
        lines = [x for x in ndjson.read_text(encoding="utf-8").splitlines() if x.strip()]
        assert len(lines) == 1
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
        assert len(rows) == 1
        assert rows[0]["identity.title"] == "怒龙战记3｜962旧镜像系谱"
        assert rows[0]["observed.maps"] == "140"
        assert rows[0]["identity.source"] == "https://99dj.197784.com/9dj2/nlzj3.rar"

    print("fangame feature-store regression: PASS")


if __name__ == "__main__":
    main()
