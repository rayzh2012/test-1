# PAL3.Unity Human Devlog Protocol

This directory is the human-readable publication layer for the PAL3.Unity ChatGPT rewrite project.

The machine-readable source of truth remains:

- `../commands/` — normalized ChatGPT commands;
- `../experiment-logs/` — one experiment log per material attempt, preserving failures and fixes;
- GitHub Actions evidence artifacts — machine verification;
- `../control.json` — pinned upstream and ordered patch stack.

The human devlog is **not allowed to replace machine evidence**. It explains that evidence as a chronological engineering story.

## Canonical publication file

`PAL3-AI-DEVLOG.md`

This file is intentionally plain Markdown so it can be copied or mirrored with minimal editing to:

1. GitHub Gist;
2. Medium;
3. a static blog;
4. any Markdown publishing system.

The current ChatGPT/GitHub connector does not expose a create/update Gist action, so the repository Markdown is the canonical writable mirror until a Gist-capable write surface is available.

## Required entry structure

Every material experiment that reaches a terminal state must eventually be represented in the human devlog with:

- date/time or milestone order;
- objective;
- what was actually changed;
- attempts made;
- failures observed, including failed hypotheses and infrastructure blockers;
- fixes applied;
- machine evidence (PR/run/artifact/test counts where available);
- claim boundary — what is **not** proven yet;
- reusable lesson for future workers;
- next experiment.

If an experiment succeeds on the first attempt, write `Failures: none observed` rather than inventing a failure narrative.

If a later attempt fixes an earlier failure, the earlier failure must remain in the published history.

## Parallel-worker rule

Before writing a new human-log entry, a worker must re-read:

1. `../combat-magic-roadmap.md`;
2. `../experiment-logs/README.md`;
3. `../experiment-logs/index.json`;
4. the latest relevant experiment logs;
5. this README;
6. the tail of `PAL3-AI-DEVLOG.md`.

Workers must append a new uniquely identifiable milestone rather than rewriting old history.

## Publication principle

The devlog should be readable by a developer who has never seen the ChatGPT conversation. It should answer:

> What did the AI try, what actually happened on a machine, what failed, what was repaired, what remains unproven, and what should the next worker do?
