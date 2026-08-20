#!/usr/bin/env python3
"""Generic source-rewrite controller for externally checked-out codebases.

The controller keeps the control plane in this repository while treating the
target codebase as an upstream workspace. It can apply a local patch stack,
inventory source files, detect implementation markers, and emit an auditable
JSON/Markdown report for the next ChatGPT-controlled iteration.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

MARKER_PATTERNS = {
    "todo": re.compile(r"\bTODO\b", re.IGNORECASE),
    "fixme": re.compile(r"\bFIXME\b", re.IGNORECASE),
    "not_implemented_exception": re.compile(r"\bNotImplementedException\b"),
    "not_supported_exception": re.compile(r"\bNotSupportedException\b"),
    "throw_exception": re.compile(r"\bthrow\s+new\s+\w*Exception\b"),
}

CODE_EXTENSIONS = {".cs", ".shader", ".hlsl", ".cginc", ".json", ".asmdef", ".asmref"}


@dataclass
class PatchResult:
    patch: str
    check_ok: bool
    applied: bool
    error: str | None = None


def run(cmd: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def git_head(workspace: Path) -> str | None:
    try:
        return run(["git", "rev-parse", "HEAD"], workspace).stdout.strip()
    except Exception:
        return None


def expose_untracked_files_to_git_diff(workspace: Path) -> list[str]:
    """Make patch-created untracked files visible to git diff without staging contents.

    `git apply` leaves newly added files untracked. Plain `git diff`, including
    `git diff --check`, otherwise ignores them. Intent-to-add entries preserve the
    working-tree content while making those files auditable by the same diff path
    used for modified tracked files.
    """
    proc = run(["git", "ls-files", "--others", "--exclude-standard"], workspace, check=False)
    if proc.returncode != 0:
        return []

    untracked_files = [line for line in proc.stdout.splitlines() if line]
    for start in range(0, len(untracked_files), 100):
        chunk = untracked_files[start : start + 100]
        add_proc = run(["git", "add", "--intent-to-add", "--", *chunk], workspace, check=False)
        if add_proc.returncode != 0:
            raise RuntimeError((add_proc.stderr or add_proc.stdout).strip())

    return untracked_files


def iter_source_files(workspace: Path, roots: Iterable[str]) -> Iterable[Path]:
    seen: set[Path] = set()
    for root in roots:
        base = workspace / root
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in CODE_EXTENSIONS and path not in seen:
                seen.add(path)
                yield path


def relative_module(path: Path, workspace: Path, source_roots: list[str]) -> str:
    rel = path.relative_to(workspace)
    parts = rel.parts
    for root in source_roots:
        root_parts = Path(root).parts
        if tuple(parts[: len(root_parts)]) == root_parts:
            tail = parts[len(root_parts) :]
            if not tail:
                return str(Path(root))
            if len(tail) == 1 or Path(tail[1]).suffix:
                return tail[0]
            return "/".join(tail[:2])
    return parts[0] if parts else "."


def apply_patch_stack(workspace: Path, patch_dir: Path) -> list[PatchResult]:
    results: list[PatchResult] = []
    if not patch_dir.exists():
        return results

    for patch in sorted(patch_dir.glob("*.patch")):
        check_proc = run(["git", "apply", "--check", str(patch.resolve())], workspace, check=False)
        if check_proc.returncode != 0:
            results.append(
                PatchResult(
                    patch=patch.name,
                    check_ok=False,
                    applied=False,
                    error=(check_proc.stderr or check_proc.stdout).strip()[:4000],
                )
            )
            continue

        apply_proc = run(["git", "apply", str(patch.resolve())], workspace, check=False)
        results.append(
            PatchResult(
                patch=patch.name,
                check_ok=True,
                applied=apply_proc.returncode == 0,
                error=None
                if apply_proc.returncode == 0
                else (apply_proc.stderr or apply_proc.stdout).strip()[:4000],
            )
        )
    return results


def scan_file(path: Path) -> tuple[int, dict[str, int]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0, {k: 0 for k in MARKER_PATTERNS}
    line_count = text.count("\n") + (1 if text else 0)
    counts = {name: len(pattern.findall(text)) for name, pattern in MARKER_PATTERNS.items()}
    return line_count, counts


def build_report(
    config: dict[str, Any],
    workspace: Path,
    patch_results: list[PatchResult],
    untracked_files: list[str],
) -> dict[str, Any]:
    source_roots = config.get("source_roots", ["Assets/Scripts"])
    files = list(iter_source_files(workspace, source_roots))

    ext_counts: Counter[str] = Counter()
    module_files: Counter[str] = Counter()
    module_lines: Counter[str] = Counter()
    module_markers: dict[str, Counter[str]] = defaultdict(Counter)
    marker_totals: Counter[str] = Counter()
    marker_files: list[dict[str, Any]] = []
    total_lines = 0

    for path in files:
        ext_counts[path.suffix.lower()] += 1
        module = relative_module(path, workspace, source_roots)
        module_files[module] += 1

        lines, markers = scan_file(path)
        total_lines += lines
        module_lines[module] += lines
        marker_sum = sum(markers.values())

        for name, count in markers.items():
            marker_totals[name] += count
            module_markers[module][name] += count

        if marker_sum:
            marker_files.append(
                {
                    "path": str(path.relative_to(workspace)),
                    "module": module,
                    "lines": lines,
                    "markers": markers,
                    "marker_total": marker_sum,
                }
            )

    marker_files.sort(key=lambda x: (-x["marker_total"], -x["lines"], x["path"]))

    module_summary = []
    for module in sorted(module_files):
        marker_count = sum(module_markers[module].values())
        module_summary.append(
            {
                "module": module,
                "files": module_files[module],
                "lines": module_lines[module],
                "marker_total": marker_count,
                "markers": dict(module_markers[module]),
            }
        )
    module_summary.sort(key=lambda x: (-x["marker_total"], -x["lines"], x["module"]))

    try:
        diff_stat = run(["git", "diff", "--stat"], workspace, check=False).stdout.strip()
        diff_name_only = [
            x for x in run(["git", "diff", "--name-only"], workspace, check=False).stdout.splitlines() if x
        ]
        diff_check_proc = run(["git", "diff", "--check"], workspace, check=False)
        diff_check_ok = diff_check_proc.returncode == 0
        diff_check_output = (diff_check_proc.stderr or diff_check_proc.stdout).strip()[:4000]
    except Exception:
        diff_stat = ""
        diff_name_only = []
        diff_check_ok = False
        diff_check_output = "git diff --check unavailable"

    actual_head = git_head(workspace)

    return {
        "schema_version": "source_rewrite_control.v0.1",
        "identity": {
            "project_id": config.get("project_id"),
            "upstream_repository": config.get("upstream_repository"),
            "expected_upstream_ref": config.get("upstream_ref"),
            "actual_upstream_commit": actual_head,
            "engine": config.get("engine"),
            "engine_version": config.get("engine_version"),
        },
        "observed": {
            "source_roots": source_roots,
            "source_file_count": len(files),
            "total_lines": total_lines,
            "extension_counts": dict(ext_counts),
            "marker_totals": dict(marker_totals),
            "marker_files": marker_files[:100],
            "patch_results": [r.__dict__ for r in patch_results],
            "untracked_files_after_patch": untracked_files,
            "changed_files_after_patch": diff_name_only,
            "diff_stat": diff_stat,
            "diff_check_ok": diff_check_ok,
            "diff_check_output": diff_check_output,
        },
        "derived": {
            "module_summary": module_summary,
            "hotspots": module_summary[:20],
            "patch_stack_healthy": all(r.check_ok and r.applied for r in patch_results),
        },
        "inferred": {
            "status": "UNASSESSED",
            "note": "Rewrite priorities are intentionally left to the ChatGPT review step; the controller emits evidence, not model guesses.",
        },
        "audit": {
            "controller_version": "0.2",
            "config_schema": config.get("schema_version"),
        },
    }


def write_markdown(report: dict[str, Any], out_path: Path) -> None:
    obs = report["observed"]
    ident = report["identity"]
    lines = [
        "# Source Rewrite Control Report",
        "",
        f"- Project: `{ident.get('project_id')}`",
        f"- Upstream: `{ident.get('upstream_repository')}`",
        f"- Commit: `{ident.get('actual_upstream_commit')}`",
        f"- Engine: `{ident.get('engine')} {ident.get('engine_version')}`",
        f"- Source files: **{obs.get('source_file_count')}**",
        f"- Source lines: **{obs.get('total_lines')}**",
        "",
        "## Implementation markers",
    ]
    for name, count in sorted(obs.get("marker_totals", {}).items()):
        lines.append(f"- `{name}`: {count}")

    lines += ["", "## Hot modules"]
    for item in report["derived"].get("hotspots", [])[:15]:
        lines.append(
            f"- `{item['module']}` — files={item['files']}, lines={item['lines']}, markers={item['marker_total']}"
        )

    lines += ["", "## Patch stack"]
    patches = obs.get("patch_results", [])
    if not patches:
        lines.append("- No patches applied.")
    else:
        for item in patches:
            lines.append(
                f"- `{item['patch']}` — check={item['check_ok']} applied={item['applied']}"
            )

    changed = obs.get("changed_files_after_patch", [])
    lines += ["", "## Changed files after patches"]
    if changed:
        lines.extend(f"- `{path}`" for path in changed)
    else:
        lines.append("- None.")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit(args: argparse.Namespace) -> int:
    config_path = Path(args.config).resolve()
    config = load_config(config_path)
    workspace = Path(args.workspace).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    patch_dir = (config_path.parent / config.get("patch_dir", "patches")).resolve()
    patch_results = apply_patch_stack(workspace, patch_dir)
    untracked_files = expose_untracked_files_to_git_diff(workspace)

    report = build_report(config, workspace, patch_results, untracked_files)

    json_path = out_dir / "source_control_report.json"
    md_path = out_dir / "source_control_report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, md_path)
    diff_path = out_dir / "applied.patch"
    diff_proc = run(["git", "diff", "--binary"], workspace, check=False)
    diff_path.write_text(diff_proc.stdout, encoding="utf-8")

    failed_patches = [x for x in patch_results if not (x.check_ok and x.applied)]
    if failed_patches:
        print(f"Patch stack failed: {len(failed_patches)} patch(es).")
        return 2
    if not report["observed"].get("diff_check_ok", False):
        print("git diff --check failed.")
        return 3

    print(json.dumps({
        "project_id": report["identity"]["project_id"],
        "upstream_commit": report["identity"]["actual_upstream_commit"],
        "source_files": report["observed"]["source_file_count"],
        "total_lines": report["observed"]["total_lines"],
        "markers": report["observed"]["marker_totals"],
        "changed_files": report["observed"]["changed_files_after_patch"],
        "report": str(json_path),
    }, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    audit_parser = sub.add_parser("audit")
    audit_parser.add_argument("--config", required=True)
    audit_parser.add_argument("--workspace", required=True)
    audit_parser.add_argument("--out", required=True)
    audit_parser.set_defaults(func=audit)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
