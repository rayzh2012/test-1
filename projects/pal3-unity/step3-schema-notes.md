# Step 3 schema notes — real `SkillInfo`

Observed directly from pinned upstream `Pal3.Core.DataReader.Gdb.SkillInfo`:

- source elements are `HashSet<ObjectElementType>`; current `SkillDefinition` stores one `ElementType`;
- MP/SP consumption each have both `AttributeImpactType` and value; current runtime executor only understands absolute integer cost;
- source includes special consumption type/impact/value;
- source includes success-rate level and special-skill ID;
- source retains applicable actors, level/progression chain, outside-combat usage, composite-skill requirements and combo trigger metadata;
- source attribute and combat-state effects are dictionaries and may contain multiple effects.

Step 3 policy: never coerce multi-element to `.First()`, never reinterpret percentage cost as absolute, never drop special consumption or behavior silently. The mapping result retains the original `SkillInfo` and emits structured issues for semantics not projected into the current runtime domain.
