# Step 5C — Multi-target combat facts cross the presentation boundary

## Objective

Step 5B had already verified atomic multi-target combat mutation with target-associated resolved facts. This experiment carried those facts into a reusable presentation contract without giving presentation authority over targeting, MP, HP, damage math, or combat state.

## Presentation contract

One resolved cast now maps to:

```text
one global SkillCast
→ one global Cast cue
→ target A: Impact [+ optional TargetDefeated]
→ target B: Impact [+ optional TargetDefeated]
→ target C: Impact [+ optional TargetDefeated]
```

The plan preserves target identity and target order from `MultiTargetSkillCastResolution<TKey>`. Each Impact cue carries the already-resolved damage amount. Defeat cues appear only when the corresponding resolved target is terminally defeated.

## Deliberate non-invention boundary

The generic multi-target planner does **not** emit `Travel` cues and does not infer trajectory, timing, prefab, sound, camera behavior, spatial sequencing, Unity objects, or `ElementPosition` geometry.

`VisualArchetype` and `VisualProfileKey` are preserved as metadata for a later engine adapter. A `GroundField` test specifically verifies that merely carrying an archetype does not cause the planner to invent a Travel phase.

## Machine verification — PASS

- Source Audit run: `32357032521`
- Fast Lane run: `32357032514`
- Artifact: `9402045720`
- SHA256: `c3f8eebc58a5f7ab8905ecc9e8da1c9db970dfc3ac99c8b748095403721e1a97`

Machine result:

```text
98 passed
0 failed
0 skipped
```

There was no CI failure in the first code-bearing attempt.

## What this proves

- multi-target presentation can remain downstream from already-resolved combat truth;
- one cast-level presentation fact can coexist cleanly with multiple target-level presentation facts;
- target identity survives the domain → presentation boundary;
- presentation mirrors resolved damage and defeat state rather than recalculating either;
- building a plan does not mutate caster MP or target HP;
- plan collections are exposed through read-only wrappers;
- duplicate target keys and mismatched skill IDs are rejected;
- generic visual metadata can be preserved without inventing playback semantics.

## What this does not prove

This is not actual Unity multi-target playback. VFX, prefab selection, animation timing, spatial sequencing, sound, camera, damage-number rendering, Unity compile/runtime, iOS build and playtest remain separate heavy-lane work.

## Reusable lesson

The stable boundary is now:

```text
combat mutation
→ immutable target-addressed resolved facts
→ immutable target-addressed presentation plan
→ engine adapter later
```

This closes Roadmap Step 5 at the pure-domain/presentation-contract level. The next mechanics slice is Step 6 healing/support.
