---
name: fangame-playability-miner
description: Rescue 后对 fangame 做包身份校验、RPG Maker 静态内容挖掘、CI 启动与输入烟测、结构图构建、支线/结局/时长/Grinding 保守推断，并把 observed/derived/inferred 特征写入 Fangame Feature Store。调用场景：新 rescue、补测可玩性、判断内容丰富度、批量排序真正值得玩的游戏。
version: 0.1
allowed-tools: [github, google_drive, notion, web, code_execution, file_ops]
---

# Fangame Playability & Content Mining Skill

## Goal
Turn each rescued fangame into a structured evidence object rather than a mere archived binary:

`Binary Preservation -> Structural Understanding -> Runtime Evidence -> Semantic Graph -> Conservative Inference -> Personal Ranking`

The spreadsheet/Excel asset is a **Fangame Feature Store**, not just a registry.

## Evidence classes
Every field must be one of:
- `OBSERVED`: directly measured from files or runtime.
- `DERIVED`: deterministic calculation from observed values.
- `INFERRED`: model inference with confidence and evidence summary.
- `UNKNOWN`: insufficient evidence; never fill by guessing.

Never overwrite observed facts with later inference-model revisions.

## Pipeline

### P0 Package identity
Verify source, filename, bytes, archive magic, SHA256, version/lineage, and whether the artifact is a complete game vs patch/stub/repack.

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

Encrypted/opaque packages must explicitly retain an opacity boundary.

### P2 CI runtime smoke
Runtime evidence stages are independent gates:
1. `TITLE_VERIFIED`
2. `NEW_GAME_VERIFIED`
3. `INPUT_FLOW_VERIFIED`
4. `MAP_GAMEPLAY_VERIFIED`
5. future: `BATTLE_VERIFIED`, `SAVE_LOAD_VERIFIED`

Keep screenshots, runtime log, and smoke JSON. Distinguish CI environment failures (Wine/audio/font/Xvfb) from game failures.

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

Produce:
- Event Graph
- Map Graph
- Switch/Variable Dependency Graph

### P4 Derived features
Deterministic examples:
- `dialogue_density`
- `event_density`
- `choice_density`
- `transfer_density`
- `system_breadth`
- `asset_diversity`
- `optional_graph_ratio`
- `terminal_map_count`
- `branch_point_candidates`
- `reward_loop_count`
- `local_switch_cluster_count`

### P5 Sidequest inference
A `SIDEQUEST_CANDIDATE` should combine several signals rather than rely on choice count alone:
- branches from likely mainline and can rejoin it
- local switch/variable state with limited blast radius
- accept -> progress -> complete/reward state transitions
- dedicated NPC/map/boss/item-reward cluster
- weak dependence on core mainline gates
- skipping the cluster still leaves a route to later mainline content

Output:
- `sidequest_candidate_count`
- `sidequest_cluster_count`
- `optional_content_ratio`
- `sidequest_confidence`
- `sidequest_evidence_summary`

Candidate count is NOT an official quest count.

### P6 Ending inference
An `ENDING_CANDIDATE` can combine:
- credits/staff/END text or resources
- fadeout + BGM stop + title return/game terminate
- final-boss path into terminal map/cluster
- different switch/variable conditions reaching distinct terminal clusters
- ending-specific dialogue/images/music

Output:
- `ending_candidate_count`
- `distinct_terminal_cluster_count`
- `ending_branch_depth`
- `ending_confidence`
- `ending_evidence_summary`

If evidence only proves at least one terminal path, record `>=1`.

### P7 Time / grinding inference
Do not pretend to know precise hours. Use ranges and confidence. Inputs may include:
- map/event/dialogue scale
- movement distances
- fixed/random encounter structure
- EXP rewards and level curves
- shop prices/economy
- recovery/teleport/speed-up
- failure penalties
- repeat-map and repeat-combat ratios

Example output: `estimated_main_story_hours = 15-25h (MEDIUM)`.

## Scoring separation
Keep four independent scores:
- historical player reputation
- CI playability
- AI structural richness
- personal fit

AI structural score must never be presented as a completed-play review.

## Fangame Feature Store schema

### Identity
`game_id,title,version,engine,sha256,bytes,lineage,source,drive_ids`

### Observed structure
`maps,events,event_pages,event_commands,dialogue_lines,dialogue_chars,choices,common_events,transfers,battle_calls,shops,switches,variables,scripts,actors,skills,items,enemies,audio_count,image_count`

### Runtime
`ci_status,title_verified,new_game_verified,input_flow_verified,map_gameplay_verified,runtime_error_class,evidence_drive_id`

### Derived
`dialogue_density,event_density,choice_density,system_breadth,content_richness,optional_graph_ratio`

### Inferred
`sidequest_candidate_count,sidequest_confidence,ending_candidate_count,ending_confidence,estimated_hours_range,grind_pressure,inference_version`

### Ranking
`historical_rating,ai_structural_score,ci_playability_score,personal_fit_score,final_priority`

## Current executors
Repository: `rayzh2012/test-1`

- `tools/fangame_fetcher.py`
- `tools/fangame_inspect.py`
- `tools/rpgmaker_marshal_probe.rb`
- `tools/fangame_smoke.py`
- `tools/fangame_review_card.py`
- `.github/workflows/fangame-fetch.yml`

Known benchmark: `怒龙战记3 V3.0` has verified title, New Game, and input flow; map gameplay remains a separate gate.

## Roadmap
- v0.1: skill contract, evidence classes, feature-store schema, inference boundaries.
- v0.2: persist feature-store fields + CI JSON sidecar automatically.
- v0.3: event/map/switch graph exporter.
- v0.4: sidequest and ending candidate inference.
- v0.5: playtime and grind-pressure interval model.
- v0.6: cross-game clustering and ranking.

## Non-negotiable rule
`OBSERVED != INFERRED`.

If evidence is missing, write `UNKNOWN`. The purpose of the skill is to reduce uncertainty, not hide it.
