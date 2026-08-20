# Step 4A — SkillInfo population audit without inventing the missing data

## Objective

After Step 3 proved a loss-aware mapper over the real upstream `SkillInfo` type, the next question was empirical: which unsupported semantics actually dominate the PAL3 skill population?

That question cannot be answered honestly from hand-built fixtures. The first task was therefore to locate lawful original PAL3 GDB input, while separately building reusable audit machinery that could run immediately once such input exists.

## Data-input discovery

Upstream `GameResourceProvider` identifies the runtime database as `CombatData/<AppName>_Softstar.gdb` and exposes parsed `SkillInfos` from that database.

The open-source repository does not commit the commercial GDB file. Connected Google Drive searches for `Softstar.gdb` and `PAL3` returned no original database file; Chinese-title searches returned unrelated guide material.

**Classification: `DATA_INPUT_BLOCKER`.**

This is not a code failure. No fake population was substituted.

## Audit engine

`GdbSkillPopulationAudit` was added as an input-agnostic consumer of `IEnumerable<SkillInfo>`.

It reports:

- total skills;
- execution-ready skills;
- blocked skills;
- execution-ready ratio;
- info-only skills;
- issue frequency grouped by mapper issue code and severity;
- sorted representative skill IDs with a configurable cap.

The auditor delegates semantic judgment to the existing loss-aware `GdbSkillInfoMapper`; it does not reinterpret unsupported semantics itself and does not mutate input records.

## Attempt 2.1 — patch replay failed before tests

The first code-bearing run did not reach NUnit.

Fast Lane run `32339928133` failed at the patch replay gate because both newly authored unified diffs had incorrect new-file hunk counts:

- `0009-skill-population-audit.patch` declared 163 added lines but contained 159;
- `0010-skill-population-audit-tests.patch` declared 230 added lines but contained 172.

Artifact: `9395977698`  
SHA256: `22e16828a7e4dd8f7acdebaad125814ca7346ac65e886671c4c525fc2b5742de`

The semantic implementation was not changed. Only the two hunk headers were corrected.

## Attempt 2.2 — verified

After correcting those headers, source replay and the fast domain lane passed.

Fast Lane run: `32340164174`  
Source Audit run: `32340164155`  
Evidence artifact: `9396063171`  
Artifact SHA256: `6774b3b2b118a55c52595a6c6b91cad18fb317e9eedd2975ed62ab82d54e39cd`

Machine result:

```text
51 total
51 executed
51 passed
0 failed
0 skipped
0 compiler warnings
120 ms
```

The six new tests cover empty populations, mixed ready/blocked populations, issue-frequency counting, deterministic/capped example IDs, info-only metadata, and non-mutation of source skill semantics.

## What this proves

The project now has a verified population-audit layer that can rank semantic blockers as soon as real parsed PAL3 `SkillInfo` data is supplied.

It also proves the workflow can preserve a mixed terminal state accurately:

- audit machinery: **VERIFIED**;
- real PAL3 population measurement: **BLOCKED_NO_INPUT**.

## What this does not prove

No claim is made about the real frequency of multi-element skills, percentage MP/SP costs, special consumption, success-rate semantics, composite skills, or any other blocker in the commercial PAL3 dataset.

No Unity runtime, VFX, or original-formula fidelity claim is added by this experiment.

## Reusable lessons

1. Missing commercial input is a data blocker, not a code failure.
2. A reusable measurement instrument can be built before the data arrives.
3. New-file unified-diff line counts remain a recurring mechanical failure mode; patch replay must stay blocking.
4. Do not select the next semantic implementation by pretending synthetic fixtures are representative of the original game.

## Next

When lawful `Softstar.gdb` or already parsed original `SkillInfo` records become available, run them through this auditor first. Until then, independent roadmap work should target infrastructure that does not require fabricated population-frequency assumptions.
