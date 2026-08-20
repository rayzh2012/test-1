# Step 3 — Real GDB `SkillInfo` without silent semantic loss

**Time:** 2026-08-20 02:08 America/Toronto  
**Experiment:** `pal3-exp-20260820-0208-step3-gdb-skill-mapping-0007`  
**PR:** #86  
**Pinned upstream:** `0x7c13/Pal3.Unity@cfed96a21fde248e93e64a47d465b2a9f839ccf8`

## Objective

Stop testing skill mechanics only against synthetic domain objects and compile the real upstream `Pal3.Core.DataReader.Gdb.SkillInfo` schema inside the ChatGPT fast lane.

The critical requirement was **no silent semantic loss**. The mapper must not turn a richer source field into a simpler runtime field by guessing.

## Source mismatch observed

The real upstream schema contains semantics that the current feasibility `SkillDefinition` does not yet fully represent:

- elemental attributes are `HashSet<ObjectElementType>`, not a single element;
- MP and SP consumption each have an `AttributeImpactType` plus a value;
- special resource consumption has its own type / impact type / value;
- special-skill behavior and success-rate level exist independently;
- applicable actors, progression, outside-combat use, composite-skill requirements and combo triggers are retained in GDB;
- attribute and combat-state effects can contain multiple entries.

A mapper such as `Element = source.ElementAttributes.First()` would therefore be unacceptable.

## What changed

### `GdbSkillInfoMapper`

A loss-aware projection layer was added. Every result retains the original `SkillInfo` struct and exposes structured mapping issues.

Simple source skills can project into the current `SkillDefinition` only when the currently required execution semantics are representable.

Blocking examples include:

- `MULTI_ELEMENT_NOT_REPRESENTABLE`;
- `MP_CONSUMPTION_TYPE_NOT_REPRESENTABLE`;
- `SP_CONSUMPTION_TYPE_NOT_REPRESENTABLE`;
- `SPECIAL_CONSUMPTION_NOT_REPRESENTABLE`;
- `SPECIAL_SKILL_BEHAVIOR_NOT_REPRESENTABLE`;
- `SUCCESS_RATE_NOT_REPRESENTABLE`.

Progression/composite/applicability metadata remains in the retained source and is reported rather than silently discarded.

### Presentation remains explicit

The mapper does **not** infer a VFX archetype from a GDB element or skill name. `SkillVisualArchetype` and `VisualProfileKey` are supplied explicitly by the caller.

### Fast lane now compiles the real PAL3 conditional schema

`pal3_fastlane.py` gained per-slice `define_constants` support. The combat slice now compiles with `PAL3` defined and directly includes:

- `ActorEnums.cs`;
- `CombatEnums.cs`;
- `ItemEnums.cs`;
- `SceneEnums.cs`;
- upstream `GdbFile.cs`.

This is important: the tests are no longer validating a locally copied fake `SkillInfo` shape.

## Attempt 1

**Result: PASS on first attempt.**

There was no implementation failure to invent.

The ordered patch stack replayed cleanly on the pinned upstream, and the real GDB schema compiled inside the fast lane.

Machine result:

```text
45 total
45 executed
45 passed
0 failed
0 skipped
57 ms
```

Fast-lane workflow run: `32338925581`  
Evidence artifact: `9395634316`  
Artifact SHA256: `2d0981f15e85e34161c0c06c7821de0d9f79a161de4e369cc137a133280128f6`

The source audit also observed the new `GdbSkillInfoMapper.cs` and `GdbSkillInfoMapperTests.cs` in the replayed upstream tree.

## What this proves

- ChatGPT can compile tests against the **real upstream `SkillInfo` type** under the PAL3 conditional build path.
- A simple absolute-cost single-element source skill can be projected into the current combat domain.
- Multi-element and richer resource-consumption semantics can be detected and preserved without `.First()` / integer-coercion shortcuts.
- Source metadata can remain available for later workers even when it is not yet executable by the current runtime domain.

## What this does **not** prove

- We have not scanned the commercial PAL3 GDB dataset and measured how common each blocking semantic is.
- Multi-element runtime execution is not implemented.
- Percentage MP/SP consumption is not implemented.
- Special consumption, special-skill behavior and success-rate logic are not implemented.
- Full Unity compilation remains unverified because activation is still unavailable in CI.
- No spell VFX or cast-animation path was added here.
- No claim is made about original PAL3 damage-formula fidelity.

## Reusable lesson

**Schema gaps should become data, not guesses.**

A future worker can now inspect `MappingResult.Issues` and decide which missing semantic has the highest information gain. That is much safer than letting every worker invent its own conversion rules.

## Next experiment

The next high-information step is to determine which blocking semantics actually occur in real skill data, then promote the most common one into the runtime domain as a separate verified slice.
