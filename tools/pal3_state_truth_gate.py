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
    money_command = read(workspace, "Assets/Scripts/Pal3.Core/Command/SceCommands/ScriptVarSetMoneyCommand.cs")

    checks: list[dict] = []

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

    failed = [item for item in checks if not item["pass"]]
    report = {
        "schema_version": "pal3_state_truth_gate.v0.1",
        "status": "PASS" if not failed else "FAIL",
        "verification_boundary": "source-contract verification after ordered patch replay; not a Unity runtime playthrough",
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
