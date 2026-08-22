#!/usr/bin/env python3
"""Deep static genome parser for inspectable RPG Maker MV/MZ JSON projects.

Reads only project/package data already available to the caller. It does not
attempt to decrypt media assets. JSON event/database structure remains fully
observable even when .rpgmvp/.rpgmvo media are encrypted.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path

SCHEMA = "fangame.mv.genome.v0.1"
NORMALIZED_SCHEMA = "fangame.normalized_profile.v0.1"


def load_json(path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return default


def stats(values):
    vals = sorted(float(x) for x in values if x is not None)
    if not vals:
        return {"n": 0, "min": None, "median": None, "mean": None, "max": None}
    n = len(vals)
    mid = n // 2
    med = vals[mid] if n % 2 else (vals[mid - 1] + vals[mid]) / 2
    return {"n": n, "min": vals[0], "median": med, "mean": sum(vals) / n, "max": vals[-1]}


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def slugify(text):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s or "unknown-game"


def locate(root):
    candidates = [
        (root / "www" / "data", root / "www" / "js" / "plugins.js", root / "www"),
        (root / "data", root / "js" / "plugins.js", root),
    ]
    for data, plugins, base in candidates:
        if (data / "System.json").exists():
            return data, plugins, base
    raise SystemExit("No RPG Maker MV/MZ JSON data directory found")


def iter_commands(page):
    for cmd in (page or {}).get("list", []) or []:
        if isinstance(cmd, dict):
            yield cmd


def parse_plugins(path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig", errors="ignore")
    m = re.search(r"\$plugins\s*=\s*(\[.*?\])\s*;", text, re.S)
    if not m:
        return []
    try:
        arr = json.loads(m.group(1))
        return arr if isinstance(arr, list) else []
    except Exception:
        return []


def count_assets(base):
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".rpgmvp", ".png_"}
    audio_exts = {".ogg", ".m4a", ".wav", ".mp3", ".rpgmvo", ".rpgmvm"}
    out = {"image_count_including_encrypted": 0, "image_bytes": 0,
           "audio_count_including_encrypted": 0, "audio_bytes": 0,
           "js_count": 0, "js_bytes": 0, "encrypted_images": 0, "encrypted_audio": 0}
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        if ext in image_exts:
            out["image_count_including_encrypted"] += 1
            out["image_bytes"] += size
            if ext == ".rpgmvp":
                out["encrypted_images"] += 1
        if ext in audio_exts:
            out["audio_count_including_encrypted"] += 1
            out["audio_bytes"] += size
            if ext in {".rpgmvo", ".rpgmvm"}:
                out["encrypted_audio"] += 1
        if ext == ".js":
            out["js_count"] += 1
            out["js_bytes"] += size
    return out


def db_count(data, name):
    arr = load_json(data / name, []) or []
    if not isinstance(arr, list):
        return 0
    return sum(1 for x in arr if x is not None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("game_root")
    ap.add_argument("--out", required=True)
    ap.add_argument("--normalized-out")
    ap.add_argument("--identity-json")
    ap.add_argument("--package")
    ap.add_argument("--game-id")
    ap.add_argument("--title")
    ap.add_argument("--version")
    ap.add_argument("--engine")
    ap.add_argument("--source-url")
    args = ap.parse_args()

    root = Path(args.game_root).resolve()
    data_dir, plugins_path, base = locate(root)
    system = load_json(data_dir / "System.json", {}) or {}
    map_infos = load_json(data_dir / "MapInfos.json", []) or []
    map_ids = [i for i, x in enumerate(map_infos) if i and x]
    if not map_ids:
        map_ids = sorted(int(m.group(1)) for p in data_dir.glob("Map*.json")
                         if (m := re.fullmatch(r"Map(\d+)\.json", p.name, re.I)))

    obs = {
        "maps_loaded": 0, "maps_with_events": 0, "events": 0, "event_pages": 0,
        "event_commands": 0, "dialogue_blocks": 0, "dialogue_lines": 0,
        "dialogue_chars": 0, "choice_commands": 0, "choice_options": 0,
        "conditional_branches": 0, "script_commands": 0, "script_chars": 0,
        "transfers": 0, "battle_processing_calls": 0, "shop_processing_calls": 0,
        "maps_with_random_encounters": 0, "encounter_troop_entries": 0,
        "event_command_code_counts": {},
        "reward_command_counts": {"gold": 0, "items": 0, "weapons": 0, "armors": 0,
                                  "exp": 0, "level": 0, "skills": 0, "recover_all": 0},
    }
    encounter_steps = []
    map_tiles = []

    reward_codes = {125: "gold", 126: "items", 127: "weapons", 128: "armors",
                    315: "exp", 316: "level", 318: "skills", 314: "recover_all"}

    for mid in map_ids:
        mp = load_json(data_dir / f"Map{mid:03d}.json", None)
        if not isinstance(mp, dict):
            continue
        obs["maps_loaded"] += 1
        width, height = mp.get("width"), mp.get("height")
        if isinstance(width, int) and isinstance(height, int):
            map_tiles.append(width * height)
        encounters = mp.get("encounterList") or []
        if encounters:
            obs["maps_with_random_encounters"] += 1
            obs["encounter_troop_entries"] += len(encounters)
            step = mp.get("encounterStep")
            if isinstance(step, (int, float)) and step > 0:
                encounter_steps.append(step)
        events = mp.get("events") or []
        map_has_events = False
        for ev in events:
            if not isinstance(ev, dict):
                continue
            map_has_events = True
            obs["events"] += 1
            for page in ev.get("pages", []) or []:
                if not isinstance(page, dict):
                    continue
                obs["event_pages"] += 1
                for cmd in iter_commands(page):
                    code = int(cmd.get("code", 0) or 0)
                    params = cmd.get("parameters") or []
                    obs["event_commands"] += 1
                    k = str(code)
                    obs["event_command_code_counts"][k] = obs["event_command_code_counts"].get(k, 0) + 1
                    if code == 101:
                        obs["dialogue_blocks"] += 1
                    elif code == 401:
                        obs["dialogue_lines"] += 1
                        if params:
                            obs["dialogue_chars"] += len(str(params[0]))
                    elif code == 102:
                        obs["choice_commands"] += 1
                        if params and isinstance(params[0], list):
                            obs["choice_options"] += len(params[0])
                    elif code == 111:
                        obs["conditional_branches"] += 1
                    elif code in (355, 655):
                        obs["script_commands"] += 1
                        if params:
                            obs["script_chars"] += len(str(params[0]))
                    elif code == 201:
                        obs["transfers"] += 1
                    elif code == 301:
                        obs["battle_processing_calls"] += 1
                    elif code == 302:
                        obs["shop_processing_calls"] += 1
                    if code in reward_codes:
                        obs["reward_command_counts"][reward_codes[code]] += 1
        if map_has_events:
            obs["maps_with_events"] += 1

    obs["random_encounter_map_ratio"] = (obs["maps_with_random_encounters"] / obs["maps_loaded"]
                                           if obs["maps_loaded"] else None)
    obs["encounter_step_stats"] = stats(encounter_steps)
    obs["map_tile_stats"] = stats(map_tiles)

    enemies = load_json(data_dir / "Enemies.json", []) or []
    enemy_exp, enemy_gold = [], []
    for x in enemies:
        if isinstance(x, dict):
            if isinstance(x.get("exp"), (int, float)): enemy_exp.append(x["exp"])
            if isinstance(x.get("gold"), (int, float)): enemy_gold.append(x["gold"])
    obs["enemy_exp_stats"] = stats(enemy_exp)
    obs["enemy_gold_stats"] = stats(enemy_gold)

    equipment_prices = []
    for fn in ("Weapons.json", "Armors.json"):
        for x in load_json(data_dir / fn, []) or []:
            if isinstance(x, dict) and isinstance(x.get("price"), (int, float)) and x["price"] > 0:
                equipment_prices.append(x["price"])
    item_prices = [x.get("price") for x in (load_json(data_dir / "Items.json", []) or [])
                   if isinstance(x, dict) and isinstance(x.get("price"), (int, float)) and x["price"] > 0]
    obs["equipment_price_stats"] = stats(equipment_prices)
    obs["item_price_stats"] = stats(item_prices)

    db_files = {
        "actors": "Actors.json", "classes": "Classes.json", "skills": "Skills.json",
        "items": "Items.json", "weapons": "Weapons.json", "armors": "Armors.json",
        "enemies": "Enemies.json", "troops": "Troops.json", "states": "States.json",
        "common_events": "CommonEvents.json",
    }
    obs["database"] = {k: db_count(data_dir, v) for k, v in db_files.items()}
    obs["assets"] = count_assets(base)

    plugins = parse_plugins(plugins_path)
    enabled_names = [str(x.get("name", "")) for x in plugins if isinstance(x, dict) and x.get("status")]
    obs["plugins"] = {"total": len(plugins), "enabled": len(enabled_names), "enabled_names": enabled_names}
    lower_names = [x.lower() for x in enabled_names]
    letbs_count = sum(1 for x in lower_names if "letbs" in x or re.search(r"(^|_)tbs($|_)", x))

    maps = obs["maps_loaded"] or 1
    derived = {
        "events_per_map": obs["events"] / maps,
        "event_commands_per_map": obs["event_commands"] / maps,
        "dialogue_chars_per_map": obs["dialogue_chars"] / maps,
        "dialogue_chars_per_event": (obs["dialogue_chars"] / obs["events"] if obs["events"] else None),
        "choice_options_per_map": obs["choice_options"] / maps,
        "conditional_branches_per_map": obs["conditional_branches"] / maps,
        "transfers_per_map": obs["transfers"] / maps,
        "battle_calls_per_map": obs["battle_processing_calls"] / maps,
        "shops_per_100_maps": obs["shop_processing_calls"] / maps * 100,
        "maps_with_events_ratio": obs["maps_with_events"] / maps,
    }

    def has_plugin(*needles):
        return any(any(n.lower() in name for n in needles) for name in lower_names)

    system_evidence = {
        "difficulty_slider_plugin": has_plugin("difficultyslider", "choixdifficulte"),
        "autosave_plugin": has_plugin("autosave"),
        "quest_journal_plugin": has_plugin("questjournal"),
        "new_game_plus_plugin": has_plugin("newgameplus", "ngplus"),
        "speed_up_plugin": has_plugin("speeduptoggle", "speedup"),
        "letbs_related_enabled_plugins": letbs_count,
    }

    signals = []
    if derived["event_commands_per_map"] >= 300: signals.append("VERY_HIGH_EVENT_SCRIPTING_DENSITY")
    if obs["random_encounter_map_ratio"] is not None and obs["random_encounter_map_ratio"] <= 0.05: signals.append("LOW_RANDOM_ENCOUNTER_COVERAGE")
    if len(enabled_names) >= 100: signals.append("VERY_HIGH_PLUGIN_SYSTEM_BREADTH")

    identity = {}
    if args.identity_json:
        identity = load_json(Path(args.identity_json), {}) or {}
    package = Path(args.package).resolve() if args.package else None
    package_bytes = identity.get("bytes")
    package_sha = identity.get("sha256")
    archive_name = identity.get("file")
    if package and package.exists():
        archive_name = archive_name or package.name
        package_bytes = package_bytes or package.stat().st_size
        package_sha = package_sha or sha256(package)
    title = args.title or identity.get("name") or root.name
    version = args.version or identity.get("version") or "UNKNOWN"
    engine = args.engine or identity.get("engine") or ("RPG Maker MZ" if (base / "js" / "rmmz_core.js").exists() else "RPG Maker MV")
    source_url = args.source_url or (identity.get("sources") or [None])[0]
    game_id = args.game_id or slugify(f"{title}-{version}")

    genome = {
        "schema": SCHEMA,
        "observed": {
            "archive": archive_name,
            "bytes": package_bytes,
            "sha256": package_sha,
            "engine": engine,
            "map_files": len(map_ids),
            **obs,
        },
        "derived": derived,
        "system_evidence": system_evidence,
        "signals": signals,
        "limitations": [
            "MV/MZ event metrics observe JSON event commands; plugin/script-created runtime content can add behavior beyond static counts.",
            "Encrypted media assets are counted by file metadata but are not decrypted or semantically inspected.",
            "Battle Processing commands can undercount plugin-driven tactical encounters invoked through scripts/common events.",
            "Grinding pressure remains a proxy until progression curves, battle graph, healing/failure costs, and runtime behavior are modeled."
        ]
    }
    Path(args.out).write_text(json.dumps(genome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.normalized_out:
        database = obs["database"]
        assets = obs["assets"]
        normalized = {
            "schema": NORMALIZED_SCHEMA,
            "game_id": game_id,
            "title": title,
            "version": version,
            "engine": engine,
            "sha256": package_sha,
            "bytes": package_bytes,
            "source_url": source_url,
            "metrics": {
                "maps": obs["maps_loaded"], "events": obs["events"], "event_pages": obs["event_pages"],
                "event_commands": obs["event_commands"], "dialogue_blocks": obs["dialogue_blocks"],
                "dialogue_lines": obs["dialogue_lines"], "dialogue_chars": obs["dialogue_chars"],
                "choice_commands": obs["choice_commands"], "choice_options": obs["choice_options"],
                "conditional_branches": obs["conditional_branches"], "transfers": obs["transfers"],
                "battle_calls": obs["battle_processing_calls"], "shops": obs["shop_processing_calls"],
                "enabled_plugins": len(enabled_names), "total_plugins": len(plugins),
                "image_count": assets["image_count_including_encrypted"], "audio_count": assets["audio_count_including_encrypted"],
                **database,
            },
            "derived": derived,
            "progression": {
                "random_encounter_map_ratio": obs["random_encounter_map_ratio"],
                "encounter_step_median": obs["encounter_step_stats"]["median"],
                "enemy_exp_median": obs["enemy_exp_stats"]["median"],
                "enemy_gold_median": obs["enemy_gold_stats"]["median"],
                "equipment_price_median": obs["equipment_price_stats"]["median"],
            },
            "system_evidence": system_evidence,
            "baseline_status": "REAL_ORDINARY_RPG_BASELINE_PENDING",
            "note": "Do not emit production percentile labels until a real same-schema ordinary-RPG corpus is populated."
        }
        Path(args.normalized_out).write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"schema": SCHEMA, "maps": obs["maps_loaded"], "events": obs["events"],
                      "event_commands": obs["event_commands"], "dialogue_chars": obs["dialogue_chars"],
                      "enabled_plugins": len(enabled_names), "signals": signals}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
