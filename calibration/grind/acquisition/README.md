# Calibration Acquisition v0.7

This layer decides where the next unit of evidence-collection or human-review effort should go. It does not create labels and it does not score grind.

## Three separate artifacts

1. **Inventory = FACT**
   - canonical grind-vector availability/coverage
   - active label count
   - independent evidence-group count
   - known/unknown dimensions
   - active label conflicts

2. **Acquisition Policy = POLICY**
   - whether a vector is required before labeling
   - target independent-source count
   - target dimension coverage
   - whether conflicts should be adjudicated
   - explicit ordering of review actions

3. **Queue = DECISION**
   - `BACKFILL_VECTOR`
   - `ADJUDICATE_CONFLICT`
   - `ADD_FIRST_LABEL`
   - `ADD_INDEPENDENT_LABEL`
   - `FILL_UNKNOWN_DIMENSIONS`
   - `NO_ACTION`

Changing policy must be able to change the queue without changing inventory facts or queue code.

## No active production acquisition policy yet

The repository ships the contract and deterministic decision engine, but no production policy. This prevents hidden priorities from becoming de facto governance.

The same pattern generalizes to enterprise human review: missing evidence, disagreement, weak coverage, or stale derivations become inventory facts; review priorities are explicit policy; the queue is a reproducible decision artifact.
