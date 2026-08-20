# PAL3.Unity ChatGPT Control Target

This directory is the control-plane state for the upstream open-source project `0x7c13/Pal3.Unity`.

## Why this is not a fork copy

The upstream repository remains the reproducible source input. This control repository stores only:

- a pinned upstream commit,
- rewrite policy,
- an ordered patch stack,
- normalized ChatGPT command provenance,
- CI evidence.

That keeps upstream updates cheap and makes every ChatGPT change auditable.

## Direct ChatGPT loop

The intended interactive path is now:

`CHAT -> NORMALIZED COMMAND -> SOURCE READ -> SMALLEST PATCH/CONTROL CHANGE -> FAST LANE -> EVIDENCE RE-INGEST -> NEXT CHAT ITERATION`

Cursor is not required in the default path.

### Fast lane

`PAL3 Chat Fast Lane` is the low-latency verification path. It:

1. checks out the pinned upstream without LFS,
2. replays `patches/*.patch`,
3. runs source/diff audit,
4. executes registered Unity-independent domain test slices from `fast-tests.json`,
5. uploads machine-readable evidence for ChatGPT to re-ingest.

A fast-lane PASS means the registered domain slice compiled/executed successfully after patch replay. It does **not** imply Unity/runtime/platform success.

### Unity lane

Unity import/compile, EditMode/runtime, iOS and playtest remain separate heavy gates. Missing Unity activation is classified as `BLOCKED_NO_LICENSE`, not as a source-code failure.

## Current verified state

- `SOURCE_AUDITED`: verified.
- `FIRST_PATCH_APPLIES`: verified.
- `COMBATCORE_DOMAIN_TESTS`: verified; 10/10 tests passed in the first realtime fast-lane run.
- `UNITY_COMPILE_VERIFIED`: open; currently blocked by missing Unity activation material.
- `RUNTIME_SMOKE_VERIFIED`: open.
- `IOS_BUILD_VERIFIED`: open.
- `PLAYTEST_VERIFIED`: open.

Original PAL3/PAL3A commercial game data is not part of this control repository.
