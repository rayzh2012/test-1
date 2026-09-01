# PAL3.Unity 重构学习资料｜源码架构 × 修复逻辑 × 验证证据

> 目标：一边推进《仙剑奇侠传三》PAL3.Unity 程序重构，一边把每次源码研究、故障定位、修复选择和验证结果沉淀成可复用教材。这里记录的是程序工程，不是剧情人物设定研究。

## 0. 阅读规则：事实、推论、验证必须分层

- **SOURCE FACT**：直接来自当前 pinned upstream `0x7c13/Pal3.Unity@cfed96a21fde248e93e64a47d465b2a9f839ccf8` 的源码。
- **PATCHED FACT**：ordered patch stack 成功重放后，可以直接从 patched source 观察到。
- **DOMAIN VERIFIED**：Unity-independent C# / NUnit 测试通过。
- **SOURCE CONTRACT VERIFIED**：源码契约检查通过，只证明指定源码结构，没有冒充 Unity 编译。
- **UNITY COMPILE VERIFIED**：必须真的由 Unity Editor / GameCI 编译成功。
- **RUNTIME / VISUAL VERIFIED**：必须真实运行并观察到画面、行为、截图或视频。

任何“静态源码分析”都不能写成“游戏里已经跑通”。

---

## 1. 工程结构：为什么 control repo 不是完整 fork

### Upstream

- Repo: `0x7c13/Pal3.Unity`
- Pinned commit: `cfed96a21fde248e93e64a47d465b2a9f839ccf8`
- Engine: Unity `6000.5.0f1`

### Control plane

- Repo: `rayzh2012/test-1`
- Project path: `projects/pal3-unity`
- 工作方式：CI checkout pinned upstream → 按文件名顺序重放 patch stack → 跑审计 / 快速测试 / Unity gate。

这意味着：

1. `test-1` 保存的是**重构方法、patch、验证和证据**；
2. 修改后的完整 Unity tree 不直接提交进 control repo；
3. 每一个 patch 都应该可独立审计，并且能在 pinned upstream 上重放。

---

## 2. PAL3.Unity 的核心运行架构

### 2.1 `Pal3.cs` 是 composition root

`Pal3.OnEnable()` 负责创建并注册绝大多数运行系统到 `ServiceLocator`：

- `UserVariableManager`
- `ScriptManager`
- `SceneStateManager`
- `SceneManager`
- `InventoryManager`
- `TradingManager`
- `TeamManager`
- `HotelManager`
- `FavorManager`
- `CombatManager`
- `CombatCoordinator`
- `SaveManager`
- 以及 camera/audio/effect/UI 等服务。

重要工程含义：PAL3.Unity 不是一堆互不相关的 MonoBehaviour；它实际上有一个很清楚的**服务组合层**。很多修复应首先问：

> 真正的 state owner 是谁？Command executor 只是转发，还是它自己偷偷造状态？

### 2.2 Command system 是原版脚本语义与新引擎之间的总线

大量原游戏行为被还原为 `ICommand`：

- SCE 脚本解析命令；
- `CommandExecutorRegistry<ICommand>` 找 executor；
- manager 执行状态修改 / UI / scene action；
- SaveManager 反过来把当前状态再次序列化为 command 列表。

因此 command 的关键原则是：

> **command 查询必须读取真实 state owner；command 修改必须写入真实 state owner。**

开发期 hard-code 会直接污染剧情逻辑。

---

## 3. 已完成主线：Combat Domain（master patch 0001–0024）

当前 master 已建立的核心分层：

1. normal attack / hit resolution
2. combat runtime registry
3. skill domain contract
4. single-target skill resolution
5. GDB skill mapping / population audit
6. target resolver
7. multi-target resolution
8. multi-target presentation plan
9. HP recovery primitives / skill resolution

### 最重要的架构律

**Combat truth 与 presentation 分离。**

Presentation 只能消费已经解决的事实，不能：

- 选择目标；
- 重新计算 damage；
- 消耗 MP；
- 改 HP；
- 改 combat outcome。

这条规则后续所有动画、镜头、音效都必须遵守。

---

## 4. 动画 / VFX 书签（暂时不继续耗）

独立分支 / PR：`#105 PAL3: first visible Unity projectile presentation + procedural F7 smoke`

当前已经做到：

- Unity-facing projectile adapter；
- cast / travel / impact procedural fallback；
- `effectGroupId == 0` 表示开放程序化 VFX；
- 不依赖缺失的第三方 VFX prefab；
- C# contract compile；
- Editor-only procedural capture sandbox 与测试骨架。

当前 blocker：

- upstream README 明确说明 PAL3 VFX prefabs 因第三方插件/素材被 gitignore；已联系原作者；
- Unity activation 未配置，因此不能把 workflow green 写成 Unity compile success；
- 尚无真实 PAL3 combat runtime screenshot/video。

恢复条件：作者回复 VFX/plugin 信息，或取得 Unity activation / 可运行环境。

---

# Module A｜Script State × Inventory Truth

## A1. 为什么这一块优先级高

这不是 UI polish，而是剧情控制面。

### `ScriptVarSetMoneyCommand`（SCE Command 49）

命令定义的语义很明确：

> “取出当前金钱数并赋值给变量”

但 upstream `UserVariableManager.Execute(ScriptVarSetMoneyCommand)` 实际写入固定值：

```text
777777
```

这会导致任何依赖金钱变量的脚本分支都不是在读真实库存。

### `InventoryManager.HaveItem()`

upstream 对 `ItemType.Plot` 有开发捷径：无论玩家有没有拿到，只要数据库里是剧情道具，就直接返回 `true`。

而 `PalScriptRunner.Execute(ScriptEvaluateVarIfPlayerHaveItemCommand)` 正是通过 `InventoryManager.HaveItem(itemId)` 做脚本条件判断。

所以这不是“背包显示错误”，而是：

**剧情脚本 → HaveItem → 所有剧情道具自动存在 → 条件分支可能被提前满足。**

## A2. 为什么可以确认这是开发期假状态

`SaveManager.ConvertCurrentGameStateToCommands()` 已经把真实库存状态序列化为：

- `InventoryAddMoneyCommand(_inventoryManager.GetTotalMoney())`
- `InventoryAddItemCommand(item.Key, item.Value)`

也就是说存档设计本身已经把 InventoryManager 当作真实 state owner。

因此：

- `777777` 与 SaveManager 的真实金钱模型矛盾；
- Plot item 永远 true 与 SaveManager 的真实 item count 模型矛盾。

## A3. Step 5 修复

分支：`agent/pal3-step5-state-truth-inventory-script`

Patch `0100-inventory-script-state-truth.patch`：

1. `InventoryManager.HaveItem(itemId)` 改为只根据 `_items` 中真实 count 判断；
2. `UserVariableManager` 通过 `ServiceLocator` 查询真实 `InventoryManager.GetTotalMoney()`；
3. 不修改 command semantics，不伪造新状态格式。

## A4. 验证策略

新增 `PAL3 State Truth Gate`，在 ordered patch replay 之后验证：

- Plot item shortcut 已消失；
- `HaveItem` 读取真实 count；
- Script money 不再包含 `777777`；
- Command 49 仍然声明“取出当前金钱数”；
- PalScriptRunner 的物品条件仍走 InventoryManager；
- SaveManager 仍能把真实 money/items 写回存档 command。

证据边界：这是 **source-contract verification**，不是 Unity runtime playthrough。

---

## 5. 下一批程序修复地图

按“可玩性影响 × 可独立验证 × 不依赖 VFX”排序：

### P0 — 剧情 / 状态真相

- `ScriptVarSetCombatResultCommand`：当前用随机数伪造战斗结果，必须接真实 combat result state。
- Save/load state round-trip：继续审计哪些 manager 的状态仍未被完整保存。
- UserVariable / SceneState / Favor / Team 的 query-command 是否还有 hard-coded fallback。

### P1 — 核心 RPG 循环

- `TradingManager`：目前 dealer menu 只显示“交易功能暂未开启”。
- `HotelManager`：只有少数剧情特例可执行，普通住店仍未实现。
- Inventory item use / equipment / economy consistency。

### P1 — Combat 非演出层

- battle result propagation
- reward / EXP / money / drop
- status / buff / debuff
- MP/resource spending truth
- escape / defeat / post-combat state

### P2 — Data readers / content compatibility

继续审计明确抛 `NotImplementedException` 的 reader，例如：

- combat config / camera config
- MOV/MV3 config
- combat SCN
- task definition
- texture loader path

优先处理“真实 PAL3 数据一到手就会卡启动/剧情”的 reader。

### P2 — UI / presentation

- dealer / hotel UI
- combat UI
- VFX / camera / audio

动画分支已经书签化，资源/activation blocker 解除后恢复。

---

## 6. 每次修复都应该形成的学习条目

以后每修一个模块，本文件追加以下固定结构：

1. **原版语义 / command 或数据格式是什么**
2. **upstream 当前实现是什么**
3. **OBSERVED bug / TODO 是什么**
4. **为什么确定它不是有意设计**
5. **state owner / data flow / call chain**
6. **最小修复**
7. **回归风险**
8. **验证等级**
9. **下一层 blocker**

目标不是只得到一个能跑的 fork，而是最终得到一套可以从头读懂 PAL3.Unity 的工程教材。
