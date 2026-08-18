# Grind Calibration Readiness Policies

A calibration corpus can be valid without being ready for model fitting.

Readiness thresholds must live in an explicit, versioned policy document validating against:

`schemas/fangame_grind_calibration_policy_v05d.schema.json`

The deterministic gate is:

`tools/fangame_grind_calibration_gate.py`

The gate consumes a corpus audit plus a policy and emits a decision report. Thresholds are never hidden in the gate implementation.

## No active production policy yet

This repository intentionally does not ship a production readiness policy at v0.5d. A future policy must state its rationale and explicit requirements for sample size, independent evidence groups, dimension coverage, label diversity, and tolerated conflict rate.

Even if a future readiness policy passes, that only permits model-fitting and held-out evaluation experiments. It does **not** authorize production `grind_pressure` values. Deployment requires a later model-evaluation policy gate.
