---
name: evidence-feature-inference-flow
description: 将任意重复性 workflow 从“执行任务”升级为 Evidence -> Normalize -> Verify -> Feature Store -> Derived Metrics -> Conservative Inference -> Cross-object Compare -> Ranking/Decision -> Action 的可审计数据系统。适用于游戏测试、招聘/邮件运营、研究、QA、文档审计、资产筛选等需要长期积累结构化证据和推断的工作流。
version: 0.2
allowed-tools: [github, google_drive, notion, web, code_execution, file_ops]
---

# Evidence → Feature → Inference Flow

## Purpose
This is a domain-agnostic personal/enterprise workflow pattern.

A task is not complete merely because an agent performed an action. A mature workflow converts every run into reusable evidence and features so later runs can compare, cluster, infer, rank, detect anomalies, and improve decisions.

Core single-object flow:

`RAW INPUT -> IDENTITY -> OBSERVED EVIDENCE -> NORMALIZED FEATURES -> VERIFIED STATE -> DERIVED METRICS -> CONSERVATIVE INFERENCE -> ACTION -> AUDIT`

Cross-object learning flow:

`CANONICAL RECORDS -> FEATURE PROJECTION -> NORMALIZATION -> SIMILARITY / PEERS -> CLUSTERING -> ANOMALY -> EXPLAINABLE RANKING -> HUMAN/AUTOMATION DECISION`

## Four evidence classes
Every persisted field must be labeled conceptually as one of:
- `OBSERVED`: directly measured/read from source or runtime.
- `DERIVED`: deterministic transformation of observed data.
- `INFERRED`: probabilistic/model/rule inference; carries confidence + version + evidence summary.
- `UNKNOWN`: insufficient evidence. Never replace uncertainty with fabricated completeness.

## Core objects
Every domain adapter should emit a canonical feature record with:
- **Identity** — stable ID, version/lineage, provenance, content hash where possible.
- **Evidence** — raw measurement summaries, runtime logs, screenshots/reports, source references, timestamps.
- **Verification** — what was actually confirmed, what failed, and whether failure belongs to subject or test environment.
- **Features** — normalized machine-readable fields suitable for comparison.
- **Inference** — model/rule output separated from observed facts, with confidence/evidence trace.
- **Decision** — priority/ranking/fit/action recommendation with visible component scores.
- **Audit** — schema, inference/tool versions, run ID, timestamp, artifact IDs.

## Design rules
1. **Evidence before inference.** Model output never masquerades as source fact.
2. **Feature Store, not tracker.** Sheets/databases are long-lived analytical assets.
3. **Schema-first.** Domain workflows emit stable JSON before writing to Sheets/Notion/Drive.
4. **Idempotent upsert.** Re-running the same object/version updates the same entity.
5. **Recomputable inference.** Observed data is immutable-ish; derived/inferred layers may be recalculated.
6. **Environment vs subject failure.** Harness failures are not attributed to the tested object.
7. **Confidence is data.** Inference exposes confidence, version, and evidence summary.
8. **Human time goes to decisions.** Agents collect/normalize/verify; humans inspect ranked signal or exceptions.
9. **Comparison must be explainable.** Similarity/ranking emits feature-level reasons and coverage, not only a score.
10. **Missing evidence is not zero.** Pairwise comparison ignores unavailable dimensions and reports coverage.
11. **Uncalibrated features stay descriptive.** A vector can support similarity without being promoted into a normative score.
12. **Domain policies are separate from the engine.** The generic engine does math; adapters define projections, weights, and decision semantics.

## Adapter contract
A domain adapter SHOULD provide:
- `identity_adapter`
- `evidence_collector`
- `normalizer`
- `verifier`
- `feature_emitter`
- optional `graph_builder`
- optional `inference_modules`
- `comparison_policy`
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

## Compare Core v0.6
Generic executor: `tools/evidence_feature_compare.py`.

Inputs:
- canonical JSON records, JSONL/NDJSON, or a directory of feature records;
- a domain comparison policy.

Outputs per object:
- deterministic `cluster_id`;
- nearest peers;
- similarity + pair evidence coverage;
- top similar dimensions;
- top differing dimensions;
- anomaly score;
- explainable ranking score;
- ranking coverage;
- per-component ranking contributions.

Implementation deliberately uses standard-library robust statistics and pairwise available-feature distance so it can run in lightweight CI without sklearn.

The engine does **not** define what “good” means. Domain ranking rules live in policy files. A domain may use a feature for similarity while forbidding it from ranking until calibration exists.

## Enterprise reuse examples
- **Game QA**: package/build -> smoke/crash/input/perf features -> peer builds -> regression anomaly -> release queue.
- **Recruiting**: job posting + email thread -> normalized role features -> similar roles -> fit/urgency ranking -> action queue.
- **Research**: source corpus -> claims/evidence graph -> hypothesis features -> comparable cases -> contradiction/anomaly queue.
- **Document operations**: files -> completeness/compliance features -> peer templates -> outlier detection -> exception queue.
- **Asset triage**: packages -> identity/hash/structure -> recoverability/value -> similar assets -> storage priority.

## Production architecture
The Fangame adapter demonstrates a fully decoupled three-stage pipeline:

`Fangame Fetch (Evidence Collector)`
→ `Fangame Feature Store (Normalizer / Feature Emitter)`
→ `Fangame Compare (Cross-object Compare / Rank)`

The stages communicate through artifact contracts rather than hidden process state. Any future sandbox, enterprise CI, or other domain adapter can enter at the stage for which it already has valid evidence.

## First production adapter
`fangame-playability-miner` is the first concrete adapter. RPG Maker was chosen because it provides strong ground truth: binary identity, inspectable data files, runtime smoke evidence, measurable content structure, graphable state machines, and repeatable CI.

## Non-negotiable
The system exists to make accumulated work **more valuable over time**. If a run only produces a transient answer and no reusable evidence/feature state when persistence is possible, the flow is incomplete.
