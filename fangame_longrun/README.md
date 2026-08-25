# Fangame Long-Run Agent — zero-cost proof lane

Status: **EXPERIMENTAL / PROOF_OF_POSSIBILITY**.

This lane exists to test whether an RPG Maker MV fangame can be exercised autonomously for long periods without a paid LLM API, paid GitHub larger runner, or a local desktop session.

## Current target

- Game: Final Redemption
- Package identity: inherited from `fangame_targets/final_redemption_mv.json`
- Runtime: the packaged RPG Maker MV web runtime in headless Chromium
- Input: real Playwright keyboard events
- Decision engine: runtime-symbolic agent reading `SceneManager`, `$gameMap`, `$gamePlayer`, `$gameMessage`, `$gameParty`, passability and battle state
- Initial duration: 10 minutes
- Maximum configured duration: 240 minutes
- External AI API: disabled
- Paid larger runner: disabled

## Evidence discipline

A long-running process is not automatically gameplay verification. The probe records elapsed playable time, map and coordinate progression, scene changes, battle entry/return-to-map, stalls, game-over/fatal stops, JSONL action trace and bounded screenshots.

Promotion gates remain separate:

1. `BATTLE_VERIFIED` — a real battle is entered and returns to `Scene_Map`.
2. `SAVE_LOAD_VERIFIED` — not implemented in v0.1; must be independently demonstrated.
3. `LONG_RUN_3H_VERIFIED` — at least 3 hours plus nontrivial progression and no fatal stop.
4. `LONG_RUN_4H_VERIFIED` — at least 4 hours plus nontrivial progression and no fatal stop.

## How to scale without opening a paid service

`current_longrun.json` is the control file. The first run uses `duration_minutes: 10`. Once the proof is healthy, change it to `180` or `240` and push the config. The workflow uses only `ubuntu-latest`; it must never be changed to a larger/GPU runner for the zero-cost lane.

Game binaries are temporary runner data and are never committed or uploaded as workflow evidence. Only small logs, summaries and screenshots are retained.
