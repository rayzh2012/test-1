# PAL3.Unity Human Devlog Protocol

This directory is the human-readable publication layer for the PAL3.Unity ChatGPT rewrite project.

The machine-readable source of truth remains:

- `../commands/` — normalized ChatGPT commands;
- `../experiment-logs/` — one experiment log per material attempt, preserving failures and fixes;
- GitHub Actions evidence artifacts — machine verification;
- `../control.json` — pinned upstream and ordered patch stack.

The human devlog is **not allowed to replace machine evidence**. It explains that evidence as a chronological engineering story.

## Two-level publication model

### Append-only worker entries

`entries/*.md`

Every material terminal experiment gets one uniquely named human-readable entry. This is the parallel-worker-safe write surface.

Workers may create or finish **their own** entry, but they must not rewrite another terminal entry.

`entries/index.json` records the experiment → human-entry relationship and machine evidence IDs.

### Aggregate publication snapshot

`PAL3-AI-DEVLOG.md`

This is the continuous long-form publication snapshot suitable for:

1. GitHub Gist;
2. Medium;
3. a static blog;
4. any Markdown publishing system.

The aggregate is updated serially from historical content plus terminal entry files. Parallel workers must not concurrently rewrite it; that would turn the blog into a merge-conflict hotspot.

The current ChatGPT/GitHub connector does not expose a create/update Gist action, so repository Markdown remains the canonical writable mirror until a Gist-capable write surface is available.

## Required entry structure

Every material experiment that reaches a terminal state must be represented by a human entry containing:

- date/time or milestone order;
- experiment ID and PR when available;
- objective;
- what was actually changed;
- attempts made;
- failures observed, including failed hypotheses and infrastructure blockers;
- fixes applied;
- machine evidence (workflow/run/artifact/test counts where available);
- claim boundary — what is **not** proven yet;
- reusable lesson for future workers;
- next experiment.

If an experiment succeeds on the first attempt, write `Failures: none observed` / `PASS on first attempt` rather than inventing a failure narrative.

If a later attempt fixes an earlier failure, the earlier failure must remain in the published history.

## Parallel-worker rule

Before acting or writing, a worker must re-read:

1. `../combat-magic-roadmap.md`;
2. `../experiment-logs/README.md`;
3. `../experiment-logs/index.json`;
4. the latest relevant experiment logs;
5. this README;
6. `entries/index.json`;
7. the latest relevant human entry;
8. the current command record.

A worker writes one uniquely named entry for its experiment. It must not directly rewrite `PAL3-AI-DEVLOG.md` while other workers may be active.

## Publication principle

The devlog should be readable by a developer who has never seen the ChatGPT conversation. It should answer:

> What did the AI try, what actually happened on a machine, what failed, what was repaired, what remains unproven, and what should the next worker do?

The aggregate can later be mirrored to a Gist or edited into a Medium series, but publication cleanup must not erase failed attempts or blur verification boundaries.
