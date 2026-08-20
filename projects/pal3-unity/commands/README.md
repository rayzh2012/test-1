# PAL3 Chat Command Ledger

This directory stores normalized command records for material ChatGPT-driven changes to PAL3.Unity.

A command record is not a transcript dump. It captures only the minimum auditable control intent needed to explain why a patch or control-plane change exists.

Each record should include:

- a stable command id and timestamp,
- the normalized user intent,
- the target subsystem or control-plane surface,
- the expected verification gates,
- evidence boundaries and known blockers,
- the resulting PR/commit/run ids once observed.

The live execution path remains:

`CHAT -> NORMALIZED COMMAND -> SOURCE READ -> SMALLEST CHANGE -> FAST LANE -> EVIDENCE RE-INGEST -> NEXT CHAT ITERATION`

Unity-dependent gates are a separate heavy lane. Missing Unity activation is recorded as `BLOCKED_NO_LICENSE`; it must not turn a successful fast-lane domain iteration into a false code failure.
