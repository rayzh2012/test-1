# Fangame Grind Calibration Corpus v0.5c

This directory is the governance boundary for future grind-model ground truth.

## Separation rule

Production per-game features live in the Fangame Feature Store. Human/source labels do **not** belong in those feature records. Calibration labels are an independent dataset and are joined to feature vectors only in a future training/evaluation stage.

This separation reduces label leakage, circular evaluation, and accidental conversion of historical opinions into observed game facts.

## Label contract

Each NDJSON record must validate against:

`schemas/fangame_grind_label_v05c.schema.json`

A label records five mechanism-level dimensions plus an overall human/source judgment:

- `required_repetition`
- `level_pressure`
- `economy_pressure`
- `encounter_intrusion`
- `recovery_penalty`
- `overall_grind_burden`

The ordinal vocabulary is `VERY_LOW / LOW / MEDIUM / HIGH / VERY_HIGH / UNKNOWN`.

## Evidence independence

`source_id` identifies the concrete source. `independence_group` identifies the underlying evidence family. Ten mirrors or reposts of the same review should share one independence group and must not be treated as ten independent observations.

## Immutable corrections

Do not edit historical label records in place after they have entered a corpus snapshot. Create a new label with a new `label_id` and set `audit.supersedes_label_id` to the old label. Corpus audit excludes superseded labels from active statistics while preserving the audit trail.

## No calibration policy yet

v0.5c validates and profiles the label corpus but deliberately does not decide whether the corpus is large or diverse enough to fit a model. That readiness decision requires a separate versioned calibration policy.

Until such a policy exists and passes:

- no model weights
- no `grind_pressure`
- no playtime estimate

An empty corpus is valid and preferable to fabricated labels.
