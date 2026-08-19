---
name: open-source-game-rewrite-controller
description: ChatGPT 直接控制开源游戏重写项目的 Source Control adapter。把上游代码库视为可复现输入，用 pinned upstream + patch stack + CI evidence report 管理修改；适用于 PAL3.Unity 等开源重写/移植项目，目标是无需 Cursor 也能完成读源码→定位模块→改代码→静态验证→CI→回灌状态的闭环。
version: 0.1
allowed-tools: [github, notion, google_drive, code_execution, file_ops]
---

# Open-source Game Rewrite Controller

## Purpose

这个 Skill 把“让 AI 帮我改一个开源游戏”从一次性聊天升级成长期可审计的控制系统。

核心公式：

`PINNED UPSTREAM -> SOURCE EVIDENCE -> TARGET MODULE -> PATCH STACK -> VERIFY -> CI ARTIFACT -> RE-INGEST -> NEXT PATCH`

ChatGPT 是控制面；GitHub Actions 是执行面；Notion/Drive 是长期状态与证据层。Cursor 只保留为可选 fallback，不是默认执行器。

## Control-plane model

### 1. Upstream stays reproducible

不要把整个第三方 Unity repo 粗暴复制进控制仓。

每个目标只保存：
- upstream repository
- pinned commit/ref
- engine/version
- source roots
- patch stack
- latest control report

CI 每次重新 checkout upstream，再依序 apply 本地 patch。这样上游升级、回滚、比较和复现都更简单。

### 2. Evidence before rewrite

第一次接入必须先做 source audit，而不是直接大改。

最小 evidence：
- upstream commit
- Unity / engine version
- source file count / LOC
- module topology
- TODO / FIXME
- NotImplementedException / NotSupportedException
- patch application status
- git diff --check
- build/runtime status（若 runner 能执行）

所有事实按 `OBSERVED / DERIVED / INFERRED / UNKNOWN` 分层。不能把“看起来像没实现”直接说成 runtime broken。

### 3. ChatGPT patch loop

每轮修改按以下顺序：

1. **READ**：读取 `control.json`、最新 CI report、目标上游文件。
2. **TARGET**：只选一个明确 module / bug / missing feature。
3. **PATCH**：根据上游 exact file content 生成最小 patch。
4. **VERIFY**：`git apply --check` → apply → `git diff --check` → source audit。
5. **BUILD**：有 Unity license/build runner 时再跑真实 Unity compile/build；没有时不得声称已编译通过。
6. **RE-INGEST**：把 report、diff、CI outcome 写回长期状态。
7. **NEXT**：从失败/marker/hotspot 中选下一块最高 Information Gain。

默认“小 patch 连续闭环”，不一次改几十个 subsystem。

## PAL3.Unity adapter

当前控制项目：
- control repo: `rayzh2012/test-1`
- project manifest: `projects/pal3-unity/control.json`
- upstream: `0x7c13/Pal3.Unity`
- patch stack: `projects/pal3-unity/patches/*.patch`
- controller: `tools/source_rewrite_controller.py`
- CI: `.github/workflows/pal3-unity-control.yml`

PAL3.Unity 的源代码与原版游戏数据分开处理。控制仓只管理开源代码修改；原版商业游戏资源保持外部用户自有数据，不提交进 repo。

## Commands / intent mapping

用户说：
- “scan / 扫一下 / 看看还有什么没写” → 跑 source audit，读取 report。
- “修这个” → fetch exact upstream files，生成最小 patch，跑 control CI。
- “继续重写” → 读取最近 report + patch stack，从最高价值未完成模块继续。
- “上游更新了” → 先改 pinned ref，在新 ref 上 `git apply --check` 全 patch；冲突必须显式记录。
- “做 iOS build” → 先确认 Unity build credentials / runner；source audit 通过不等于 iOS build 通过。
- “不要 Cursor” → 直接使用 GitHub connector + patch stack；Cursor 不进入主路径。

## Patch discipline

每个 patch 文件只解决一个主题，命名：

`0001-<module>-<intent>.patch`
`0002-<module>-<intent>.patch`

必须满足：
- 来源文件已读取；
- patch 可在 pinned upstream 上 clean apply；
- `git diff --check` 通过；
- report 记录 changed files；
- build 未运行时明确标记 `BUILD_UNKNOWN`。

禁止直接把 proprietary game data、账号凭证、Unity license、Apple signing material 写进 patch/control repo。

## Upgrade protocol

升级 upstream ref 时：

`OLD REF -> NEW REF -> APPLY ALL PATCHES -> CONFLICT AUDIT -> STATIC AUDIT -> BUILD -> ACCEPT/ROLLBACK`

如果 patch 冲突：
- 不静默丢 patch；
- 记录 conflict；
- 读取新 upstream 对应文件；
- 重写该 patch；
- 保留旧 patch/ref 的 provenance。

## Completion states

- `SOURCE_AUDITED`
- `PATCH_APPLIES`
- `STATIC_VERIFIED`
- `UNITY_COMPILE_VERIFIED`
- `RUNTIME_SMOKE_VERIFIED`
- `IOS_BUILD_VERIFIED`
- `PLAYTEST_VERIFIED`

后一级不能由前一级自动推断。

## Non-negotiable

**Source evidence != runtime evidence.**
**A patch that applies != a patch that works.**
**ChatGPT can be the controller without Cursor, but CI/build evidence仍然必须独立验证。**
