# Final Redemption — Public Genome

**Version:** 2026-08-16 current itch build  
**Engine:** RPG Maker MV  
**Package bytes:** 1,005,259,975  
**SHA256:** `692ce84549b838c095c0f777b6085f2d9eeabdfe3a73c40431c061f8c8d68c3b`  
**Public source:** https://infiniv.itch.io/final-redemption  
**Source-page release status:** Prototype

> The source page describes roughly 40–60 hours, many side quests, up to 130 recruitable characters, freer exploration later in the game, and a few alternate endings. The structural measurements below strongly support a very large content surface, but they do **not** override the author's current `Prototype` status or prove release completeness.

## Structural feature vector

| Feature | Value |
|---|---:|
| Maps | 999 |
| Events | 9,631 |
| Event pages | 13,845 |
| Event commands | 224,227 |
| Dialogue blocks | 22,537 |
| Dialogue lines | 33,788 |
| Dialogue characters | 1,013,558 |
| Choice commands | 1,791 |
| Choice options | 3,824 |
| Conditional branches | 18,188 |
| Transfers | 4,427 |
| Battle calls | 1,793 |
| Shops | 194 |
| Common events | 12 |
| Actors | 190 |
| Classes | 48 |
| Skills | 287 |
| Items | 851 |
| Weapons | 167 |
| Armors | 270 |
| Enemies | 587 |
| Troops | 796 |
| States | 10 |
| Enabled plugins | 2 |
| Total plugins | 2 |
| Images | 2,494 |
| Audio | 459 |
| Events / map | 9.64 |
| Event commands / map | 224.45 |
| Dialogue chars / map | 1,014.57 |
| Choice options / map | 3.83 |
| Conditional branches / map | 18.21 |
| Transfers / map | 4.43 |
| Battle calls / map | 1.79 |
| Maps with events ratio | 1.00 |
| Random encounter map ratio | 0.4915 |
| Encounter-step median | 30 |

## Runtime evidence — 2026-08-23

The exact package above was re-fetched and passed its expected byte-count and SHA256 identity gates before runtime testing.

- **Windows package under Wine/Xvfb:** `Game.exe` opened a visible window titled `Final Redemption` and the process stayed alive, but the image remained on `Now Loading...` through an extended 60-second test and after confirm/directional input. Chromium/NW.js emitted GPU/context failures under the CI Wine graphics stack. This path is therefore classified as **runtime alive / compatibility unresolved**, not as a broken game and not as verified gameplay.
- **Native Chromium execution of the packaged MV web layer:** the package's own `www/index.html` loaded successfully with PixiJS/WebGL, with no page-level JavaScript exceptions recorded. Semantic screenshot review confirmed the actual **Final Redemption title screen** with `New Game / Continue / Options`.
- **New Game verified:** pressing Enter on `New Game` transitioned into the opening prologue. Runtime state changed from `Scene_Title` to `Scene_Map`, initially on map 32 with an active story event.
- **Intro progression verified:** repeated confirm input advanced the prologue normally. After 30 confirm inputs the runtime reached an idle `Scene_Map` on **map_id 2**, with no active message and no running autorun interpreter.
- **Map gameplay verified:** before movement, `$gamePlayer` was at **(14, 9)** facing down. Holding `ArrowRight` moved the same player to **(15, 9)** and changed direction to right (`6`). Screenshot evidence shows the controllable location **Mt. Kolts Cave Passage** before and after the move. This is direct engine-state evidence, not a pixel-animation proxy.
- **Still unverified:** battle completion, save/load, long-session stability, and absence of later softlocks.

Current conservative runtime classification: **`PLAYABILITY_VERIFIED_MAP_GAMEPLAY`**. The acquired package demonstrably loads the title screen, starts a new game, advances through the opening sequence, reaches an idle playable map, and accepts movement input on a current Chromium-compatible RPG Maker MV runtime path. Native Windows behavior remains distinct from the Wine CI result and has not been directly certified here.

## Machine-generated descriptors

- **large_map_surface** — absolute/versioned heuristic; evidence: `maps=999`
- **heavy_event_scripting** — absolute/versioned heuristic; evidence: `event_commands=224227`
- **broad_database_surface** — absolute/versioned heuristic; evidence: `database_objects=3218`
- **dialogue_dense_absolute** — absolute/versioned heuristic; evidence: `dialogue_chars_per_map=1014.57`

## Baseline status

`REAL_ORDINARY_RPG_BASELINE_PENDING`

No production percentile or `top X%` claim is made until a sufficiently large compatible ordinary-RPG corpus exists under the same normalized schema/parser family.

## Publication boundary

This report publishes structural analysis and bounded runtime evidence only. It contains no game binary, private Drive identifier, private note, personal-fit score, or extracted game-content corpus.
