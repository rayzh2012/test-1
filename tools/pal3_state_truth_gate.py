#!/usr/bin/env python3
"""Verify PAL3 runtime state is sourced from real game state, not development shortcuts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read(workspace: Path, relative: str) -> str:
    path = workspace / relative
    if not path.is_file():
        raise FileNotFoundError(relative)
    return path.read_text(encoding="utf-8-sig")


def check_contains(checks: list[dict], source: str, name: str, fragment: str) -> None:
    checks.append({"name": name, "pass": fragment in source, "expected": fragment})


def check_absent(checks: list[dict], source: str, name: str, fragment: str) -> None:
    checks.append({"name": name, "pass": fragment not in source, "forbidden": fragment})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    inventory = read(workspace, "Assets/Scripts/Pal3.Game/GameSystems/Inventory/InventoryManager.cs")
    variables = read(workspace, "Assets/Scripts/Pal3.Game/Script/UserVariableManager.cs")
    script_runner = read(workspace, "Assets/Scripts/Pal3.Game/Script/PalScriptRunner.cs")
    save_manager = read(workspace, "Assets/Scripts/Pal3.Game/State/SaveManager.cs")
    pal3 = read(workspace, "Assets/Scripts/Pal3.Game/Pal3.cs")
    money_command = read(workspace, "Assets/Scripts/Pal3.Core/Command/SceCommands/ScriptVarSetMoneyCommand.cs")
    combat_result_command = read(
        workspace,
        "Assets/Scripts/Pal3.Core/Command/SceCommands/ScriptVarSetCombatResultCommand.cs",
    )
    combat_manager = read(
        workspace,
        "Assets/Scripts/Pal3.Game/GameSystems/Combat/CombatManager.cs",
    )
    combat_coordinator = read(
        workspace,
        "Assets/Scripts/Pal3.Game/GameSystems/Combat/CombatCoordinator.cs",
    )
    combat_outcome = read(
        workspace,
        "Assets/Scripts/Pal3.Game/GameSystems/Combat/Domain/CombatOutcomeResolver.cs",
    )
    combat_reward = read(
        workspace,
        "Assets/Scripts/Pal3.Game/GameSystems/Combat/Domain/CombatRewardResolver.cs",
    )
    progression_store = read(
        workspace,
        "Assets/Scripts/Pal3.Game/GameSystems/PlayerProgression/Domain/PlayerActorProgressionStore.cs",
    )
    progression_manager = read(
        workspace,
        "Assets/Scripts/Pal3.Game/GameSystems/PlayerProgression/PlayerActorProgressionManager.cs",
    )
    progression_codec = read(
        workspace,
        "Assets/Scripts/Pal3.Game/GameSystems/PlayerProgression/Domain/PlayerActorProgressionSaveCodec.cs",
    )
    progression_restore_command = read(
        workspace,
        "Assets/Scripts/Pal3.Game/Command/Extensions/PlayerRestoreActorProgressionCommand.cs",
    )

    checks: list[dict] = []

    # Inventory / money truth.
    check_contains(
        checks,
        inventory,
        "inventory_have_item_reads_real_count",
        "return _items.TryGetValue(itemId, out int count) && count > 0;",
    )
    check_absent(
        checks,
        inventory,
        "plot_items_are_not_auto_owned",
        "_gameItemInfos[itemId].Type == ItemType.Plot",
    )
    check_contains(
        checks,
        variables,
        "script_money_reads_inventory_manager",
        "ServiceLocator.Instance.Get<InventoryManager>().GetTotalMoney()",
    )
    check_absent(checks, variables, "script_money_has_no_777777_stub", "777777")
    check_contains(
        checks,
        money_command,
        "sce_command_49_semantics_are_current_money",
        "取出当前金钱数并赋值给变量",
    )
    check_contains(
        checks,
        script_runner,
        "script_item_condition_uses_inventory_have_item",
        ".HaveItem(command.ItemId);",
    )
    check_contains(
        checks,
        save_manager,
        "save_roundtrip_serializes_real_money",
        "new InventoryAddMoneyCommand(_inventoryManager.GetTotalMoney())",
    )
    check_contains(
        checks,
        save_manager,
        "save_roundtrip_serializes_real_items",
        "new InventoryAddItemCommand(item.Key, item.Value)",
    )

    # Combat-result truth.
    check_contains(
        checks,
        combat_result_command,
        "sce_command_132_semantics_are_zero_lose_one_win",
        "取得战斗结果（0输1赢）并赋值给变量",
    )
    check_contains(
        checks,
        combat_outcome,
        "combat_outcome_reads_domain_alive_state",
        "member.Party == CombatParty.Enemy && member.State.IsAlive",
    )
    check_contains(
        checks,
        combat_manager,
        "combat_manager_resolves_terminal_outcome_from_runtime_state",
        "CombatOutcomeStatus outcome = CombatOutcomeResolver.Resolve(members);",
    )
    check_contains(
        checks,
        combat_manager,
        "combat_manager_signals_real_player_loss",
        "isPlayerWin: false,\n                        rewards: CombatRewardSummary.Empty",
    )
    check_contains(
        checks,
        combat_coordinator,
        "combat_coordinator_persists_last_result_before_script_resume",
        "_lastCombatPlayerWin = combatResult.IsPlayerWin;",
    )
    check_contains(
        checks,
        combat_coordinator,
        "combat_loss_can_resume_when_no_game_over_flag_is_set",
        "combatResult.IsPlayerWin || combatResult.CombatContext.IsNoGameOverWhenLose",
    )
    check_contains(
        checks,
        variables,
        "script_combat_result_reads_coordinator_state",
        "combatCoordinator.TryGetLastCombatResult(out bool isPlayerWin)",
    )
    check_absent(
        checks,
        variables,
        "script_combat_result_has_no_random_win_loss_stub",
        "你战胜了重楼",
    )
    check_absent(
        checks,
        variables,
        "script_combat_result_has_no_random_pal3a_stub",
        "你战胜了景小楼",
    )
    check_contains(
        checks,
        combat_manager,
        "escape_finish_is_explicitly_debug_labeled",
        "Debug combat finish forced by Escape key.",
    )

    # Combat reward truth.
    check_contains(
        checks,
        combat_reward,
        "reward_domain_uses_checked_money_aggregation",
        "money = checked(money + source.Money);",
    )
    check_contains(
        checks,
        combat_manager,
        "enemy_reward_sources_use_gdb_experience",
        "actorInfo.Experience,",
    )
    check_contains(
        checks,
        combat_manager,
        "enemy_reward_sources_use_gdb_money_when_killed",
        "actorInfo.MoneyWhenKilled,",
    )
    check_contains(
        checks,
        combat_manager,
        "enemy_reward_sources_use_gdb_normal_loot",
        "actorInfo.NormalLoot,",
    )
    check_contains(
        checks,
        combat_manager,
        "real_player_win_resolves_rewards",
        "rewards: CombatRewardResolver.Resolve(_enemyRewardSources)",
    )
    check_contains(
        checks,
        combat_manager,
        "debug_escape_cannot_generate_rewards",
        "Debug combat finish forced by Escape key.\");\n                SignalCombatFinished(\n                    isPlayerWin: true,\n                    rewards: CombatRewardSummary.Empty",
    )
    check_contains(
        checks,
        combat_coordinator,
        "combat_reward_settlement_requires_player_win",
        "if (!combatResult.IsPlayerWin) return;",
    )
    check_contains(
        checks,
        combat_coordinator,
        "combat_money_reward_enters_inventory_command_bus",
        "new InventoryAddMoneyCommand(rewards.Money)",
    )
    check_contains(
        checks,
        combat_coordinator,
        "combat_loot_reward_enters_inventory_command_bus",
        "new InventoryAddItemCommand(checked((int)itemId), count)",
    )
    check_contains(
        checks,
        combat_coordinator,
        "combat_exp_is_explicitly_pending_growth_semantics",
        "Combat EXP reward pending persistent actor-stat support",
    )

    # Persistent player-progression truth. These checks intentionally verify exact snapshot
    # round-trip wiring only. They do not claim an EXP->level threshold or level-growth formula.
    check_contains(
        checks,
        progression_store,
        "progression_store_exports_defensive_snapshot_copies",
        "snapshots[actorId] = snapshot.Copy();",
    )
    check_contains(
        checks,
        progression_manager,
        "progression_manager_executes_restore_command",
        "ICommandExecutor<PlayerRestoreActorProgressionCommand>",
    )
    check_contains(
        checks,
        progression_manager,
        "progression_restore_decodes_into_runtime_owner",
        "_store.RestoreSnapshot(PlayerActorProgressionSaveCodec.Decode(command));",
    )
    check_contains(
        checks,
        progression_codec,
        "progression_codec_is_versioned",
        "private const int FORMAT_VERSION = 1;",
    )
    check_contains(
        checks,
        progression_codec,
        "progression_codec_roundtrip_command_encoder_exists",
        "public static PlayerRestoreActorProgressionCommand Encode(",
    )
    check_contains(
        checks,
        progression_restore_command,
        "progression_restore_command_rejects_empty_payload",
        "string.IsNullOrWhiteSpace(payload)",
    )
    check_contains(
        checks,
        save_manager,
        "save_manager_owns_progression_dependency",
        "private readonly PlayerActorProgressionManager _playerActorProgressionManager;",
    )
    check_contains(
        checks,
        save_manager,
        "save_manager_serializes_all_progression_snapshots",
        "_playerActorProgressionManager.GetAllSnapshots()",
    )
    check_contains(
        checks,
        save_manager,
        "save_manager_uses_versioned_progression_codec",
        "PlayerActorProgressionSaveCodec.Encode(pair.Value)",
    )
    check_contains(
        checks,
        pal3,
        "composition_root_injects_same_progression_owner_into_save_manager",
        "_playerActorProgressionManager,\n                    _inventoryManager",
    )

    failed = [item for item in checks if not item["pass"]]
    report = {
        "schema_version": "pal3_state_truth_gate.v0.4",
        "status": "PASS" if not failed else "FAIL",
        "verification_boundary": (
            "source-contract verification after ordered patch replay; pure combat outcome/reward and "
            "progression codec domains are separately compiled/tested by Fast Lane; exact progression "
            "snapshot persistence is checked here; not a Unity runtime playthrough and not evidence of "
            "original PAL3 EXP thresholds or level-growth formulas"
        ),
        "checks": checks,
    }

    (out / "state_truth_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# PAL3 State Truth Gate",
        "",
        f"- Status: **{report['status']}**",
        f"- Boundary: {report['verification_boundary']}",
        "",
        "## Checks",
    ]
    for item in checks:
        lines.append(f"- {'PASS' if item['pass'] else 'FAIL'} — `{item['name']}`")
    (out / "state_truth_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps({"status": report["status"], "checks": len(checks), "failed": len(failed)}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
