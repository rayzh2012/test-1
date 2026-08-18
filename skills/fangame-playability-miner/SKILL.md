---
name: fangame-playability-miner
description: Evidence→Feature→Inference Flow 的 Fangame domain adapter。Rescue 后对 fangame 做包身份校验、RPG Maker 静态内容挖掘、CI 启动与输入烟测、标准 Feature Record、后续结构图/支线/结局/时长/Grinding 保守推断，并写入 Fangame Feature Store。调用场景：新 rescue、补测可玩性、判断内容丰富度、批量排序真正值得玩的游戏。
version: 0.2
allowed-tools: [github, google_drive, notion, web, code_execution, file_ops]
---

# Fangame Playability & Content Mining Skill

## Architecture
This Skill is the first production adapter of the generic `evidence-feature-inference-flow` Skill.

Core pattern:

`Raw Evidence -> Identity -> Observed Features -> Runtime Verification -> Derived Metrics -> Conservative Inference -> Ranking -> Action/Audit`

Fangame adapter:

`Binary Preservation -> Structural Understanding -> Runtime Evidence -> Canonical Feature Record -> Semantic Graph -> Conservative Inference -> Personal Ranking`

The spreadsheet/Excel asset is a **Fangame Feature Store**, not merely a registry.

## Evidence classes
Every persisted field belongs conceptually to one of:
- `OBSERVED`: directly measured from files/runtime.
- `DERIVED`: deterministic calculation from observed values.
- `INFERRED`: model/rule inference with confidence, version and evidence summary.
- `UNKNOWN`: evidence is insufficient. Never fill gaps by guessing.

Observed facts survive future inference-model revisions.

## v0.2 canonical data contract
Every successful normalization stage emits:
- `fangame_features.json` — one canonical record per game/package.
- `fangame_features.schema.json` — machine-readable schema contract.
- batch `fangame_feature_store.ndjson` — append/stream-friendly analytical asset.
- batch `fangame_feature_store.csv` — Excel/Sheets-friendly flattened feature table.

Schema: `schemas/fangame_features.schema.json`
Emitter: `tools/fangame_feature_emitter.py`
Batch exporter: `tools/fangame_feature_batch.py`
Normalizer workflow: `.github/workflows/fangame-feature-store.yml`

The normalizer is deliberately decoupled from the fetcher. `Fangame Fetch` is an **Evidence Collector**; `Fangame Feature Store` is a **Normalizer/Feature Emitter**. Any future sandbox or enterprise CI can integrate by producing the same evidence contract.

## Pipeline

### P0 Package identity
Verify source, filename, bytes, archive magic, SHA256, version/lineage, complete game vs patch/stub/repack.

### P1 Static structure mining
For inspectable RPG Maker packages collect at minimum:
- engine / RGSS version
- maps and map bytes
- events / event pages / event commands
- dialogue lines / dialogue chars
- choices
- common events
- switches / variables
- transfers / battle calls / shops
- actors / classes / skills / items / weapons / armors / enemies / troops / states
- image / audio / script counts and bytes

Encrypted/opaque packages retain an explicit opacity boundary.

### P2 CI runtime smoke
Runtime evidence stages are independent gates:
1. `TITLE_VERIFIED`
2. `NEW_GAME_VERIFIED`
3. `INPUT_FLOW_VERIFIED`
4. `MAP_GAMEPLAY_VERIFIED`
5. future: `BATTLE_VERIFIED`, `SAVE_LOAD_VERIFIED`

Mechanical smoke evidence and screenshot semantic claims remain separate. CI environment failures (Wine/audio/font/Xvfb) must not be mislabeled as game failures.

### P2.5 Canonical Feature Emit
Normalize fetch/static/smoke/review evidence into `fangame.features.v0.2`.

Top-level sections:
- `identity`
- `observed`
- `runtime`
- `derived`
- `inferred`
- `ranking`
- `evidence`
- `audit`

v0.2 intentionally leaves unsupported inference fields as `UNKNOWN` / null. It does not manufacture sidequest/ending counts merely to populate the table.

### P3 Semantic mining
Parse event/data semantics into:
- dialogue clusters
- task accept/progress/complete/reward patterns
- boss/combat gates
- shops/heal/transport/save-point patterns
- ending/credits/title-return/fadeout signals
- switch/variable read-write relationships
- map transfer graph
- event/script call graph

Produce Event Graph, Map Graph, Switch/Variable Dependency Graph.

### P4 Derived features
Deterministic examples:
- `dialogue_density_per_map`
- `event_command_density_per_map`
- `choice_density_per_1000_commands`
- `transfer_density_per_map`
- `system_object_count`
- `asset_count`
- `content_richness_score_5`
- future `optional_graph_ratio`, `terminal_map_count`, `reward_loop_count`

### P5 Sidequest inference
A `SIDEQUEST_CANDIDATE` should combine several signals:
- branch from likely mainline and rejoin path
- local switch/variable state with limited blast radius
- accept -> progress -> complete/reward transition
- dedicated NPC/map/boss/item-reward cluster
- weak dependence on core mainline gates
- skipping cluster still leaves route to later mainline

Output candidate count, cluster count, optional-content ratio, confidence and evidence summary. Candidate count is NOT official quest count.

### P6 Ending inference
Use combinations of credits/END resources, fade/title return/terminate, final-boss terminal paths, switch-conditioned terminal clusters and ending-specific dialogue/images/music.

If evidence only supports at least one terminal route, record `>=1` rather than invent an exact number.

### P7 Time / Grinding inference
Use ranges and confidence rather than fake precision. Candidate inputs:
- map/event/dialogue scale
- traversal distances
- encounter structure
- EXP rewards / level curves
- economy / shop prices
- recovery / teleport / speed-up
- failure penalties
- repeat-map / repeat-combat ratios

## Ranking separation
Keep independent:
- historical player reputation
- CI playability
- AI structural richness
- personal fit

Do not collapse everything into one unexplained score. Final priority may be computed, but component evidence must remain visible.

## Current executors
Repository: `rayzh2012/test-1`

Evidence collection:
- `tools/fangame_fetcher.py`
- `tools/fangame_inspect.py`
- `tools/rpgmaker_marshal_probe.rb`
- `tools/fangame_smoke.py`
- `tools/fangame_review_card.py`
- `.github/workflows/fangame-fetch.yml`

Feature normalization:
- `schemas/fangame_features.schema.json`
- `tools/fangame_feature_emitter.py`
- `tools/fangame_feature_batch.py`
- `.github/workflows/fangame-feature-store.yml`

Known benchmark: `怒龙战记3 V3.0` has verified title, New Game and input flow; map gameplay remains a separate gate.

## Roadmap
- [x] v0.1: Skill contract, evidence classes, feature-store concept, inference boundaries.
- [x] v0.2: canonical feature schema + JSON emitter + NDJSON/CSV analytical export + decoupled normalizer workflow.
- [ ] v0.3: Event/Map/Switch graph exporter.
- [ ] v0.4: sidequest and ending candidate inference.
- [ ] v0.5: playtime and grind-pressure interval model.
- [ ] v0.6: cross-game clustering and ranking.

## Non-negotiable rule
`OBSERVED != INFERRED`.

The goal is not merely to answer whether one game works. The goal is to make every tested game increase the value of the whole dataset and make the next decision easier.
