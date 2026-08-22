# A King's Son — Public Genome

**Corpus role:** ordinary RPG reference  
**Version:** 1.6  
**Engine:** RPG Maker MV  
**Package bytes:** 202,420,886  
**SHA256:** `4462623cec4ba1b840c4f942c065b35b4e6bf6f8eb8777f55cb019111c895091`  
**Public source:** https://enzevil.itch.io/a-kings-son  

## Structural feature vector

| Feature | Value |
|---|---:|
| Maps | 23 |
| Events | 576 |
| Event pages | 888 |
| Event commands | 9,666 |
| Dialogue blocks | 1,547 |
| Dialogue lines | 3,906 |
| Dialogue characters | 89,537 |
| Choice commands | 72 |
| Choice options | 149 |
| Conditional branches | 201 |
| Transfers | 71 |
| Battle calls | 25 |
| Shops | 5 |
| Common events | 4 |
| Actors | 5 |
| Classes | 5 |
| Skills | 56 |
| Items | 25 |
| Enemies | 15 |
| Troops | 20 |
| States | 20 |
| Enabled plugins | 3 |
| Total plugins | 5 |
| Images | 176 |
| Audio | 136 |
| Events / map | 25.04 |
| Event commands / map | 420.26 |
| Dialogue chars / map | 3892.91 |
| Choice options / map | 6.48 |
| Conditional branches / map | 8.74 |
| Transfers / map | 3.09 |
| Battle calls / map | 1.09 |
| Maps with events ratio | 1.00 |
| Random encounter map ratio | 0.00 |

## Explicit system evidence

- `autosave_plugin`: `False`
- `difficulty_slider_plugin`: `False`
- `letbs_related_enabled_plugins`: `0`
- `new_game_plus_plugin`: `False`
- `quest_journal_plugin`: `False`
- `speed_up_plugin`: `False`

## Machine-generated descriptors

- **no_native_random_encounter_maps** — OBSERVED_STRUCTURE; evidence: `random_encounter_map_ratio=0`
- **scripted_or_event_driven_combat_structure** — DERIVED_STRUCTURE; evidence: `battle_calls=25; random_encounter_map_ratio=0`
- **dialogue_dense_absolute** — ABSOLUTE_HEURISTIC; evidence: `dialogue_chars_per_map=3892.91`

## Baseline status

`MV_JSON ordinary-RPG corpus: N=1 / DRAFT / production percentiles disabled.`

This sample is the first real ordinary-RPG measurement in the MV_JSON reference corpus. It is **not** enough to support a production percentile or `top X%` claim. The default production gate remains 20 compatible ordinary RPGs measured under the same normalized schema and parser family.

## Publication boundary

This report publishes structural analysis only. It contains no game binary, private Drive identifier, personal-fit score, full dialogue corpus, image/audio payload, or script source.
