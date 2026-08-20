# Step 5A — Target selection without inventing PAL3 formation geometry

## Objective

The roadmap reached multi-target combat after the domain-to-presentation boundary was verified. Before one skill can mutate several actors, the combat domain needs a deterministic answer to a simpler question: **which actors are targeted?**

Pinned upstream already exposes these target-range semantics:

```text
FirstPartySingle
FirstPartyAll
EnemyPartySingle
EnemyPartyAll
EnemyPartyOneRow
EnemyPartyOneColumn
```

Pinned upstream also exposes six ally and six enemy `ElementPosition` values, but no verified row/column mapping was found. Therefore this experiment deliberately does **not** reinterpret elemental positions as a guessed 2-D grid.

## Contract

`CombatTargetSlot<TKey>` carries:

```text
Key
CombatantState
Party
Row
Column
```

`Row` and `Column` are explicit adapter input. The target resolver treats them as already-resolved formation coordinates; the PAL3 runtime adapter must eventually supply them from evidence-backed scene/config semantics.

`CombatTargetResolver<TKey>` now provides pure target selection for:

- first-party single;
- first-party all;
- enemy single;
- enemy all;
- enemy one row;
- enemy one column.

It filters defeated actors and sorts selected groups deterministically by `(row,column)`.

## Pre-CI contract review finding

Before the first machine run, review found an identity invariant missing from the initial implementation.

The resolver already rejected two actors occupying the same `(party,row,column)`, but it did not globally reject the **same target key** appearing at two different coordinates. On an all-target path that malformed input could have returned the same actor identity twice.

This was fixed before CI by adding a separate target-key uniqueness check. A regression test covers it. This was not a CI failure and is recorded as pre-CI hardening.

## Attempt 1 — PASS

- PR: `#90`
- Source Audit run: `32352972672` — PASS
- Fast Lane run: `32352972869` — PASS
- Artifact: `9400548210`
- SHA256: `ce590e3c7ea8c1e9e6b9ec289a2745ed0132f51cf51ac1be2d1136f9d439f6ce`

Machine result:

```text
74 passed
0 failed
0 skipped
117 ms
```

There was no machine failure in the code-bearing attempt.

## Verified behavior

The test suite locks the following rules:

- party-all targeting includes only living actors from the requested party;
- single targeting requires exactly one living anchor from the required party;
- enemy-row targeting uses the anchor's explicit row;
- enemy-column targeting uses the anchor's explicit column;
- row/column group selection excludes defeated actors;
- selected group order is deterministic;
- wrong-party, missing, or defeated anchors are rejected;
- duplicate formation coordinates within one party are rejected;
- duplicate target keys are rejected even when coordinates differ;
- returned target collections are read-only wrappers rather than mutable array aliases;
- negative row/column coordinates are rejected.

## What this proves

The combat domain can now represent and select single/all/row/column targets without giving damage resolution or Unity presentation responsibility for target discovery.

More importantly, it does this without silently asserting that PAL3's `Water / Fire / Wind / Thunder / Earth / Center` element positions correspond to any particular row/column geometry.

## What this does not prove

This step does not:

- apply one spell to several actors;
- define multi-target MP semantics beyond future design;
- prove the original PAL3 formation row/column layout;
- connect `ElementPosition` to explicit coordinates;
- add Unity targeting UI or VFX;
- prove Unity compile/runtime.

## Reusable lesson

Target identity and target geometry are separate invariants. A target-selection layer should be pure and deterministic before state mutation is generalized.

When upstream exposes semantic enums but omits the mapping that gives them physical meaning, preserve the missing mapping as explicit adapter input rather than turn a plausible guess into domain truth.

## Next

Step 5B can now consume `CombatTargetResolver` output and generalize the already-supported negative absolute HP skill effect across the selected target set. MP should be spent once per cast, each affected actor should receive its own resolved damage fact, and presentation should continue consuming those facts after mutation rather than recalculating combat truth.
