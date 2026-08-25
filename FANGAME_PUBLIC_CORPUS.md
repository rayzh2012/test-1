# Fangame Public Genome Corpus

The public corpus lives under [`public_reports/`](public_reports/README.md).

## Featured analysis

### Pokémon Unchosen v1.5.10 ENG JoiPlay

- Public Markdown report: [`public_reports/pokemon_unchosen_v1.5.10_eng_joiplay.md`](public_reports/pokemon_unchosen_v1.5.10_eng_joiplay.md)
- Machine-readable JSON: [`public_reports/pokemon_unchosen_v1.5.10_eng_joiplay.json`](public_reports/pokemon_unchosen_v1.5.10_eng_joiplay.json)
- Engine: RPG Maker MV + LeTBS
- Package size measured: 1,008,732,457 bytes
- Structural snapshot: 547 maps, 16,538 events, 32,037 event pages, 205,650 event commands, 357,172 dialogue characters, 7,823 choice options, 3,880 battle calls, 252 enabled plugins.

The publication layer contains structural analysis only. It does not publish game binaries, private Drive identifiers, private notes, or personal-fit scores.

## Method

The pipeline normalizes engine-specific RPG Maker data into a common structural profile, then emits a sanitized JSON/Markdown report. Ordinary-RPG-relative percentile claims are gated until a sufficiently large compatible reference corpus exists.
