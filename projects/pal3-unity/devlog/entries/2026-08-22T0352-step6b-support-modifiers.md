# Step 6B1 — Source-grounded temporary support modifiers

## Objective

Continue PAL3 combat Roadmap Step 6 after verified HP recovery by implementing the smallest support-stat slice that is explicitly grounded in pinned upstream source.

The pinned `ActorCombatStateType` already names eight temporary modifier states and annotates each one as ±10%:

- AttackIncrease / AttackDecrease;
- DefenseIncrease / DefenseDecrease;
- SpeedIncrease / SpeedDecrease;
- LuckIncrease / LuckDecrease.

This is enough evidence to model **state presence and modifier metadata**. It is not enough evidence to invent duration, stacking, refresh/cancellation, or integer rounding.

## Domain design

The new path is:

```text
AssistMagic SkillDefinition
→ FirstPartySingle / FirstPartyAll target resolution
→ validate state identity / conflict / resource preconditions
→ spend MP once
→ apply or remove encounter-local support state
→ SkillCast fact
→ target-addressed CombatStateChanged fact(s)
```

`CombatantState` now owns encounter-local combat-state presence and exposes `GetSupportModifierPercent` for Attack / Defense / Speed / Luck. The return value is -10, 0 or +10 based on the exact upstream state annotation.

The percentage is **not yet multiplied into Attack/Defense or scheduler math**. That is deliberate: the current evidence does not establish PAL3's integer rounding point, duration or replacement rules.

## Supported behavior

- `SkillType.AssistMagic` only;
- `FirstPartySingle` and `FirstPartyAll` only;
- one support combat-state effect per skill;
- the eight Attack / Defense / Speed / Luck increase/decrease states only;
- `CombatStateImpactType.Increase` and `Remove`;
- deterministic party-all order through the existing target resolver;
- self-support through a valid first-party single anchor;
- one MP spend per cast;
- typed immutable `CombatStateChanged` events.

Expected invalid operations reject **before** MP or state mutation:

- duplicate application;
- removing a state that is not active;
- applying an increase while the matching decrease is active, or vice versa;
- aliased target states;
- unsupported state families such as poison;
- wrong skill type or target range;
- SP-consuming support skills in this slice;
- insufficient MP.

## Attempt 1 — fast-lane compile failure

Source Audit passed and the ordered patch stack replayed correctly, but the first Fast Lane failed before tests executed.

- Source Audit run: `32561216589` — PASS
- Fast Lane run: `32561216579` — FAIL_COMPILE
- Artifact: `9472824162`
- Artifact SHA256: `b9644476ab680570596d0b61cbe75c7e647026098bd3209e59dfea1056803208`

Compiler error:

```text
CombatEvent.cs(81,31): CS0120
An object reference is required for the non-static field, method, or property
'CombatEvent.CombatStateImpactType'
```

### Root cause

The new immutable event property was named `CombatStateImpactType`, the same identifier as the enum type. Inside the static factory, the unqualified `CombatStateImpactType.None` therefore resolved ambiguously toward the instance property.

### Fix

Ordered patch `0029` fully qualifies:

```text
Pal3.Core.Contract.Enums.CombatStateImpactType.None
```

No combat semantics changed.

## Attempt 2 — domain green, legacy compile-gate harness exposed

After the qualification fix:

- Source Audit run: `32561268576` — PASS
- Fast Lane run: `32561268552` — PASS
- **135 passed / 0 failed / 0 skipped**
- Duration: 140 ms
- Fast artifact: `9472839320`
- Artifact SHA256: `109ab955cd12d55e6b1fb4a05011e424be967fbc4c4932407fab156d84190fdc`

The separate Unity Compile Gate then failed **before Unity** because its old scratch .NET harness still copied only `CombatCore.cs` and `CombatCoreTests.cs`. Step 6B made `CombatCore` legitimately depend on pinned `ActorEnums` / `CombatEnums`, so that hand-maintained harness had drifted behind the actual registered domain dependency graph.

This was classified as **CONTROL_PLANE_HARNESS_DRIFT**, not a PAL3 domain failure.

### Control-plane fix

The Unity Compile Gate was changed to reuse the same `fast-tests.json` + `pal3_fastlane.py` manifest as the Chat Fast Lane instead of maintaining a second hand-written dependency list.

This removes an entire class of future false failures as the combat domain grows.

## Attempt 3 — terminal verification

Current terminal pre-publication head:

- Source Audit run: `32561349662` — PASS
- Fast Lane run: `32561349663` — PASS
- **135 passed / 0 failed / 0 skipped**
- Duration: 171 ms
- Fast artifact: `9472863161`
- Fast artifact SHA256: `02e0f9b519de330d8ca9948d93ac11910b27af744ccf895307d11550bbc12a29`
- Unity Compile Gate run: `32561349674` — SUCCESS for patch replay + registered domain gate
- Compile evidence artifact: `9472864077`
- Compile evidence SHA256: `0a55e765811bc568def4d04cc6485d26f33461645dbde67706828e1489e03e50`

Unity import/build itself remains:

```text
BLOCKED_NO_LICENSE
```

The gate correctly skipped GameCI because no Unity activation material is configured. That is not promoted to Unity compile success.

## What is now verified

- encounter-local presence for all eight source-declared temporary support modifier states;
- exact -10/0/+10 modifier metadata for Attack / Defense / Speed / Luck;
- single-ally, self and party-all targeting;
- deterministic target order;
- one-time MP transaction;
- typed `CombatStateChanged` facts;
- pre-mutation rejection of known invalid/conflicting operations;
- the shared domain test manifest can be reused by both Fast Lane and Compile Gate without dependency drift.

## Claim boundary

This step **does not** establish:

- how many rounds the modifier lasts;
- whether recasting refreshes duration;
- whether opposing states cancel, replace or are prohibited in original PAL3;
- whether identical states stack;
- where integer rounding occurs when ±10% is applied;
- how Speed interacts with the future action scheduler;
- how Luck affects original formulas;
- support VFX or animation timing;
- Unity compilation/runtime, iOS build or playtest.

Those remain separate evidence questions.

## Publication state

This Markdown file is the canonical publication source for this experiment. The project publication policy now treats **GitHub Gist** as the normalized “snippet” mirror and also lists **Medium** and **知乎** as mirrors.

No writable authenticated Gist / Medium / 知乎 transport is currently connected, so external mirror publication is intentionally deferred. Engineering is never blocked on a publishing platform.

## Next information gain

Before consuming the ±10% values in effective combat math, inspect source/data/runtime evidence for:

1. modifier duration;
2. refresh / replacement / cancellation semantics;
3. integer rounding point;
4. whether Speed and Luck use the same effective-value pipeline as Attack / Defense.

If those remain ungrounded, keep the state metadata verified but move lifecycle-heavy poison/control/reflection mechanics into Roadmap Step 7 rather than inventing behavior.
