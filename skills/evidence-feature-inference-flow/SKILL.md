---
name: evidence-feature-inference-flow
description: 将任意重复性 workflow 从“执行任务”升级为 Evidence -> Normalize -> Verify -> Feature Store -> Derived Metrics -> Conservative Inference -> Ranking/Decision -> Action 的可审计数据系统。适用于游戏测试、招聘/邮件运营、研究、QA、文档审计、资产筛选等需要长期积累结构化证据和推断的工作流。
version: 0.1
allowed-tools: [github, google_drive, notion, web, code_execution, file_ops]
---

# Evidence → Feature → Inference Flow

## Purpose
This is a domain-agnostic personal/enterprise workflow pattern.

A task is not complete merely because an agent performed an action. A mature workflow should convert every run into reusable evidence and features so later runs can compare, cluster, infer, rank, and improve decisions.

Core flow:

`RAW INPUT -> IDENTITY -> OBSERVED EVIDENCE -> NORMALIZED FEATURES -> VERIFIED STATE -> DERIVED METRICS -> CONSERVATIVE INFERENCE -> RANKING/DECISION -> ACTION -> AUDIT` 

## Four evidence classes
Every persisted field must be labeled conceptually as one of:
- `OBSERVED`: directly measured/read from source or runtime.
- `DERIVED`: deterministic transformation of observed data.
- `INFERRED`: probabilistic/model inference; must carry confidence + model/rule version + evidence summary.
- `UNKNOWN`: insufficient evidence. Never replace uncertainty with fabricated completeness.

## Core objects
Every domain adapter should emit a canonical feature record with:

### Identity
Stable object ID, version/lineage, source/provenance, content hash where possible.

### Evidence
Raw measurement summaries, runtime logs, screenshots/reports, source references, timestamps.

### Verification
What was actually confirmed, what failed, and whether failure belongs to the subject or the test environment.

### Features
Normalized machine-readable fields suitable for comparison across objects.

### Inference
Model/rule output separated from observed facts. Include confidence and evidence trace.

### Decision
Priority/ranking/fit/action recommendation. Preserve the underlying component scores instead of only one opaque final score.

### Audit
Schema version, inference version, tool/runtime version, run ID, timestamp, and artifact IDs.

## Design rules
1. **Evidence before inference.** Never let model output masquerade as source fact.
2. **Feature Store, not tracker.** Spreadsheets/databases should become long-lived analytical assets.
3. **Schema-first.** Domain workflows emit a stable JSON record before writing to Sheets/Notion/Drive.
4. **Idempotent upsert.** Re-running the same object/version updates the same entity; do not create duplicate rows.
5. **Recomputable inference.** Observed data is immutable-ish; derived/inferred layers may be recalculated when rules improve.
6. **Environment vs subject failure.** Test harness failures must never be silently attributed to the object being tested.
7. **Confidence is data.** Every inference should expose confidence and evidence summary.
8. **Human time goes to decisions.** Agents collect/normalize/verify; people inspect only ranked signal or exceptions.

## Adapter contract
A domain adapter SHOULD provide:
- `identity_adapter`
- `evidence_collector`
- `normalizer`
- `verifier`
- `feature_emitter`
- optional `graph_builder`
- optional `inference_modules`
- `ranking_policy`
- `feature_store_writer`
- `evidence_archive_writer`

## Canonical output pattern
```json
{
  "schema_version": "domain.features.v1",
  "identity": {},
  "observed": {},
  "runtime": {},
  "derived": {},
  "inferred": {},
  "ranking": {},
  "evidence": {},
  "audit": {}
}
```

## Enterprise reuse examples
- **Game QA**: package/build -> smoke test -> crash/input/perf features -> defect likelihood -> release decision.
- **Recruiting**: job posting + email thread -> normalized role features -> fit/urgency inference -> action queue.
- **Research**: source corpus -> claims/evidence graph -> contradiction/features -> hypothesis ranking.
- **Document operations**: files -> metadata/content signals -> completeness/compliance features -> exception queue.
- **Asset triage**: files/packages -> identity/hash/structure -> recoverability/value -> storage priority.

## First production adapter
`fangame-playability-miner` is the first concrete adapter. It demonstrates the pattern on RPG Maker fangames because the domain offers strong ground truth: binary identity, inspectable data files, runtime smoke evidence, and measurable content structure.

## Non-negotiable
The system exists to make accumulated work **more valuable over time**. If a run only produces a transient answer and no reusable evidence/feature state when the domain supports persistence, the flow is incomplete.
