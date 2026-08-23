# Pokemon Sisyphus Unchained — Public Genome

**Version:** current itch release  
**Engine:** RPG Maker XP  
**Package bytes:** 853,993,702  
**SHA256:** `ebd2bc828f260eec89492105c8b8c2f369934386b7d63bdaab933cd45f61b8b7`  
**Public source:** https://socialistcubone.itch.io/sisyphus-unchained  

## Structural feature vector

| Feature | Value |
|---|---:|
| Maps | 209 |
| Events | 2,688 |
| Event pages | 3,780 |
| Event commands | 37,350 |
| Dialogue blocks | 4,510 |
| Dialogue lines | 6,377 |
| Dialogue characters | 222,973 |
| Choice options | 2,020 |
| Conditional branches | 1,193 |
| Transfers | 500 |
| Native battle calls | 0 |
| Native shops | 0 |
| Common events | 10 |
| Actors (native DB) | 1 |
| Enemies (native DB) | 1 |
| Images | 10,114 |
| Audio | 1,032 |
| Events / map | 12.86 |
| Event commands / map | 178.71 |
| Dialogue chars / map | 1066.86 |
| Choice options / map | 9.67 |
| Conditional branches / map | 5.71 |
| Transfers / map | 2.39 |
| Native battle calls / map | 0.00 |
| Native random encounter map ratio | 0.00 |

## Metric semantics / engine caveats

- RGSS battle/shop/random-encounter counts describe native RPG Maker event/database structures. Script frameworks such as Pokemon Essentials can implement major systems outside those native slots, so native zero counts do not mean the game lacks those systems.
- RGSS database object counts can be placeholders when a custom script framework keeps gameplay data in separate files or scripts; interpret very small native database counts conservatively.

## Machine-generated descriptors

- **no_native_random_encounter_maps** — OBSERVED_STRUCTURE; evidence: `random_encounter_map_ratio=0`
- **dialogue_dense_absolute** — ABSOLUTE_HEURISTIC; evidence: `dialogue_chars_per_map=1066.86`

## Interpretation boundary

- This is a static structural measurement of the acquired package, not a claim that every branch or ending was manually played.
- `battle_calls = 0`, `shops = 0`, and tiny native database counts are **not** evidence that Pokémon Sisyphus Unchained lacks battles, shops, Pokémon, items, or progression. Pokémon Essentials implements much of that logic in scripts and framework data outside vanilla RGSS database/event slots.
- The strong observed signal here is narrative/event structure: 222,973 dialogue characters, 2,020 choice options, 1,193 conditional branches, and 500 map transfers across 209 maps.

## Baseline status

`REAL_ORDINARY_RPG_BASELINE_PENDING`

No production percentile or `top X%` claim is made until a compatible ordinary-RPG corpus is measured with the same parser family and schema.

## Publication boundary

This report publishes structural analysis only. It contains no game binary, private Drive identifier, or personal-fit score.
