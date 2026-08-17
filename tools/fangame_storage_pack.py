#!/usr/bin/env python3
"""Prepare a space-efficient, reversible preservation payload for Drive.

Rules:
- Already-compressed archives stay byte-for-byte original; don't double-compress.
- Other single-file payloads are trial-packed into ZIP9 containing the original file.
- Use the ZIP only when it saves at least 2% AND 1 MiB.
- Always write a manifest preserving original filename, size and SHA256.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

MIN_SAVE_BYTES = 1 * 1024 * 1024
MIN_SAVE_RATIO = 0.02


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_already_compressed(path: Path) -> bool:
    suffix = path.name.lower()
    compressed_exts = (
        ".zip", ".rar", ".7z", ".gz", ".tgz", ".bz2", ".xz", ".cab",
        ".png", ".jpg", ".jpeg", ".webp", ".mp3", ".ogg", ".mp4", ".webm",
    )
    if suffix.endswith(compressed_exts):
        return True
    try:
        head = path.read_bytes()[:16]
    except Exception:
        return False
    return (
        head.startswith(b"PK\x03\x04") or
        head.startswith(b"Rar!\x1a\x07") or
        head.startswith(b"7z\xbc\xaf\x27\x1c") or
        head.startswith(b"\x1f\x8b") or
        head.startswith(b"BZh") or
        head.startswith(b"\xfd7zXZ\x00")
    )


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: fangame_storage_pack.py INPUT OUTPUT_DIR MANIFEST_JSON", file=sys.stderr)
        return 2

    src = Path(sys.argv[1]).resolve()
    outdir = Path(sys.argv[2]).resolve()
    manifest_path = Path(sys.argv[3]).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if not src.is_file():
        raise FileNotFoundError(src)

    original_size = src.stat().st_size
    original_sha = sha256_file(src)
    payload = outdir / src.name
    method = "original_already_compressed"
    trial_zip_size = None

    if looks_already_compressed(src):
        shutil.copy2(src, payload)
    else:
        trial_zip = outdir / f"{src.name}.preservation.zip"
        with zipfile.ZipFile(trial_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            zf.write(src, arcname=src.name)
        trial_zip_size = trial_zip.stat().st_size
        saved = original_size - trial_zip_size
        ratio = (saved / original_size) if original_size else 0.0
        if saved >= MIN_SAVE_BYTES and ratio >= MIN_SAVE_RATIO:
            payload = trial_zip
            method = "zip9_contains_original_byte_for_byte"
        else:
            trial_zip.unlink(missing_ok=True)
            payload = outdir / src.name
            shutil.copy2(src, payload)
            method = "original_trial_zip_not_smaller_enough"

    payload_size = payload.stat().st_size
    payload_sha = sha256_file(payload)
    savings = original_size - payload_size
    savings_pct = (100.0 * savings / original_size) if original_size else 0.0

    manifest = {
        "schema": "fangame-preservation-storage/v1",
        "original_filename": src.name,
        "original_size_bytes": original_size,
        "original_sha256": original_sha,
        "storage_payload_filename": payload.name,
        "storage_payload_size_bytes": payload_size,
        "storage_payload_sha256": payload_sha,
        "storage_method": method,
        "storage_savings_bytes": savings,
        "storage_savings_percent": round(savings_pct, 4),
        "trial_zip_size_bytes": trial_zip_size,
        "reversible": True,
        "reconstruction": (
            "Concatenate Drive parts in numeric order to reconstruct storage payload. "
            "If storage_method is zip9_contains_original_byte_for_byte, extract exactly one original file; "
            "verify its SHA256 equals original_sha256. Otherwise the reconstructed payload is the original file itself."
        ),
        "policy": {
            "never_store_full_and_parts_in_drive": True,
            "dedupe_key": "original_sha256",
            "double_compress_existing_archives": False,
            "zip_trial_min_savings_bytes": MIN_SAVE_BYTES,
            "zip_trial_min_savings_ratio": MIN_SAVE_RATIO,
        },
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"payload": str(payload), "manifest": str(manifest_path), "method": method, "savings_pct": savings_pct}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
