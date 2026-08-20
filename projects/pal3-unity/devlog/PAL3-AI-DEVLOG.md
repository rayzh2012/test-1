# Rebuilding PAL3 Combat with ChatGPT as the Control Plane

_A running engineering devlog of what was attempted, what failed, what passed on real machines, and what remains unproven._

This is the human-readable publication layer for the PAL3.Unity rewrite-control experiment. The goal is not to make the work look smoother than it was. The goal is to preserve enough detail that a future developer — human or AI worker — can understand the actual engineering path without reconstructing it from chat history.

The canonical code-control repository is `rayzh2012/test-1`. The upstream rewrite is `0x7c13/Pal3.Unity`, pinned at `cfed96a21fde248e93e64a47d465b2a9f839ccf8` for the experiments recorded here.

The original PAL3/PAL3A commercial game data remains external and user-supplied. None of this log changes the copyright status of the original assets.

---

## 0. Why this project exists

PAL3.Unity is unusually attractive for AI-directed completion because much of the hard groundwork already exists:

- the world, scenes, resource readers, actors and plot plumbing are substantially present;
- combat already has scene loading, formations, actor placement and attack-animation scaffolding;
- the project is heavily code-driven rather than Inspector-driven;
- PAL3 combat data is already represented by rich structures such as `CombatActorInfo` and `SkillInfo`;
- the upstream repository explicitly leaves combat and surrounding systems incomplete.

The working hypothesis became:

> If combat rules can be separated into a deterministic pure-C# domain, ChatGPT can author, test and repair that domain rapidly, while Unity becomes a presentation/runtime adapter around machine-tested rules.

The intended development loop is:

```text
CHAT
→ normalized command
→ read exact source
→ smallest patch
→ replay on pinned upstream
→ fast tests
→ machine evidence
→ ChatGPT re-ingests result
→ next patch
```

A heavier lane remains separate:

```text
Unity activation
→ import / compile
→ EditMode / runtime
→ iOS build
→ playtest
```

This distinction matters because environmental failure must not be misreported as code failure.

---

## 1. Control plane installed

### Objective

Create a control repository that can modify PAL3.Unity without forking or copying the whole upstream tree into the control plane.

### What was built

The control repo gained:

- a project manifest with the upstream repository and pinned ref;
- an ordered patch stack;
- a source-rewrite controller;
- GitHub Actions source-audit workflow;
- a reusable open-source game rewrite skill;
- a policy that the upstream repository remains read-only from this control plane.

The core architecture became:

```text
PINNED UPSTREAM
→ SOURCE EVIDENCE
→ ORDERED PATCH STACK
→ git apply --check
→ apply
→ git diff --check
→ CI evidence artifact
→ ChatGPT re-ingest
```

### Result

The first integration and validation PRs succeeded. The project could now reproduce a known upstream checkout and audit it deterministically.

### Failure observed

None at the architectural bootstrap level that invalidated the approach.

### Reusable lesson

Do not let an AI rewrite project depend on an opaque local working tree. A pinned upstream plus replayable ordered patches gives every worker the same starting state and makes conflicts explicit.

---

## 2. First real source audit

### Objective

Measure the actual source surface before guessing what “unfinished combat” means.

### Machine result

The first real GitHub Actions audit reported approximately:

- 582 source files;
- 59,593 source lines;
- 21 TODO markers;
- 8 `NotImplementedException` markers;
- 9 `NotSupportedException` markers;
- 153 generic exception throws.

The high-value observation was not the raw marker count. It was the distribution: `Pal3.Game/GameSystems` contained gameplay-relevant TODOs, while many parser exceptions in `Pal3.Core/DataReader` were defensive/format-related and could not be treated as “missing feature” counts.

### Result

Combat was confirmed as a real incomplete gameplay surface by both source comments and audit evidence.

### Failure / trap identified

A raw TODO/exception count is a poor backlog. Defensive guards, unsupported file variants and intentionally unimplemented branches can look identical to genuine feature gaps if an AI only scans markers.

### Reusable lesson

Every future worker must classify a marker before converting it into work:

`defensive guard` vs `unsupported branch` vs `real implementation gap`.

---

## 3. CombatCore v0.0 — first deterministic 1v1 slice

### Objective

Prove that ChatGPT can add a real combat-domain slice to PAL3.Unity and have it machine-verified.

### What was added

The first patch introduced a pure-C# feasibility core:

- `CombatantState` with HP / Attack / Defense;
- `NormalAttackResolver`;
- `CombatDuel` terminal state machine;
- EditMode-style NUnit tests authored against the same source.

The temporary damage formula was deliberately simple:

```text
max(1, Attack - Defense)
```

It was explicitly labelled **FEASIBILITY BASELINE ONLY**. It was never claimed to be the original PAL3 formula.

### Attempt 1 — patch apply succeeded, evidence was wrong

The patch itself applied, but the controller produced an incorrect evidence report:

- newly created files were not listed as changed;
- `applied.patch` was empty.

### Root cause

`git apply` created untracked files, while plain `git diff` ignores untracked files.

### Fix

The controller was upgraded so it discovers untracked files and runs `git add --intent-to-add`. This makes new files visible to:

- `git diff`;
- `git diff --check`;
- the generated binary/unified patch evidence.

### Attempt 2 — PASS

The second audit showed the three new files correctly, with a non-empty `applied.patch` and clean diff checking.

### Additional execution proof

The exact patched `CombatCore.cs` and authored tests were then compiled and executed under .NET/NUnit on GitHub Actions.

Result:

```text
10 passed
0 failed
0 skipped
```

### Reusable lesson

A control plane needs tests for its own evidence machinery. “The patch applied” and “the evidence artifact accurately describes the patch” are separate claims.

---

## 4. First Unity compile attempt — environmental blocker discovered

### Objective

Move from pure-domain proof to real Unity project compilation.

### What was tried

A compile gate replayed the PAL3 patch stack and then invoked the same GameCI family used by upstream Unity workflows.

### Result

The workflow reached Unity Builder, but the environment exposed empty values for:

- `UNITY_LICENSE`;
- `UNITY_EMAIL`;
- `UNITY_PASSWORD`.

GameCI stopped with a missing-license/activation error before PAL3 C# project compilation.

### Classification

**ENVIRONMENT / ACTIVATION BLOCKER**, not code failure.

Unity never got far enough to prove or disprove compilation of the patched project.

### Fix to the workflow

The compile gate was normalized so missing activation becomes an explicit state:

```text
BLOCKED_NO_LICENSE
```

The workflow can remain green for the fast-domain lane while truthfully recording that Unity compilation has not been verified.

### Reusable lesson

Never let infrastructure prerequisites collapse into a generic red CI status. A future worker must be able to distinguish:

- code failed;
- tests failed;
- patch failed;
- environment blocked execution.

---

## 5. ChatGPT realtime fast lane

### Objective

Turn the project from “AI-assisted coding” into a low-latency ChatGPT control loop.

### What was added

A dedicated fast lane was created:

```text
conversation
→ normalized command
→ pinned upstream checkout
→ replay ordered patches
→ source/diff audit
→ compile Unity-independent domain slice
→ NUnit
→ evidence artifact
→ ChatGPT reads result
```

This lane intentionally does not require Unity activation.

### Result

The first realtime fast-lane execution ran the CombatCore tests successfully and returned machine evidence to the same conversation-driven workflow.

### Design decision

Cursor became optional fallback rather than a required middle layer.

### Reusable lesson

Low-latency verification changes how aggressively AI can iterate. Small, deterministic domain slices can be corrected in the same conversation instead of accumulating speculative code between manual test sessions.

---

## 6. First real integration seam — normal attack animation hit frame

### Objective

Stop testing only an isolated combat core and connect it to actual PAL3.Unity combat code.

### Source seam discovered

`CombatActorController.AnimationEventTriggered()` already handled `work*` animation events and contained a TODO for normal-attack behavior.

The existing attack coroutine already knew the target.

That made the minimal integration seam:

```text
StartNormalAttackAsync(attacker, target)
→ open one-shot hit gate
→ existing attack animation
→ work* animation event
→ emit NormalAttackHit(attacker, target)
→ close hit gate
```

### Attempt 1 — FAILED before semantic compilation

The first hand-written unified patch had incorrect new-file hunk lengths.

The fast pipeline rejected it at `git apply --check`.

### Fix

Only the two hunk headers were corrected. The semantic code was not changed.

### Attempt 2 — PASS, then warning cleanup

The patch replay succeeded and the new single-hit tests passed. A subsequent run exposed nullable-analysis warnings in the fast .NET harness.

Those warnings were removed before merge.

Final result:

```text
15 passed
0 failed
0 skipped
0 compiler warnings
```

### What this proved

The existing PAL3 attack animation path could now emit one deterministic domain-facing hit event without embedding the damage formula inside the animation controller.

### Reusable lesson

Animation should announce a hit; it should not own combat mechanics.

---

## 7. Runtime combat state — normal attacks now mutate encounter HP

### Objective

Make the animation hit seam change real encounter-local combat state.

### Important design decision

The rich GDB `CombatActorInfo.AttributeValues` structure was not assumed to be mutable runtime HP. No evidence showed that it should be directly mutated during combat.

Instead:

```text
GDB actor data
→ initialize CombatantState
→ CombatRuntimeRegistry owns encounter-local mutable state
```

### Additional hardening

The combat namespace was changed from `Combat.Core` to `Combat.Domain` to reduce the risk of shadowing upstream `Core.*` namespace usage during a future full Unity compile.

### Runtime path

```text
work* hit frame
→ NormalAttackHit
→ CombatManager
→ CombatRuntimeRegistry
→ NormalAttackResolver
→ defender CurrentHp decreases
```

### Machine proof

A representative registry test verified that a defender could move from 80 HP to 60 HP while the attacker remained unchanged.

Initial result:

```text
20 passed
0 failed
0 skipped
```

### Minor issue

One nullable warning in registry lookup remained.

### Fix

The lookup was adjusted and the current head returned:

```text
20 passed
0 failed
0 skipped
0 compiler warnings
```

### Reusable lesson

Static game definitions and mutable encounter state must be separated early. Otherwise later persistence, reset and replay logic becomes extremely difficult to reason about.

---

## 8. Combat + magic roadmap — mechanics separated from presentation

### Problem

Complex magic is not difficult only because of formulas. Bespoke spell animation can dominate development cost.

A system with 100 skills cannot reasonably require 100 unrelated handcrafted presentation pipelines if AI is expected to scale development.

### Architecture chosen

Mechanics and presentation were split:

```text
SkillDefinition
├── mechanics
│   ├── resource cost
│   ├── target range
│   ├── attribute effects
│   └── combat-state effects
└── presentation reference
    ├── visual archetype
    └── visual profile key
```

A small visual vocabulary was defined:

- `MeleeImpact`;
- `Projectile`;
- `DescendStrike`;
- `AreaBurst`;
- `GroundField`;
- `SupportPulse`;
- `SelfAura`;
- `BossSpecial`.

### Why this matters

Two skills can have identical mechanics but different visuals, or different mechanics but reuse the same visual skeleton.

The system therefore supports the long-term goal:

> complex RPG rules + templated presentation + bespoke treatment only for high-value signature skills.

### Machine proof

The Step 1 skill-domain contract extended the fast tests to:

```text
30 passed
0 failed
0 skipped
0 warnings
```

Tests explicitly checked that:

- one skill can contain multiple independent effects;
- changing the visual archetype/profile does not silently change the underlying mechanics.

### Reusable lesson

Do not let VFX architecture dictate combat rules. Treat visual playback as a consumer of resolved combat events.

---

## 9. Step 2 — first executable single-target damage spell

### Objective

Prove the first real spell-mechanics path before mapping actual PAL3 GDB skills or building VFX.

### Scope

The slice deliberately supports only a narrow, explicit subset:

- a live caster;
- one enemy target;
- enough encounter-local MP;
- one supported damage-magic definition;
- one negative absolute HP effect;
- deterministic HP mutation;
- defeated-target result.

Unsupported mechanics are rejected before mutation rather than guessed.

### Shared encounter state

`CombatantState` was extended with MP so normal attacks and spell casts operate on the same encounter model instead of maintaining separate fake state systems.

The path became:

```text
caster CombatantState
→ validate alive / target / semantics / MP
→ spend MP
→ resolve supported skill effect
→ mutate target CurrentHp
→ return skill resolution / defeated state
```

`CombatRuntimeRegistry` exposes the same encounter-state objects to the spell resolver.

### Attempt 1 — PASS

Unlike the normal-attack seam experiment, the first Step 2 patch replay succeeded immediately.

The fast lane also passed on the first semantic attempt.

There was no observed implementation failure to invent or hide.

Final NUnit result from the evidence artifact:

```text
39 total
39 executed
39 passed
0 failed
0 skipped
```

The new tests covered, among other things:

- MP spending;
- target HP mutation;
- lethal damage;
- insufficient MP;
- dead caster rejection;
- dead target rejection;
- unsupported target-range rejection;
- unsupported effect rejection;
- zero-cost skill behavior;
- registry integration.

### What is **not** proven

This step does not prove:

- mapping from real PAL3 `SkillInfo`;
- original PAL3 magic formula fidelity;
- original MP/SP consumption semantics;
- Unity cast input/events;
- VFX playback;
- full Unity compilation;
- runtime playability.

### Reusable lesson

A feature can succeed on the first attempt and still deserve a detailed log. The point of the log is reproducibility, not drama.

---

## 10. Experiment-log protocol — turning failures into reusable worker memory

### Motivation

As the number of parallel AI workers grows, repeated rediscovery becomes expensive.

The project now maintains dedicated machine-readable experiment logs.

Each material experiment records:

- objective;
- hypothesis;
- changed surfaces;
- attempts;
- failures;
- fixes;
- evidence;
- claim boundary;
- reusable lessons;
- next experiment.

Terminal logs are append-only in the historical sense: a later success cannot erase an earlier failed attempt.

### Worker bootstrap order

Before acting, a worker is required to read:

1. the combat/magic roadmap;
2. experiment-log rules;
3. experiment index;
4. latest relevant experiment logs;
5. current normalized command.

This human devlog adds a sixth perspective: the chronological engineering narrative.

### Why both machine logs and a human blog exist

Machine logs answer:

> What exactly happened, in structured fields?

The human devlog answers:

> Why did we take this path, what did the failures mean, and what should another engineer learn from it?

Both are necessary if dozens of workers are eventually running against isolated steps.

---

## 11. Current project truth

### Verified

- ChatGPT can read the relevant PAL3 source surface through the control workflow.
- Ordered patches can be replayed against the pinned upstream.
- New files and modified files are represented in diff evidence correctly.
- Pure-C# combat code authored through this workflow can compile and execute tests on GitHub runners.
- Normal-attack animation hit events can be bridged into a one-shot domain seam.
- Encounter-local HP state can be mutated by normal attacks.
- Skill definitions can represent multiple mechanics independently of presentation archetypes.
- A single-target damage spell can spend encounter-local MP and mutate the same encounter-local HP model.
- The current fast-domain suite has reached 39 passing tests.

### Blocked / unverified

- Full Unity compilation remains unverified because usable Unity activation material is not configured in the control repo CI.
- Unity EditMode execution of the full project is unverified.
- Runtime combat smoke tests are unverified.
- iOS build/signing is unverified.
- Real PAL3 skill-data mapping is not implemented.
- Original PAL3 combat/magic formula fidelity is not established.
- Actual magic VFX and cast animations are not implemented.

---

## 12. Next high-information experiment: GDB SkillInfo adapter

The next step is **not** “make a pretty fireball.”

The next step is to consume real PAL3 skill data without silent semantic loss.

A schema mismatch is already visible.

For example, the original data model can expose richer structures such as collections of elemental attributes, while the current domain contract contains a simpler single `Element` field. Similarly, original MP consumption includes an impact type plus a value, while the feasibility domain currently exposes a simple integer MP cost.

A bad mapper would do something like:

```text
pick the first element
cast the MP value to an integer cost
ignore the rest
```

That would create silent data loss and false confidence.

The proposed adapter should instead return something like:

```text
SkillInfoMapper
→ MappingResult
   ├── SkillDefinition / partial definition
   ├── mapped fields
   ├── warnings
   ├── unsupported semantics
   ├── unmapped fields
   └── provenance
```

The rule for Step 3 should be:

> report a semantic gap before inventing a conversion.

That is the next place where the project can either become a robust AI-scalable RPG rewrite system or quietly accumulate incorrect assumptions.

---

## Publication note

This file is intentionally formatted as a single continuous Markdown article so it can become the canonical source for a GitHub Gist or a Medium series later.

The current connected GitHub write surface does not expose create/update Gist operations. Until that changes, this repository file is the writable canonical mirror.

Future publication should preserve failed attempts. A cleaned-up Medium article may improve prose, but it must not rewrite engineering history into a fictional straight line.
