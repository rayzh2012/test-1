#!/usr/bin/env python3
"""Run low-latency, Unity-independent PAL3 verification slices."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def run(cmd: list[str], cwd: Path, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# PAL3 Chat Fast Lane",
        "",
        f"- Overall: **{report['status']}**",
        "",
        "## Test slices",
    ]
    for item in report["slices"]:
        lines.append(
            f"- `{item['id']}` — status={item['status']} runner={item['runner']}"
        )
        if item.get("missing_files"):
            lines.append(f"  - missing: {', '.join(item['missing_files'])}")
        if item.get("result_file"):
            lines.append(f"  - result: `{item['result_file']}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_dotnet_nunit(
    item: dict[str, Any],
    workspace: Path,
    temp_root: Path,
    out_dir: Path,
) -> dict[str, Any]:
    slice_id = item["id"]
    framework = item.get("framework", "net8.0")
    required_files = item.get("source_files", []) + item.get("test_files", [])
    missing = [rel for rel in required_files if not (workspace / rel).is_file()]

    if missing:
        required = bool(item.get("required", False))
        return {
            "id": slice_id,
            "runner": "dotnet_nunit",
            "status": "FAIL_MISSING_FILES" if required else "SKIPPED_MISSING_FILES",
            "missing_files": missing,
        }

    slice_dir = temp_root / slice_id
    shutil.rmtree(slice_dir, ignore_errors=True)
    slice_dir.mkdir(parents=True, exist_ok=True)

    create = run(
        [
            "dotnet",
            "new",
            "nunit",
            "--name",
            f"{slice_id}.Tests",
            "--output",
            str(slice_dir),
            "--framework",
            framework,
            "--no-restore",
        ],
        cwd=temp_root,
    )
    if create.returncode != 0:
        return {
            "id": slice_id,
            "runner": "dotnet_nunit",
            "status": "FAIL_PROJECT_CREATE",
            "stdout": create.stdout[-8000:],
            "stderr": create.stderr[-8000:],
        }

    default_test = slice_dir / "UnitTest1.cs"
    if default_test.exists():
        default_test.unlink()

    copied: list[str] = []
    for rel in required_files:
        src = workspace / rel
        dst = slice_dir / src.name
        if dst.exists():
            return {
                "id": slice_id,
                "runner": "dotnet_nunit",
                "status": "FAIL_DUPLICATE_BASENAME",
                "duplicate": src.name,
            }
        shutil.copy2(src, dst)
        copied.append(rel)

    projects = list(slice_dir.glob("*.csproj"))
    if len(projects) != 1:
        return {
            "id": slice_id,
            "runner": "dotnet_nunit",
            "status": "FAIL_PROJECT_DISCOVERY",
            "project_count": len(projects),
        }

    result_dir = out_dir / "dotnet-tests" / slice_id
    result_dir.mkdir(parents=True, exist_ok=True)
    trx_name = f"{slice_id}.trx"
    test = run(
        [
            "dotnet",
            "test",
            str(projects[0]),
            "--configuration",
            "Release",
            "--logger",
            f"trx;LogFileName={trx_name}",
            "--results-directory",
            str(result_dir),
        ],
        cwd=slice_dir,
    )

    return {
        "id": slice_id,
        "runner": "dotnet_nunit",
        "status": "PASS" if test.returncode == 0 else "FAIL_TESTS",
        "copied_files": copied,
        "result_file": str((result_dir / trx_name).relative_to(out_dir)),
        "stdout": test.stdout[-12000:],
        "stderr": test.stderr[-12000:],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--temp", default=".control/fastlane")
    args = parser.parse_args()

    config = load_json(Path(args.config).resolve())
    workspace = Path(args.workspace).resolve()
    out_dir = Path(args.out).resolve()
    temp_root = Path(args.temp).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    temp_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for item in config.get("slices", []):
        runner = item.get("runner")
        if runner == "dotnet_nunit":
            results.append(run_dotnet_nunit(item, workspace, temp_root, out_dir))
        else:
            results.append(
                {
                    "id": item.get("id", "unknown"),
                    "runner": runner,
                    "status": "FAIL_UNKNOWN_RUNNER",
                }
            )

    failed = [item for item in results if item["status"].startswith("FAIL_")]
    report = {
        "schema_version": "pal3_fastlane_report.v0.1",
        "status": "PASS" if not failed else "FAIL",
        "slices": results,
    }

    json_path = out_dir / "fastlane_report.json"
    md_path = out_dir / "fastlane_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, md_path)

    print(json.dumps({"status": report["status"], "slices": len(results), "report": str(json_path)}))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
