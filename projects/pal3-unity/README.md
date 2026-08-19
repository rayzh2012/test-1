# PAL3.Unity ChatGPT Control Target

This directory is the control-plane state for the upstream open-source project `0x7c13/Pal3.Unity`.

## Why this is not a fork copy

The upstream repository remains the reproducible source input. This control repository stores only:

- a pinned upstream commit,
- rewrite policy,
- an ordered patch stack,
- CI evidence.

That keeps upstream updates cheap and makes every ChatGPT change auditable.

## Loop

1. CI checks out the pinned upstream.
2. `tools/source_rewrite_controller.py` applies `patches/*.patch` in lexical order.
3. The controller inventories source modules and implementation markers.
4. It emits `source_control_report.json`, `source_control_report.md`, and `applied.patch`.
5. ChatGPT reads the report plus exact upstream source files and creates the next smallest patch.

## Current first milestone

`SOURCE_AUDITED` — establish the real code surface and unresolved implementation markers before choosing the first rewrite target.

Runtime/build milestones are deliberately separate:
`STATIC_VERIFIED -> UNITY_COMPILE_VERIFIED -> RUNTIME_SMOKE_VERIFIED -> IOS_BUILD_VERIFIED`.

Original PAL3/PAL3A commercial game data is not part of this control repository.
