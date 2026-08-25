# Public Fangame Genome Corpus

This directory is the public, reproducible layer of the fangame analysis pipeline.

The goal is not to publish game binaries. The goal is to publish **machine-readable structural analysis** of RPG Maker fangames so different games can be compared on the same axes: content scale, event scripting density, dialogue capacity, interaction density, combat pressure, system breadth, optionality, runtime quality, and eventually ordinary-RPG-relative percentiles.

## Featured fangame: Pokémon Unchosen v1.5.10

Public report: [`pokemon_unchosen_v1.5.10_eng_joiplay.md`](pokemon_unchosen_v1.5.10_eng_joiplay.md)  
Machine-readable JSON: [`pokemon_unchosen_v1.5.10_eng_joiplay.json`](pokemon_unchosen_v1.5.10_eng_joiplay.json)

Observed structural snapshot: **547 maps, 16,538 events, 32,037 event pages, 205,650 event commands, 357,172 dialogue characters, 7,823 choice options, 3,880 battle calls, and 252 enabled plugins**. The package is RPG Maker MV + LeTBS and includes explicit evidence for autosave, difficulty control, quest journal, New Game+, speed-up, and a substantial LeTBS plugin surface.

These are structural measurements, not a claim that the entire game was manually played. Ordinary-RPG-relative percentile claims remain disabled until a sufficiently large compatible baseline corpus exists.

## Current ordinary-RPG reference

The first real ordinary-RPG reference is **A King's Son v1.6** under the `MV_JSON` parser family. The current compatible baseline is still draft-only (`N=1`), so it is useful for calibration but not for production `top X%` claims.

## Pipeline

```text
public/free fangame package
  -> package identity + SHA256
  -> engine-specific static parser
  -> normalized profile
  -> optional ordinary-RPG baseline comparison
  -> sanitized public JSON + Markdown report
  -> public_reports/index.json
```

## Evidence layers

- **OBSERVED**: directly read from package/data files, e.g. maps, events, event pages, event commands, dialogue characters, choice options, battle calls, plugins.
- **DERIVED**: deterministic transforms of observed values, e.g. event commands per map or dialogue characters per map.
- **INFERRED / HEURISTIC**: clearly versioned descriptors. These are never presented as raw facts.
- **BASELINE-RELATIVE**: percentile/band labels are allowed only after a real ordinary-RPG corpus has been measured with a compatible parser/schema.

## Public/private boundary

Public reports may include title, version, engine, public source URL, package byte size, SHA256, parser/schema versions, observed metrics, deterministic derived metrics, explicit system evidence, and baseline-relative results when valid.

Public reports must not include private Google Drive IDs, private notes, personal-fit scores, private correspondence, or copyrighted game binaries.

## Why a repo instead of only Gists?

A repository gives the corpus stable paths, version history, schema evolution, diffs, bulk download, and cross-game computation. Individual Markdown reports can still be linked or mirrored to Gists later, but the repository is the canonical public analysis layer.

## Current baseline rule

Until a real ordinary/commercial RPG reference corpus exists under the same schema, reports may describe absolute structure but must not claim `P90`, `top 5%`, `extreme`, or similar production percentile labels.

## Generator

Use `tools/fangame_public_report.py` on a normalized profile. Example:

```bash
python tools/fangame_public_report.py normalized.json \
  --out-json public_reports/<game_id>.json \
  --out-md public_reports/<game_id>.md \
  --source-url https://official.example/game \
  --parser-version mv-genome.v0.1
```
