# PAL3 Combat + Magic Roadmap v0.1

## Goal
Build a complete, testable RPG combat system for PAL3.Unity while keeping expensive bespoke animation work bounded.

Core rule: **mechanics are data-driven and presentation is template-driven**. A skill may be mechanically complex without requiring a unique animation pipeline.

## Architecture

```text
GDB SkillInfo / CombatActorInfo
        |
        v
SkillDefinition / RuntimeCombatState
        |
        v
TargetResolver -> CostResolver -> SkillResolver -> StatusResolver -> VictoryResolver
        |
        v
CombatEvent[]
        |
        +--> logging / tests / simulation
        |
        +--> SkillVisualProfile -> Unity presentation adapter
```

### Domain layer
Owns deterministic combat truth:
- current HP / MP / SP
- attack / defense / speed / luck
- five-element values
- target selection
- skill costs
- multi-effect skill resolution
- buffs / debuffs / poison / control states
- elemental modifiers
- death / victory / rewards

### Presentation layer
Owns only how domain events are shown:
- cast animation
- VFX prefab/profile
- projectile or area timing
- camera profile
- impact cue
- hit reaction
- damage/heal numbers
- sound

Domain code must never depend on a bespoke animation existing.

## Visual archetypes
Start with a deliberately small vocabulary. Most skills map to one of these profiles:

1. `MeleeImpact`
2. `Projectile`
3. `DescendStrike`
4. `AreaBurst`
5. `GroundField`
6. `SupportPulse`
7. `SelfAura`
8. `BossSpecial`

A visual profile may vary by element, scale, timing, prefab, sound, camera and hit reaction without changing skill mechanics.

## Ordered implementation plan

### STEP 0 - Normal attack vertical slice
**Status: VERIFIED**
- one-shot animation hit seam
- encounter-local HP state
- provisional normal-attack damage
- fast-lane domain tests

### STEP 1 - Skill domain contract
**Goal:** define what a skill is before implementing any specific spell.

Deliverables:
- `SkillDefinition`
- `SkillEffectDefinition`
- `SkillVisualArchetype`
- support multiple effects per skill
- MP/SP costs
- target range
- element
- validation tests

Acceptance gate:
- pure C# compile
- all existing combat tests remain green
- new contract tests green
- no Unity dependency

### STEP 2 - First single-target damage spell
**Goal:** one generic spell executes end-to-end in the domain.

Deliverables:
- target one enemy
- consume MP
- resolve elemental damage
- mutate encounter-local HP
- emit `SkillCast` + `Damage` events
- no bespoke VFX yet

Acceptance gate:
- insufficient MP rejected
- target validation
- deterministic damage
- death state can be produced

### STEP 3 - SkillInfo adapter
Map upstream GDB `SkillInfo` into our domain contract.

Fields to consume first:
- Id / Type / Name
- ElementAttributes
- TargetRangeType
- AttributeImpacts
- CombatStateImpactTypes
- SpConsumeValue / MpConsumeValue
- level metadata only as data, not yet progression logic

Important: preserve unknown or unsupported semantics instead of inventing them.

### STEP 4 - Visual profile contract + first generic spell presentation
Add a Unity adapter for one archetype only: `Projectile` or `AreaBurst`.

Success means:
- domain resolves independently
- presentation consumes combat events
- visual timing cannot alter damage truth

### STEP 5 - Multi-target targeting
Implement:
- enemy all
- ally all
- enemy row
- enemy column

No new VFX architecture; reuse existing profiles.

### STEP 6 - Healing and support
Implement:
- HP recovery
- recover-to-max
- attack/defense/speed/luck modifiers
- self / single ally / party targets

### STEP 7 - Combat states
Implement state engine:
- poison families
- paralysis / seal / sleep / chaos / madness
- reflection / evade / barrier
- death / dying
- resist states

Each state must define lifecycle, stacking/refresh policy and action restrictions.

### STEP 8 - Five-element system
Implement explicit, testable elemental modifiers using locked evidence or a documented fangame baseline where original rules are unknown.

Never silently present a guessed formula as original PAL3 behavior.

### STEP 9 - Turn / action scheduler
Replace developer-harness combat control with a real action loop:
- eligibility
- speed/order policy
- player action request
- enemy AI action
- terminal-state guard

### STEP 10 - Enemy AI
Start with deterministic policy:
- valid target selection
- normal attack fallback
- skill use when affordable
- no targeting defeated units

Then add archetype/Boss policies.

### STEP 11 - Death, victory, rewards and exit
Close the battle loop:
- death state
- victory / defeat
- EXP / money / loot
- return to map
- no save-state corruption

### STEP 12 - Battle UI
Only after the domain loop is stable:
- HP/MP/SP
- action menu
- skill list
- targeting
- status icons
- combat log / debug overlay

### STEP 13 - Visual expansion
Build reusable profiles before bespoke skills.

Priority:
1. generic elemental damage
2. heal/support
3. poison/status
4. signature protagonist skills
5. Boss skills
6. combo skills

### STEP 14 - Combo skills / special systems
Only after ordinary skills are stable:
- combo requirements
- formation requirements
- corpse-drop triggers
- steal
- special skill IDs

## Per-step workflow
Every step uses the same control loop:

```text
READ EXACT SOURCE
-> WRITE SMALLEST ORDERED PATCH
-> REPLAY PATCH STACK
-> FAST DOMAIN TESTS
-> SOURCE AUDIT
-> UNITY GATE WHEN AVAILABLE
-> EVIDENCE RE-INGEST
-> MERGE ONLY WHEN CURRENT HEAD IS GREEN
-> NEXT STEP
```

## Stop conditions
Do not expand scope if:
- current patch stack no longer replays cleanly
- deterministic tests cannot define expected behavior
- a guessed PAL3 formula is being treated as fact
- presentation code starts owning combat truth
- one skill requires a new bespoke subsystem when a reusable archetype would work

## Current next action
**STEP 1 only: Skill domain contract.**
Do not implement a concrete PAL3 spell until this contract is machine-verified.
