# Module B — Combat Result Truth × 剧情战败分支

## 1. 原版语义

SCE Command 132 `ScriptVarSetCombatResultCommand` 的声明语义是：**取得战斗结果（0输1赢）并赋值给变量**。

这意味着脚本需要查询已经发生的战斗结果，而不是在战后再次随机决定胜负。

## 2. Upstream observed defects

Pinned upstream: `0x7c13/Pal3.Unity@cfed96a21fde248e93e64a47d465b2a9f839ccf8`.

### 2.1 Command 132 fabricated combat outcome

`UserVariableManager.Execute(ScriptVarSetCombatResultCommand)` used `RandomGenerator.Range(...)` to create `won`, then wrote 0/1 into the requested script variable. PAL3/PAL3A debug notes even fabricated named victory/defeat messages.

This contradicted the command contract because the query did not read any completed combat state.

### 2.2 `IsNoGameOverWhenLose` existed but was ignored

`CombatContext` already contained `IsNoGameOverWhenLose`, and `CombatSetNoGameOverWhenLoseCommand` populated it. However, upstream `CombatCoordinator.OnCombatFinished` always switched to the main menu after loss.

Together these two facts expose the intended missing chain: some scripted battles may lose without Game Over, resume the paused script, then use Command 132 to branch on 0/1.

## 3. State ownership and data flow

The repaired truth chain is:

`CombatantState.CurrentHp / IsAlive`
→ `CombatOutcomeResolver`
→ `CombatManager.SignalCombatFinished`
→ `CombatResult.IsPlayerWin`
→ `CombatCoordinator._lastCombatPlayerWin`
→ `ScriptVarSetCombatResultCommand`
→ script variable `0/1`

Presentation is explicitly excluded from outcome selection.

## 4. Implementation

### Patch 0101 — pure domain outcome resolver

`0101-combat-outcome-domain.patch` adds:

- `CombatOutcomeStatus.InProgress`
- `CombatOutcomeStatus.PlayerWin`
- `CombatOutcomeStatus.PlayerLose`
- `CombatOutcomeStatus.MutualDefeat`
- `CombatOutcomeResolver.Resolve(...)`
- six NUnit tests

The resolver only inspects party membership and `CombatantState.IsAlive`.

### Patch 0102 — runtime result propagation

`0102-combat-result-state-truth.patch`:

1. maps encounter controllers to `CombatParty`;
2. evaluates terminal outcome after a defeated target is observed in encounter-local HP state;
3. routes terminal state through one guarded `SignalCombatFinished` path;
4. stores the last completed result in `CombatCoordinator` before script waiter resume;
5. makes `IsNoGameOverWhenLose` actually resume the previous state on scripted loss;
6. makes Command 132 read the stored completed result;
7. removes random win/loss generation;
8. retains Escape forced-win only as an explicitly labelled debug path.

## 5. Verification evidence

Head verified: `84f2b535b1d3136b462603a3afa6a0ae2c9b0f20` on PR #108.

### Source Control Audit

- ordered patch replay through `0102`: **PASS**

### PAL3 Chat Fast Lane

- `combat_core`: **119 / 119 PASS**
- includes 6 new `CombatOutcomeResolverTests`

### PAL3 State Truth Gate

- **18 / 18 PASS**
- checks include:
  - Command 132 still declares 0 lose / 1 win semantics;
  - outcome derives from domain alive state;
  - CombatManager emits real player loss as well as win;
  - coordinator persists last result before script resume;
  - `IsNoGameOverWhenLose` affects post-combat control flow;
  - Command 132 reads coordinator state;
  - random PAL3/PAL3A win/loss stubs are absent;
  - Escape forced finish is explicitly marked debug-only.

## 6. Verification boundary

This module is **DOMAIN VERIFIED + SOURCE CONTRACT VERIFIED + PATCH REPLAY VERIFIED**.

It is not a claim of a real PAL3 runtime playthrough. The Unity compile workflow may succeed while the actual Unity Editor build step remains activation-gated; runtime/visual verification remains a separate evidence level.

## 7. Open semantics

- `MutualDefeat` is intentionally explicit and unresolved; no arbitrary win/loss policy was invented.
- Future poison, self-damage, status ticks, reflection, or simultaneous effects must converge on the same combat-outcome truth path.
- Future reward/EXP/drop settlement must consume the completed `CombatResult`, not independently infer victory.
