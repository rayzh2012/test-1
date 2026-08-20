# Step 4B — Combat facts cross the presentation boundary

## Objective

The roadmap said that spell mechanics should resolve independently and presentation should consume combat events. Step 2 had a working damage spell, but its result exposed only scalar fields. This experiment closed that missing event seam and built the first generic `Projectile` presentation contract without introducing Unity dependencies.

## Domain events

`SkillCastResolution` now exposes ordered resolved facts:

```text
SkillCast
→ Damage
→ TargetDefeated (only when lethal)
```

These facts are emitted after MP spending and HP mutation. They carry resolved truth; they do not ask presentation code to calculate damage again.

## First generic Projectile plan

`GenericSkillPresentationPlanner` consumes `SkillDefinition` plus the already-resolved `SkillCastResolution` and produces:

```text
Cast
→ Travel
→ Impact
→ TargetDefeated (optional)
```

The plan preserves the skill's `VisualArchetype` and `VisualProfileKey`. The Impact cue carries the already-resolved damage amount.

No millisecond durations, prefab IDs, sounds, camera profiles, or Unity objects were invented in this slice. Those belong to a later Unity-facing adapter.

## Attempt 1 — PASS

The first code-bearing version replayed successfully and passed the fast domain lane.

- Source Audit run: `32341131104`
- Fast Lane run: `32341131050`
- Artifact: `9396383495`
- SHA256: `e850a394653783cbe20d53d90132af2f42d15fcaad34fc7b3d7db406e890f531`

Machine result:

```text
59 passed
0 failed
0 skipped
234 ms
```

There was no CI failure to invent.

## Pre-merge review finding — not a CI failure

A manual contract review found a subtle issue: the public properties were typed as `IReadOnlyList`, but their backing objects were raw arrays. A sufficiently determined caller could cast the returned object back to an array and mutate it.

That contradicted the intended immutable boundary even though all tests were green.

The fix replaced the exposed array aliases with `Array.AsReadOnly` wrappers and added a regression test proving neither public collection is a mutable array alias.

Hardened verification:

- Source Audit run: `32341367212`
- Fast Lane run: `32341367176`
- Artifact: `9396458443`
- SHA256: `2615061d951efb1cd1ffc26f7bb94e22876e2b8c711f5a3e1adaff0cdade6994`

```text
60 passed
0 failed
0 skipped
149 ms
```

## What this proves

- the first spell resolver now emits explicit immutable domain facts;
- presentation planning happens after combat mutation;
- presentation mirrors resolved damage rather than recalculating it;
- building a presentation plan cannot mutate encounter HP or MP;
- the first reusable archetype contract works without `UnityEngine`;
- no visual timing constants were fabricated.

## What this does not prove

This is not actual Unity VFX playback. Prefabs, casting animation, travel timing, camera, sound, hit reactions, damage-number rendering and real runtime playability remain unverified. Full Unity compilation is still a separate activation-blocked gate.

## Reusable lesson

The safest boundary is:

```text
combat mutation
→ immutable resolved facts
→ presentation plan
→ engine adapter later
```

A green test suite does not remove the need for contract review. In particular, `IReadOnlyList` is not enough if the returned backing object is still a mutable array.

## Next

The pure-domain roadmap can now proceed to multi-target resolution while reusing the same event/presentation boundary. A real Unity `Projectile` adapter can be attached later without granting the engine layer authority over combat truth.
