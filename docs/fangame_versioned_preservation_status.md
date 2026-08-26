# Fangame Versioned Preservation v0.1 — implementation status

Implemented in this branch:

- deterministic extracted-tree release manifest
- release lineage fields (`release_kind`, `parent_release_id`)
- file-level SHA-256 and deterministic content root hash
- parent/child diff: added, removed, changed, unchanged, reused-by-hash
- byte reuse ratio estimation
- rollback object plan from current release to target release
- explicit distinction between content-exact reconstruction and byte-exact raw-package reconstruction
- checkpoint/delta storage policy specification
- unit tests for deterministic hashing, diff, rename/reuse detection, and rollback planning

Not yet claimed complete:

- content-addressed Drive object packing
- automatic xdelta3 raw-package delta generation
- automatic checkpoint selection based on measured delta size
- actual checkout/reconstruction executor
- post-reconstruction byte/hash verification in CI

These are intentionally separate so v0.1 does not overclaim rollback fidelity before the object/delta layer exists.
