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
        if item.get("define_constants"):
            lines.append(f"  - defines: {', '.join(item['define_constants'])}")
        if item.get("result_file"):
            lines.append(f"  - result: `{item['result_file']}`")
        if item.get("missing_contains"):
            lines.append(f"  - required source fragments missing: {len(item['missing_contains'])}")
        if item.get("unexpected_contains"):
            lines.append(f"  - forbidden source fragments present: {len(item['unexpected_contains'])}")
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

    test_cmd = [
        "dotnet",
        "test",
        str(projects[0]),
        "--configuration",
        "Release",
        "--logger",
        f"trx;LogFileName={trx_name}",
        "--results-directory",
        str(result_dir),
    ]

    define_constants = item.get("define_constants", [])
    if define_constants:
        test_cmd.append(f"-p:DefineConstants={';'.join(define_constants)}")

    test = run(test_cmd, cwd=slice_dir)

    return {
        "id": slice_id,
        "runner": "dotnet_nunit",
        "status": "PASS" if test.returncode == 0 else "FAIL_TESTS",
        "copied_files": copied,
        "define_constants": define_constants,
        "result_file": str((result_dir / trx_name).relative_to(out_dir)),
        "stdout": test.stdout[-12000:],
        "stderr": test.stderr[-12000:],
    }


def run_source_assertions(item: dict[str, Any], workspace: Path) -> dict[str, Any]:
    """Run deterministic source-contract checks without pretending to compile Unity code."""
    slice_id = item["id"]
    relative_path = item["file"]
    source_path = workspace / relative_path
    required = bool(item.get("required", False))

    if not source_path.is_file():
        return {
            "id": slice_id,
            "runner": "source_assertions",
            "status": "FAIL_MISSING_FILES" if required else "SKIPPED_MISSING_FILES",
            "missing_files": [relative_path],
        }

    source = source_path.read_text(encoding="utf-8-sig")
    required_fragments = item.get("contains", [])
    forbidden_fragments = item.get("not_contains", [])
    missing_contains = [fragment for fragment in required_fragments if fragment not in source]
    unexpected_contains = [fragment for fragment in forbidden_fragments if fragment in source]

    return {
        "id": slice_id,
        "runner": "source_assertions",
        "status": "PASS" if not missing_contains and not unexpected_contains else "FAIL_SOURCE_ASSERTIONS",
        "file": relative_path,
        "missing_contains": missing_contains,
        "unexpected_contains": unexpected_contains,
        "checked_required_fragments": len(required_fragments),
        "checked_forbidden_fragments": len(forbidden_fragments),
    }


def run_dotnet_compile_with_stubs(
    item: dict[str, Any],
    workspace: Path,
    control_root: Path,
    temp_root: Path,
    out_dir: Path,
) -> dict[str, Any]:
    """Compile Unity-facing source against audited lightweight API stubs.

    This is a C# contract/syntax gate only. It is deliberately not reported as a Unity build.
    """
    slice_id = item["id"]
    framework = item.get("framework", "net8.0")
    source_files = item.get("source_files", [])
    control_files = item.get("control_files", [])
    required = bool(item.get("required", False))

    missing_workspace = [rel for rel in source_files if not (workspace / rel).is_file()]
    missing_control = [rel for rel in control_files if not (control_root / rel).is_file()]
    missing = missing_workspace + missing_control
    if missing:
        return {
            "id": slice_id,
            "runner": "dotnet_compile_with_stubs",
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
            "classlib",
            "--name",
            f"{slice_id}.Contract",
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
            "runner": "dotnet_compile_with_stubs",
            "status": "FAIL_PROJECT_CREATE",
            "stdout": create.stdout[-8000:],
            "stderr": create.stderr[-8000:],
        }

    default_class = slice_dir / "Class1.cs"
    if default_class.exists():
        default_class.unlink()

    copied: list[str] = []
    for root, relative_files in ((workspace, source_files), (control_root, control_files)):
        for rel in relative_files:
            src = root / rel
            dst = slice_dir / src.name
            if dst.exists():
                return {
                    "id": slice_id,
                    "runner": "dotnet_compile_with_stubs",
                    "status": "FAIL_DUPLICATE_BASENAME",
                    "duplicate": src.name,
                }
            shutil.copy2(src, dst)
            copied.append(rel)

    projects = list(slice_dir.glob("*.csproj"))
    if len(projects) != 1:
        return {
            "id": slice_id,
            "runner": "dotnet_compile_with_stubs",
            "status": "FAIL_PROJECT_DISCOVERY",
            "project_count": len(projects),
        }

    build_cmd = [
        "dotnet",
        "build",
        str(projects[0]),
        "--configuration",
        "Release",
    ]
    define_constants = item.get("define_constants", [])
    if define_constants:
        build_cmd.append(f"-p:DefineConstants={';'.join(define_constants)}")

    build = run(build_cmd, cwd=slice_dir)
    result_dir = out_dir / "contract-compile" / slice_id
    result_dir.mkdir(parents=True, exist_ok=True)
    log_path = result_dir / "build.log"
    log_path.write_text(
        build.stdout + "\n--- STDERR ---\n" + build.stderr,
        encoding="utf-8",
    )

    return {
        "id": slice_id,
        "runner": "dotnet_compile_with_stubs",
        "status": "PASS" if build.returncode == 0 else "FAIL_COMPILE",
        "copied_files": copied,
        "define_constants": define_constants,
        "result_file": str(log_path.relative_to(out_dir)),
        "stdout": build.stdout[-12000:],
        "stderr": build.stderr[-12000:],
        "verification_boundary": "C# contract compile against audited stubs; not a Unity build",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--temp", default=".control/fastlane")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    config = load_json(config_path)
    control_root = Path.cwd().resolve()
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
        elif runner == "source_assertions":
            results.append(run_source_assertions(item, workspace))
        elif runner == "dotnet_compile_with_stubs":
            results.append(
                run_dotnet_compile_with_stubs(
                    item,
                    workspace,
                    control_root,
                    temp_root,
                    out_dir,
                )
            )
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
        "schema_version": "pal3_fastlane_report.v0.4",
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
