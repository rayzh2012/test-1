# Fangame Calibration Labels

This directory is for **labels only**, not observed game evidence.

Canonical game evidence remains in the Fangame Feature Store. Calibration labels are a separate layer used only after schema validation and corpus audit.

## Record contract

Each label record must validate against:

- `schemas/fangame_calibration_label_v07.schema.json`
- rubric/policy: `policies/fangame_calibration_v07.json`

Recommended filename:

`<stable-game-id>__<context>__<label-record-id>.json`

## Context is part of the label

Hours and grind are not universal facts if play conditions differ. Record difficulty, speed-up, cheats/debug, completion scope and relevant EXP/difficulty mode.

A second materially different play context should create a second label record. Do not average it into the first record.

## Training boundary

`tools/fangame_calibration_audit.py` classifies each label independently for hours and grind:

- `DIRECT_TRAINING` — eligible for the initial baseline calibration gate.
- `REFERENCE_ONLY` — useful evidence but not direct training truth.
- `CONTEXTUAL_ONLY` — valid label collected under a context the baseline model does not yet represent, such as speed-up.
- `EXPERIMENTAL` — automated/experimental label retained for later evaluation.
- `UNLABELED` — no usable label for that target.

Only `DIRECT_TRAINING` opens v0.7 readiness gates.

## Non-negotiable separation

Do not add `observed`, `derived`, runtime facts, private Drive IDs, binary package data, or inferred feature-store fields to a calibration label. The schema rejects additional top-level fields so subjective training truth cannot overwrite source evidence.

The readiness gate is permission to **start a calibration experiment**, not proof that a model is accurate. Cross-validation, holdout testing and error analysis remain mandatory.
