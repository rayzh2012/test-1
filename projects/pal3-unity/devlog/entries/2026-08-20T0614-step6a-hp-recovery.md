# Step 6A — Deterministic HP recovery

## Objective

Begin Roadmap Step 6 with the smallest source-grounded healing/support mechanic: `RecoverMagic` that restores HP for `FirstPartySingle` or `FirstPartyAll` targets.

Pinned upstream already exposes the exact enum vocabulary used here:

- `SkillType.RecoverMagic`;
- `TargetRangeType.FirstPartySingle` / `FirstPartyAll`;
- `AttributeImpactType.Absolute` / `RecoverToMax`.

No new target or skill-type semantics were invented.

## Domain behavior

`CombatantState` now has clamped `RestoreHp` while existing `ApplyDamage` behavior is unchanged.

A recovery cast follows:

```text
validate RecoverMagic semantics
→ resolve living first-party targets
→ validate target-state identity
→ validate MP
→ spend MP once
→ restore HP per selected target
→ one SkillCast fact
→ one target-addressed Healing fact per target
```

`Healing=0` is allowed for a legal cast on an already-full target. Defeated targets are not revived in this slice. Self-heal is represented naturally by a `FirstPartySingle` anchor whose target state is the caster.

## Supported effects

- positive absolute HP recovery;
- `RecoverToMax` using the target's current missing HP.

The source `Value` is deliberately ignored for `RecoverToMax` because the impact type itself defines the current slice's operation. Percentage recovery is explicitly rejected until separate semantics are locked.

## Attempt 1 — FAIL_COMPILE

Patch replay and Source Audit passed, but the first fast lane failed before any test executed.

- Source Audit: `32358054897` — PASS
- Fast Lane: `32358054901` — FAIL_COMPILE
- Error: `RecoverySkillResolver.cs(276,24): CS1513 } expected`
- Failed artifact: `9402425957`
- SHA256: `e48a02524e11b980d0bf38252e84174af8956ca836c85e12d57d9899ee8259f4`

Root cause was evidence/control generation, not recovery semantics: the new-file patch contained a 286-line source but declared `+1,276`. The replayed workspace therefore contained only the first 276 lines.

The fix changed only the unified-diff hunk length from `276` to `286`.

## Attempt 2 — PASS

- Source Audit: `32358257767` — PASS
- Fast Lane: `32358257771` — PASS
- Artifact: `9402507538`
- SHA256: `dcdf7f5fddea6c4ff8c60698956604b76695e7bd339507f0cce1e63dc38b1e5f`

Machine result:

```text
113 passed
0 failed
0 skipped
144 ms
```

## Verified behavior

The new tests cover:

- single-target absolute healing;
- overheal clamping;
- recover-to-max;
- zero effective healing on a full-HP target;
- self-heal;
- party-all healing in deterministic formation order;
- dead-target filtering / no revival;
- insufficient MP with no HP mutation;
- Percentage rejection;
- non-positive Absolute rejection;
- wrong skill type / enemy target-range rejection;
- aliased target-state rejection before MP/HP mutation;
- read-only result/event collections.

## Transaction boundary

Every expected semantic/resource/identity rejection occurs before the first MP/HP mutation. After MP is spent, normal execution contains only validated non-negative `RestoreHp` calls and immutable result/event construction.

## Claim boundary

This does not establish Percentage healing, revival behavior, SP-consuming recovery, attack/defense/speed/luck modifiers, combat-state effects, Unity support VFX, Unity compile/runtime, iOS build or playtest.

## Next

Continue Step 6B with attack/defense/speed/luck support modifiers while keeping lifecycle-heavy status mechanics in Step 7.
