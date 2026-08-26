# Module C — Combat Reward Truth × Money/Loot Settlement

## 1. Source facts

Pinned upstream `CombatActorInfo` already carries battle-reward data read directly from GDB:

- `Experience`
- `NormalLoot`
- `NormalLootCount`
- `MoneyWhenKilled`
- plus corpse/steal fields for later slices

Search of pinned upstream found no runtime consumer for `MoneyWhenKilled` or `NormalLootCount`; they existed only in the GDB model/reader. Battle rewards therefore had data but no settlement path.

`InventoryManager` already owns persistent money/item state and supports the command bus mutations:

- `InventoryAddMoneyCommand`
- `InventoryAddItemCommand`

By contrast, the current `PlayerActorManager` owns only control/position state and the save pipeline has no proven persistent player EXP owner. EXP must therefore not be silently invented as a new persistence model in this slice.

## 2. Architecture decision

Reward truth consumes the completed battle outcome established in Module B. It does **not** independently decide whether the player won.

Truth path:

`enemy CombatActorInfo reward fields`
→ `CombatRewardSource`
→ `CombatRewardResolver`
→ `CombatRewardSummary`
→ real `CombatResult.Rewards`
→ `CombatCoordinator.ApplyCombatRewards`
→ inventory command bus
→ persistent money/items

EXP is aggregated into `CombatRewardSummary.Experience` but deliberately remains pending until a persistent actor-stat model exists.

## 3. Patch 0103 — pure reward domain

`0103-combat-reward-domain.patch` adds:

- `CombatRewardSource`
- `CombatRewardSummary`
- `CombatRewardResolver`
- `CombatRewardResolverTests`

Rules:

- experience and money must be non-negative;
- loot id/count must both be zero or both be non-zero;
- duplicate loot IDs are aggregated;
- totals use checked arithmetic;
- result item dictionaries are defensively copied.

An initial packaging defect accidentally embedded the second test-file diff as text in the resolver file. Source replay could still succeed, but Fast Lane correctly reported the expected test file as missing. The patch was rebuilt cleanly as two real new files before proceeding.

## 4. Patch 0104 — runtime settlement

`0104-combat-reward-runtime-settlement.patch` wires the domain into the runtime:

- `CombatResult` now carries `CombatRewardSummary Rewards`.
- `CombatManager` captures GDB reward sources only for enemy slots.
- a real domain `PlayerWin` resolves the enemy reward sources.
- a real `PlayerLose` produces `CombatRewardSummary.Empty`.
- Escape forced-win remains a debug path and explicitly carries `CombatRewardSummary.Empty`, so debugging cannot mint money/items.
- `CombatCoordinator` settles rewards only when `combatResult.IsPlayerWin`.
- money goes through `InventoryAddMoneyCommand`.
- normal loot goes through `InventoryAddItemCommand`.
- positive EXP is explicitly logged as pending persistent actor-stat support instead of pretending it has been applied.

Reward application occurs after leaving the combat scene but before a paused story script waiter is resumed, so story continuation observes the settled inventory state.

## 5. Verification

Verified head: `25cf4bb9709d5be2085b5c064d0f6367c51205b1` on PR #108.

### Ordered source replay

- Source Control Audit: **PASS** through `0104`.

### Fast Lane

- `combat_core`: **128 / 128 PASS**.
- This is 119 previously verified tests plus 9 new reward-domain NUnit test cases.

### State Truth Gate v0.3

- **28 / 28 PASS**.
- New reward contracts prove source wiring for:
  - checked reward aggregation;
  - GDB experience/money/normal-loot input;
  - real-win reward resolution;
  - debug Escape empty rewards;
  - win-only settlement;
  - money command-bus settlement;
  - item command-bus settlement;
  - EXP explicitly pending rather than silently applied.

### Unity boundary

`PAL3 Unity Compile Gate` workflow is green, but its actual Unity steps are still:

- `Cache Unity Library`: **skipped**
- `Build patched PAL3 with Unity`: **skipped**
- `Mark Unity compile verified`: **skipped**

Therefore this module is `PATCH_REPLAY_VERIFIED + DOMAIN_VERIFIED + SOURCE_CONTRACT_VERIFIED`, **not** `UNITY_EDITOR_COMPILE_VERIFIED` and not a runtime playthrough.

## 6. Open work exposed by this module

The highest-value next dependency is now explicit: build a persistent player actor-stat model so accumulated battle EXP can be applied, saved, loaded, and eventually drive level progression. That requires evidence for the original save/state representation before inventing a schema.

Dealer/hotel work remains separately blocked by the currently undocumented `DealScript` commercial-data format; upstream current `main` still contains the same stubs, so this is a real upstream gap rather than pin drift.
