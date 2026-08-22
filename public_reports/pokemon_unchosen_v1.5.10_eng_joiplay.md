# Pokémon Unchosen — Public Genome

**Version:** 1.5.10 ENG JoiPlay  
**Engine:** RPG Maker MV + LeTBS  
**Package bytes:** 1,008,732,457  
**SHA256:** `e4bc61584b70929b456c3022b0a13d1c6c75c5bdf3424091c157d494e185d613`  
**Public source:** https://aldrine.itch.io/pokemon-unchosen  

## Structural feature vector

| Feature | Value |
|---|---:|
| Maps | 547 |
| Events | 16,538 |
| Event pages | 32,037 |
| Event commands | 205,650 |
| Dialogue blocks | 7,866 |
| Dialogue characters | 357,172 |
| Choice options | 7,823 |
| Battle calls | 3,880 |
| Shops | 10 |
| Enabled plugins | 252 |
| Events / map | 30.23 |
| Event commands / map | 375.96 |
| Dialogue chars / map | 652.97 |
| Choice options / map | 14.30 |
| Random encounter map ratio | 0.00 |

## Explicit system evidence

- `autosave_plugin`: `True`
- `difficulty_slider_plugin`: `True`
- `letbs_related_enabled_plugins`: `37`
- `new_game_plus_plugin`: `True`
- `quest_journal_plugin`: `True`
- `speed_up_plugin`: `True`

## Machine-generated descriptors

- **large_map_surface** — ABSOLUTE_HEURISTIC; evidence: `maps=547`
- **heavy_event_scripting** — ABSOLUTE_HEURISTIC; evidence: `event_commands=205650`
- **broad_plugin_surface** — ABSOLUTE_HEURISTIC; evidence: `enabled_plugins=252`
- **no_native_random_encounter_maps** — OBSERVED_STRUCTURE; evidence: `random_encounter_map_ratio=0`
- **scripted_or_event_driven_combat_structure** — DERIVED_STRUCTURE; evidence: `battle_calls=3880; random_encounter_map_ratio=0`
- **dialogue_dense_absolute** — ABSOLUTE_HEURISTIC; evidence: `dialogue_chars_per_map=652.97`
- **choice_dense_absolute** — ABSOLUTE_HEURISTIC; evidence: `choice_options_per_map=14.30`
- **multiple_explicit_qol_or_meta_systems** — OBSERVED_SYSTEM_EVIDENCE; evidence: `autosave_plugin, difficulty_slider_plugin, new_game_plus_plugin, quest_journal_plugin, speed_up_plugin`

## Baseline status

`REAL_ORDINARY_RPG_BASELINE_PENDING`

No production percentile or `top X%` claim is made unless a compatible ordinary-RPG corpus was measured with the same schema/parser family.

## Publication boundary

This report publishes structural analysis only. It contains no game binary, private Drive identifier, or personal-fit score.
