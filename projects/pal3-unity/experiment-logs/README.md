# PAL3 Experiment Logs

Purpose: append-only, worker-readable engineering memory for the PAL3.Unity rewrite control plane.

## Mandatory worker protocol

Before starting a PAL3 combat/rewrite task, a worker must read:

1. `projects/pal3-unity/combat-magic-roadmap.md`
2. this README
3. `projects/pal3-unity/experiment-logs/index.json`
4. the latest relevant experiment log(s)
5. the current command ledger entry for the task, if one exists

Workers must not rely on chat history alone.

## Log rule

Every experiment gets one immutable-named JSON log under this directory. The file may be updated while the experiment is active, but after `status = VERIFIED`, `FAILED`, or `BLOCKED`, later work must create a new experiment log rather than rewriting history.

Each log records:

- objective and hypothesis
- base/upstream refs
- exact surfaces changed
- every meaningful attempt
- failures and their classifications
- fixes applied
- machine evidence (workflow/run/artifact/test counts)
- claim boundary: what was *not* proved
- reusable lessons for future workers
- next recommended experiment

## Failure classification

Use one of:

- `SOURCE_PATCH`
- `DOMAIN_COMPILE`
- `DOMAIN_TEST`
- `UNITY_ACTIVATION`
- `UNITY_COMPILE`
- `UNITY_RUNTIME`
- `DATA_MAPPING`
- `VISUAL_PRESENTATION`
- `CONTROL_PLANE`
- `UNKNOWN`

A failed attempt is valuable evidence and must not be deleted from the log after a later fix succeeds.

## Parallel-worker rule

Parallel workers should claim different numbered roadmap steps or different explicitly isolated subproblems. Before writing, re-read `index.json` and the latest logs to avoid duplicate experiments. Merge/rebase conflicts are evidence that ownership was not isolated enough.

## Claim discipline

`FAST_DOMAIN_TESTS = PASS` does not imply Unity compile/runtime/playtest success. `UNITY_COMPILE = PASS` does not imply gameplay correctness. Each verification layer remains separate.
