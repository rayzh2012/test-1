---
name: fangame-playability-miner
description: Evidence→Feature→Inference Flow 的 Fangame production adapter。Rescue 后完成包身份校验、RPG Maker/RGSS/MV-MZ 静态挖掘、CI 可玩性烟测、图结构、支线/结局候选、progression/grind evidence vector、canonical Feature Store，以及跨游戏相似度/聚类/异常/解释型排名。
version: 0.6
allowed-tools: [github, google_drive, notion, web, code_execution, file_ops]
---

# Fangame Playability & Content Mining Skill

## Architecture
This is the first production adapter of `evidence-feature-inference-flow`.

`Binary / Public Package`
→ `Evidence Collector`
→ `Static + Runtime Evidence`
→ `Canonical Feature Store`
→ `Graph + Conservative Inference`
→ `Progression / Grind Evidence Vector`
→ `Cross-game Compare / Cluster / Rank`
→ `Human or Automation Action`

The spreadsheet/NDJSON/JSON assets are analytical **Feature Stores**, not mere registries.

## Evidence classes
Persisted fields remain separated as:
- `OBSERVED`
- `DERIVED`
- `INFERRED`
- `UNKNOWN`

Observed facts survive future model revisions. Candidate counts are never silently promoted into official quest/ending counts.

## P0 Preservation / identity
Validate the real package before analysis:
- source/provenance
- filename/version/lineage
- bytes/archive magic
- SHA256
- complete game vs patch/stub/repack
- Drive archival/readback when rescue is in scope

## P1 Static mining
Supported lanes now include classic RPG Maker/RGSS plus newer MV/MZ-oriented genome work.

Classic RGSS evidence includes maps, event pages/commands, dialogue, choices, common events, switches/variables, transfers, battles, shops, database objects, assets, progression/economy evidence, and script/opacity boundaries.

## P2 Runtime verification
Mechanical runtime and semantic screenshot evidence remain independent gates. Environment failure is never mislabeled as game failure.

Typical gates:
- title/window evidence
- New Game / confirm response
- input flow
- map gameplay
- future battle/save-load/long-run semantic evidence

## P3 Canonical Feature Store
Main normalizer workflow:
`.github/workflows/fangame-feature-store.yml`

Current canonical record line reaches `fangame.features.v0.5b` and contains:
- `identity`
- `observed`
- `runtime`
- `derived`
- `graph`
- `inferred`
- `progression`
- `grind_vector`
- `ranking`
- `evidence`
- `audit`

Outputs include per-game JSON plus NDJSON/CSV analytical assets.

## P4 Graph evidence
`tools/rpgmaker_graph_probe.rb` extracts observed graph evidence such as:
- map-transfer edges
- event-page/common-event nodes
- switch/variable/self-switch reads and writes
- common-event calls
- choices/branches/battles/shops
- terminal signals
- graph connectivity/locality summaries

## P5 Conservative sidequest / ending inference
`tools/fangame_graph_inference.py` separates:
- optional structural clusters
- semantically promoted sidequest candidates
- ending candidates / terminal clusters

Promotion requires evidence combinations; topology alone is not called a quest.

## P6 Progression / grind evidence
Progression probe and `fangame_grind_vector.py` normalize encounter/economy/reward/battle/shop/transfer signals.

Important boundary: v0.5b grind vector is **UNLABELED_VECTOR_ONLY**. It deliberately emits no grind-pressure score and no hours estimate until a labeled calibration corpus exists.

## P7 Cross-game Compare v0.6
Generic engine:
`tools/evidence_feature_compare.py`

Fangame policy:
`policies/fangame_compare_v06.json`

Workflow:
`.github/workflows/fangame-compare.yml`

Outputs:
- nearest peer games
- similarity score and evidence coverage
- top matching/differing dimensions
- deterministic clusters
- anomaly score
- explainable ranking score
- component contributions and ranking coverage

Uncalibrated grind-vector dimensions may participate in neutral similarity, but are forbidden from ranking until calibration exists.

## Public genome lane
The broader system also has an in-progress public analysis/corpus lane for sanitized fangame genome reports. Publication boundaries exclude private archive metadata, Drive IDs, private notes, and binaries. This lane can become a natural cross-game corpus source for the Compare Core once merged into the canonical branch.

## Current executors
Evidence / runtime:
- `tools/fangame_fetcher.py`
- `tools/fangame_inspect.py`
- `tools/rpgmaker_marshal_probe.rb`
- `tools/rpgmaker_graph_probe.rb`
- `tools/rpgmaker_progression_probe.rb`
- `tools/fangame_smoke.py`

Feature / inference:
- `tools/fangame_feature_emitter.py`
- `tools/fangame_graph_feature_merge.py`
- `tools/fangame_graph_inference.py`
- `tools/fangame_inference_feature_merge.py`
- `tools/fangame_progression_feature_merge.py`
- `tools/fangame_grind_vector.py`
- `tools/fangame_feature_batch.py`

Cross-object:
- `tools/evidence_feature_compare.py`
- `policies/fangame_compare_v06.json`

## Roadmap
- [x] v0.1 Skill/evidence contract
- [x] v0.2 canonical schema + feature store
- [x] v0.3 map/event/state graph evidence
- [x] v0.4 optional/sidequest/ending candidate inference
- [x] v0.5a progression evidence
- [x] v0.5b normalized grind vector without fabricated score
- [x] v0.6 generic cross-game comparison/clustering/anomaly/explainable ranking core
- [ ] v0.7 labeled calibration corpus for grind/hour models
- [ ] v0.8 active-learning loop: choose next game/test based on uncertainty reduction and information gain

## Non-negotiable
`OBSERVED != DERIVED != INFERRED`.

Every tested game should make the dataset more useful, improve peer comparisons, and reduce the cost of deciding what to test/play/rescue next.
