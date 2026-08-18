#!/usr/bin/env python3
import argparse
import json
import math
from pathlib import Path

VECTOR_VERSION = "fangame.grind.vector.v0.5b"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def number(v):
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except Exception:
        return None
    return x if math.isfinite(x) else None


def rate(numerator, denominator, scale):
    n, d = number(numerator), number(denominator)
    if n is None or d is None or d <= 0:
        return None
    return round(n / d * scale, 6)


def nested(obj, *keys):
    cur = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--out", default="fangame_grind_vector.json")
    args = ap.parse_args()

    rec = load(args.features)
    progression = rec.get("progression") if isinstance(rec.get("progression"), dict) else {}
    observed = progression.get("observed") if isinstance(progression.get("observed"), dict) else {}
    derived = progression.get("derived") if isinstance(progression.get("derived"), dict) else {}
    commands = observed.get("event_commands") if isinstance(observed.get("event_commands"), dict) else {}

    maps = number(observed.get("maps_loaded"))
    event_commands = number(commands.get("event_command_count"))
    encounter_ratio = number(observed.get("random_encounter_map_ratio"))
    encounter_step = number(nested(observed, "encounter_step_stats", "median"))
    economy_ratio = number(derived.get("median_equipment_price_to_enemy_gold_ratio"))
    exp_basis_ratio = number(derived.get("median_progression_exp_basis_to_enemy_exp_ratio"))

    positive_rewards = sum(
        number(commands.get(k)) or 0.0
        for k in (
            "positive_gold_reward_ops",
            "positive_item_reward_ops",
            "positive_weapon_reward_ops",
            "positive_armor_reward_ops",
        )
    )

    missing = []
    core_inputs = {
        "random_encounter_map_ratio": encounter_ratio,
        "median_encounter_step": encounter_step,
        "median_equipment_price_to_enemy_gold_ratio": economy_ratio,
        "event_command_count": event_commands,
        "maps_loaded": maps,
    }
    for key, value in core_inputs.items():
        if value is None:
            missing.append(key)

    available = sum(v is not None for v in core_inputs.values())
    coverage = round(available / len(core_inputs), 4)
    if progression.get("status") != "PROGRESSION_OBSERVED":
        status = "VECTOR_UNAVAILABLE"
    elif coverage >= 0.8:
        status = "VECTOR_READY"
    else:
        status = "VECTOR_PARTIAL"

    vector = {
        "vector_version": VECTOR_VERSION,
        "source_feature_schema": rec.get("schema_version"),
        "source_progression_status": progression.get("status"),
        "status": status,
        "coverage": coverage,
        "missing_core_inputs": missing,
        "features": {
            "random_encounter_map_ratio": encounter_ratio,
            "encounter_checks_proxy_per_100_steps": round(100.0 / encounter_step, 6) if encounter_step and encounter_step > 0 else None,
            "median_equipment_price_to_enemy_gold_ratio": economy_ratio,
            "log1p_equipment_price_to_enemy_gold_ratio": round(math.log1p(economy_ratio), 6) if economy_ratio is not None and economy_ratio >= 0 else None,
            "positive_reward_ops_per_1000_event_commands": rate(positive_rewards, event_commands, 1000.0),
            "positive_reward_ops_per_map": rate(positive_rewards, maps, 1.0),
            "change_exp_ops_per_1000_event_commands": rate(commands.get("change_exp_ops"), event_commands, 1000.0),
            "recover_all_ops_per_100_maps": rate(commands.get("recover_all_ops"), maps, 100.0),
            "battle_processing_ops_per_100_maps": rate(commands.get("battle_processing_ops"), maps, 100.0),
            "shop_processing_ops_per_100_maps": rate(commands.get("shop_processing_ops"), maps, 100.0),
            "transfer_ops_per_100_maps": rate(commands.get("transfer_ops"), maps, 100.0),
        },
        "context_only": {
            "median_progression_exp_basis_to_enemy_exp_ratio": exp_basis_ratio,
            "enemy_exp_median": number(nested(observed, "enemy_exp_stats", "median")),
            "enemy_gold_median": number(nested(observed, "enemy_gold_stats", "median")),
            "equipment_price_median": number(nested(observed, "equipment_price_stats", "median")),
        },
        "calibration_status": "UNLABELED_VECTOR_ONLY",
        "grind_pressure": None,
        "policy": {
            "weighted_score_emitted": False,
            "hours_estimate_emitted": False,
            "note": (
                "v0.5b performs deterministic scale normalization only. It deliberately emits no grind label, score, "
                "or playtime estimate until a labeled calibration corpus exists. EXP-basis/enemy-EXP remains context-only "
                "because its monotonic relationship with grind is not established across RPG Maker generations/scripts."
            ),
        },
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(vector, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(vector, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
