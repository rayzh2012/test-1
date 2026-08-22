import importlib.util
from pathlib import Path
from types import SimpleNamespace


MODULE = Path(__file__).resolve().parents[1] / "tools" / "fangame_release_manifest.py"
spec = importlib.util.spec_from_file_location("fangame_release_manifest", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def args(release_id, version, kind="UNKNOWN", parent=None):
    return SimpleNamespace(
        game_id="fixture-game",
        title="Fixture Game",
        release_id=release_id,
        version=version,
        kind=kind,
        parent_release_id=parent,
        ignore=[],
    )


def test_manifest_diff_and_rollback_plan(tmp_path):
    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir(); new.mkdir()

    (old / "Graphics").mkdir(); (new / "Graphics").mkdir()
    (old / "Data").mkdir(); (new / "Data").mkdir()
    (old / "Graphics" / "hero.png").write_bytes(b"same-hero")
    (new / "Graphics" / "hero.png").write_bytes(b"same-hero")
    (old / "Data" / "Map001.rvdata").write_bytes(b"old-map")
    (new / "Data" / "Map001.rvdata").write_bytes(b"fixed-map")
    (old / "readme.txt").write_bytes(b"same-moved-content")
    (new / "manual.txt").write_bytes(b"same-moved-content")
    (new / "Game.ini").write_bytes(b"[Game]\nTitle=Fixture\n")

    m1 = mod.build_manifest(old, args("fixture-v1", "1.0", "ORIGINAL"))
    m2 = mod.build_manifest(new, args("fixture-v11", "1.1", "FIX", "fixture-v1"))

    assert m1["content_root_sha256"] != m2["content_root_sha256"]
    assert m1["total_files"] == 3
    assert m2["total_files"] == 4

    diff = mod.diff_manifests(m1, m2)
    assert diff["counts"]["changed"] == 1
    assert diff["counts"]["added"] == 2
    assert diff["counts"]["removed"] == 1
    assert diff["counts"]["unchanged"] == 1
    assert diff["counts"]["reused_by_hash"] == 1
    assert diff["bytes"]["reused_content"] > 0
    assert diff["bytes"]["new_or_changed_content"] > 0

    plan = mod.rollback_plan(m2, m1)
    assert plan["target_release_id"] == "fixture-v1"
    assert plan["target_root_sha256"] == m1["content_root_sha256"]
    assert "Game.ini" in plan["delete_paths"]
    assert "Data/Map001.rvdata" in plan["write_paths"]
    assert any(x["target_path"] == "Graphics/hero.png" for x in plan["reuse_objects"])
    assert len(plan["need_objects"]) >= 1


def test_manifest_is_deterministic_and_ignores_ds_store(tmp_path):
    root = tmp_path / "game"
    root.mkdir()
    (root / "b.txt").write_bytes(b"b")
    (root / "a.txt").write_bytes(b"a")
    (root / ".DS_Store").write_bytes(b"noise")

    m1 = mod.build_manifest(root, args("r1", "1"))
    m2 = mod.build_manifest(root, args("r1", "1"))

    assert m1["files"] == m2["files"]
    assert m1["content_root_sha256"] == m2["content_root_sha256"]
    assert [x["path"] for x in m1["files"]] == ["a.txt", "b.txt"]
