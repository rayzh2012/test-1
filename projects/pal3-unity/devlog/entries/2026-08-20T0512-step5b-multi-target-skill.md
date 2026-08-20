# Step 5B — One cast, many targets, one combat truth

## Objective

Step 5A proved deterministic target selection without inventing a PAL3 `ElementPosition` row/column geometry. Step 5B turns those selected target keys into actual combat mutation for the narrow damage mechanic that is already verified elsewhere: one negative absolute HP `DamageMagic` effect.

The key constraint is transaction shape:

```text
validate skill
→ select targets
→ validate non-empty target set
→ calculate requested damage safely
→ validate MP
→ validate distinct mutable state identities
→ spend MP once
→ mutate each selected target
→ emit resolved facts
```

No normal business-rule rejection is allowed after the first mutation.

## Additive result model

The existing single-target ABI remains intact. This experiment does not change `CombatEvent`, `SkillCastResolution`, `SingleTargetSkillResolver`, or the Step 4B Projectile presentation planner.

Instead it adds:

- `MultiTargetSkillCastResolution<TKey>` — one cast identity, `MpSpent`, one overall `SkillCast` fact, and ordered target results;
- `TargetSkillResolution<TKey>` — target key, applied damage, defeat flag, and target-associated `Damage` plus optional `TargetDefeated` facts;
- `MultiTargetSkillResolver<TKey>` — enemy-all / enemy-row / enemy-column mutation policy.

This keeps target identity outside the generic `CombatEvent` ABI and avoids destabilizing an already-verified single-target presentation contract.

## Pre-CI hardening

Before machine execution, contract review identified a mutable-state alias problem not covered by key uniqueness alone.

Two distinct target keys could theoretically reference the same `CombatantState` instance. If allowed, one area spell would damage the same mutable actor twice. A malformed enemy slot could also reference the caster's own state, causing the cast to spend MP and then damage the caster through an alias.

The resolver now rejects both situations before MP/HP mutation. Two regression tests were added, raising the expected suite from 88 to 90 tests.

## Attempt 1 — patch replay failure

- Source Audit run: `32354067564`
- Result: `FAIL_PATCH_REPLAY`
- Evidence artifact: `9400943227`
- SHA256: `78e18e221c62a61dee7581ff4901b4111d0bbc2bbd916e76fa7e9c1f408bd0df`

The failure occurred before C# compilation/tests. `0016` and `0017` applied, while `0018-multi-target-state-alias-guard.patch` was reported corrupt at line 29.

Cause: the unified-diff hunk header declared `+164,23`, but the hunk actually contained 24 new-side lines. The only fix was changing the header to `+164,24`; resolver semantics did not change.

This is recorded as a patch-format failure, not a code-semantic failure.

## Attempt 2 — PASS

- Source Audit run: `32354285396` — PASS
- Fast Lane run: `32354285337` — PASS
- Artifact: `9401035886`
- SHA256: `5536b9aed90d18a77df36e9f0239ffb3af6d57b9990f4c8dd888fdcf8cb88094`

Machine result:

```text
90 passed
0 failed
0 skipped
141 ms
```

## Verified behavior

The suite now locks these properties:

- `EnemyPartyAll` damages every living enemy selected by Step 5A and does not mutate allies or defeated targets;
- enemy row and column damage follow explicit adapter coordinates and preserve deterministic selection order;
- MP is spent once per cast, regardless of target count;
- each target clamps damage independently to remaining HP;
- each target independently emits `Damage` and optional `TargetDefeated` facts;
- the cast emits exactly one overall `SkillCast` fact;
- insufficient MP rejects without changing any target;
- an all-target cast with no living enemies rejects without spending MP;
- unsupported single-target semantics and extra effects reject without mutation;
- `int.MinValue` damage magnitude overflow is detected before MP/HP mutation;
- a defeated caster cannot start the cast;
- row/column ranges require the anchor overload, while the anchor overload rejects enemy-all misuse;
- distinct target keys cannot alias one mutable `CombatantState`;
- caster state cannot also be a selected enemy state;
- result/event collections expose read-only wrappers, not raw mutable arrays.

## Transaction review

After target discovery and all semantic/resource/identity checks pass, the resolver performs one `TrySpendMp` and then only positive `ApplyDamage` operations followed by result construction from already-valid skill IDs and positive applied damage.

Under expected domain conditions, there is no remaining business-rule branch that can reject halfway through the target loop. This prevents a normal partial-cast state such as "MP spent, first enemy damaged, second enemy rejected".

## Claim boundary

This step does **not** claim:

- the original PAL3 damage formula;
- elemental damage modifiers;
- healing/support semantics;
- status effects;
- ally-target damage;
- a proven `ElementPosition → row/column` mapping;
- Unity multi-target VFX or targeting UI;
- Unity compile/runtime verification.

It reuses only the already-explicit negative absolute HP effect and the verified Step 5A target-selection contract.

## Next

The clean next closure is Step 5C: a pure multi-target presentation planner consuming `MultiTargetSkillCastResolution<TKey>` after mutation. It should create target-addressed presentation cues without selecting targets, recalculating damage, or mutating combat state. Once that boundary is proven, Step 6 can add healing/support mechanics without carrying a presentation debt forward.
