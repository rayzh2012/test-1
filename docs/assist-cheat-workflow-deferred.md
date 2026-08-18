# RPG Maker Assist / Cheat Workflow — Deferred Boundary

Status: DEFERRED. Do not implement in the current FG-004/005 workstream.

Future design goal: reuse the same RPG Maker Genome outputs across games so low-friction assist generation is portable rather than game-specific.

Expected common skeleton: database-driven actors/classes/items/skills/enemies, event commands, switches/variables, save/runtime state, and engine-specific script/plugin layers. Engine families and custom scripts may alter serialization, state semantics, or battle/economy logic, so portability must be verified rather than assumed absolute.

Safety default for future work: progression/QoL mutations such as EXP, gold, recovery, encounter pressure, retry/save friction, or other reversible numeric assists may be considered SAFE candidates after validation. Story/quest switches and variables are FORBIDDEN by default until their semantics are proven. Always preserve backup/rollback and loadability checks.
