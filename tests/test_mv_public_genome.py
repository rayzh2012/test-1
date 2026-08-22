import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")


def test_mv_genome_to_public_report(tmp_path):
    game = tmp_path / "game"
    data = game / "www" / "data"
    js = game / "www" / "js"
    data.mkdir(parents=True)
    js.mkdir(parents=True)

    dump(data / "System.json", {"gameTitle": "Fixture RPG"})
    dump(data / "MapInfos.json", [None, {"id": 1, "name": "Town"}])
    dump(data / "Map001.json", {
        "width": 20,
        "height": 15,
        "encounterList": [],
        "encounterStep": 30,
        "events": [None, {
            "id": 1,
            "name": "NPC",
            "pages": [{
                "conditions": {},
                "list": [
                    {"code": 101, "parameters": ["", 0, 0, 2]},
                    {"code": 401, "parameters": ["Hello world"]},
                    {"code": 102, "parameters": [["Yes", "No"], 0, 0, 2, 0]},
                    {"code": 111, "parameters": [0, 1, 0]},
                    {"code": 201, "parameters": [0, 2, 3, 4, 2, 0]},
                    {"code": 301, "parameters": [0, 1, False, False]},
                    {"code": 302, "parameters": [0, 1, 0, 0, False]},
                    {"code": 125, "parameters": [0, 0, 100]},
                    {"code": 126, "parameters": [1, 0, 0, 1]},
                    {"code": 355, "parameters": ["console.log('fixture')"]},
                    {"code": 0, "parameters": []}
                ]
            }]
        }]
    })

    databases = {
        "Actors.json": [None, {"id": 1, "name": "Hero"}],
        "Classes.json": [None, {"id": 1, "name": "Class"}],
        "Skills.json": [None, {"id": 1, "name": "Skill"}],
        "Items.json": [None, {"id": 1, "name": "Potion", "price": 50}],
        "Weapons.json": [None, {"id": 1, "name": "Sword", "price": 1000}],
        "Armors.json": [None, {"id": 1, "name": "Armor", "price": 500}],
        "Enemies.json": [None, {"id": 1, "name": "Slime", "exp": 10, "gold": 5}],
        "Troops.json": [None, {"id": 1, "name": "Troop"}],
        "States.json": [None, {"id": 1, "name": "Poison"}],
        "CommonEvents.json": [None, {"id": 1, "name": "Common"}],
    }
    for name, payload in databases.items():
        dump(data / name, payload)

    (js / "plugins.js").write_text(
        '$plugins = ['
        '{"name":"YEP_X_DifficultySlider","status":true,"description":"","parameters":{}},'
        '{"name":"YEP_X_Autosave","status":true,"description":"","parameters":{}},'
        '{"name":"YEP_QuestJournal","status":true,"description":"","parameters":{}},'
        '{"name":"GALV_NewGamePlus","status":true,"description":"","parameters":{}},'
        '{"name":"SpeedUpToggle","status":true,"description":"","parameters":{}},'
        '{"name":"LeTBS","status":true,"description":"","parameters":{}}'
        '];',
        encoding="utf-8",
    )

    # Asset metadata should work even for encrypted MV media extensions.
    img = game / "www" / "img" / "pictures" / "fixture.rpgmvp"
    aud = game / "www" / "audio" / "bgm" / "fixture.rpgmvo"
    img.parent.mkdir(parents=True)
    aud.parent.mkdir(parents=True)
    img.write_bytes(b"encrypted-image-placeholder")
    aud.write_bytes(b"encrypted-audio-placeholder")

    identity = tmp_path / "identity.json"
    dump(identity, {
        "name": "Fixture RPG",
        "version": "1.0",
        "engine": "RPG Maker MV",
        "sources": ["https://example.invalid/fixture"],
        "file": "fixture.zip",
        "bytes": 123456,
        "sha256": "a" * 64,
    })

    genome = tmp_path / "mv_genome.json"
    normalized = tmp_path / "normalized.json"
    subprocess.run([
        sys.executable, str(ROOT / "tools" / "rpgmaker_mv_genome.py"), str(game),
        "--out", str(genome), "--normalized-out", str(normalized),
        "--identity-json", str(identity), "--game-id", "fixture-rpg",
    ], check=True)

    g = json.loads(genome.read_text(encoding="utf-8"))
    n = json.loads(normalized.read_text(encoding="utf-8"))
    o = g["observed"]
    m = n["metrics"]

    assert o["maps_loaded"] == 1
    assert o["events"] == 1
    assert o["event_pages"] == 1
    assert o["event_commands"] == 11
    assert o["dialogue_blocks"] == 1
    assert o["dialogue_lines"] == 1
    assert o["dialogue_chars"] == len("Hello world")
    assert o["choice_commands"] == 1
    assert o["choice_options"] == 2
    assert o["conditional_branches"] == 1
    assert o["transfers"] == 1
    assert o["battle_processing_calls"] == 1
    assert o["shop_processing_calls"] == 1
    assert o["reward_command_counts"]["gold"] == 1
    assert o["reward_command_counts"]["items"] == 1
    assert o["random_encounter_map_ratio"] == 0
    assert o["enemy_exp_stats"]["median"] == 10
    assert o["enemy_gold_stats"]["median"] == 5
    assert o["equipment_price_stats"]["median"] == 750
    assert o["item_price_stats"]["median"] == 50
    assert o["assets"]["encrypted_images"] == 1
    assert o["assets"]["encrypted_audio"] == 1
    assert o["plugins"]["enabled"] == 6
    assert g["system_evidence"]["difficulty_slider_plugin"] is True
    assert g["system_evidence"]["autosave_plugin"] is True
    assert g["system_evidence"]["quest_journal_plugin"] is True
    assert g["system_evidence"]["new_game_plus_plugin"] is True
    assert g["system_evidence"]["speed_up_plugin"] is True
    assert g["system_evidence"]["letbs_related_enabled_plugins"] == 1
    assert m["actors"] == 1
    assert m["common_events"] == 1
    assert n["game_id"] == "fixture-rpg"
    assert n["baseline_status"] == "REAL_ORDINARY_RPG_BASELINE_PENDING"

    # Simulate fields that can exist in the private Feature Store but must never
    # leak through the public-report whitelist.
    n["evidence_drive_id"] = "PRIVATE_DRIVE_SENTINEL_123"
    n["personal_fit_score_5"] = 4.9
    n["private_notes"] = "PRIVATE_NOTE_SENTINEL"
    normalized.write_text(json.dumps(n, ensure_ascii=False), encoding="utf-8")

    public_json = tmp_path / "public.json"
    public_md = tmp_path / "public.md"
    registry = tmp_path / "entry.json"
    subprocess.run([
        sys.executable, str(ROOT / "tools" / "fangame_public_report.py"), str(normalized),
        "--out-json", str(public_json), "--out-md", str(public_md),
        "--registry-entry-out", str(registry), "--parser-version", "fixture-parser-v1",
    ], check=True)

    pub = json.loads(public_json.read_text(encoding="utf-8"))
    ent = json.loads(registry.read_text(encoding="utf-8"))
    md = public_md.read_text(encoding="utf-8")
    serialized = json.dumps(pub, ensure_ascii=False)
    assert pub["identity"]["game_id"] == "fixture-rpg"
    assert pub["observed"]["event_commands"] == 11
    assert pub["observed"]["actors"] == 1
    assert pub["system_evidence"]["autosave_plugin"] is True
    assert pub["baseline"]["status"] == "REAL_ORDINARY_RPG_BASELINE_PENDING"
    assert pub["publication_policy"]["contains_game_binary"] is False
    assert pub["publication_policy"]["contains_private_drive_ids"] is False
    assert "PRIVATE_DRIVE_SENTINEL_123" not in serialized
    assert "PRIVATE_NOTE_SENTINEL" not in serialized
    assert "evidence_drive_id" not in pub
    assert "personal_fit_score_5" not in pub
    assert "private_notes" not in pub
    assert ent["game_id"] == "fixture-rpg"
    assert ent["baseline_status"] == "REAL_ORDINARY_RPG_BASELINE_PENDING"
    assert "Structural feature vector" in md
    assert "No production percentile" in md
