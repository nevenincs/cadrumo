---
tags:
  - '#reference'
  - '#filing-draft-modelo-typing'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:82aed0ed4ac066e875da7817a3cfc17b2de202b705b8e5a0c1816b3c011ba29c'
related: []
---

# `filing-draft-modelo-typing` reference: `Persisted draft modelo typing: code grounding`

Code grounding for the decision to retype the persisted draft modelo identifier.
Sources are the live tree at the record's date; every claim below is a locator a
reader re-opens, not a restatement of what it contains.

## Summary

### The field and its aggregate

- `src/cadrumo/domain/filing/schema.py:325` - `ModeloDraft.modelo: str`, the field
  under decision. The model is strict and frozen.
- `src/cadrumo/domain/filing/schema.py:337` - `snapshot_ref: RegistrySnapshotRef`,
  required with no default, so no stored draft can omit it and still load.
- `src/cadrumo/domain/filing/schema.py:356-397` - `_enforce_draft_invariants`,
  which refuses a draft whose modelo differs from `snapshot_ref.modelo` and whose
  `schema_version` is not the marker derived from that ref.
- `src/cadrumo/domain/calculations/registry/schema_references.py:114-120` -
  `RegistrySnapshotRef`, whose `modelo` field is `ModeloId`.
- `src/cadrumo/domain/filing/schema.py:456-496` - `compute_modelo_draft_id`; the
  modelo enters the hashed payload as a plain JSON scalar.

### The competing typed representations

- `src/cadrumo/domain/modelos/codes.py:16-38` - `ModeloCode`, a `str` subclass
  refusing anything but three digits, with a pydantic core schema running the same
  check on validation. Raises `ModeloValidationError`.
- `src/cadrumo/domain/modelos/errors.py` - `ModeloValidationError` subclasses both
  the project error hierarchy and `ValueError`, so it surfaces through pydantic
  validation rather than escaping the model build.
- `src/cadrumo/domain/calculations/registry/ids.py:10,21` - `ModeloId`, an
  annotated `str` carrying the identical three-digit pattern, used by the registry
  schema.
- `src/cadrumo/core/modelo.py:46-219` - the `Modelo` closed roster. Every member's
  value is exactly three digits; the roster includes the retired 037 and excludes
  codes such as 999 that existing tests use as shape-valid negatives.
- `src/cadrumo/domain/identifiers.py:28` - `ModeloIdentifier`, a fourth shape type
  admitting an optional uppercase suffix. Not used by the draft aggregate.
- No `ModeloCodeField` or `BeforeValidator` coercion exists for `ModeloCode`; the
  `coerce_enum_member` pattern is registry-schema-local
  (`domain/calculations/registry/schema_base.py` and its consumers).

### Sibling persisted records already typed

- `src/cadrumo/domain/modelos/work_unit.py:160`
- `src/cadrumo/domain/modelos/filing_record.py:184`
- `src/cadrumo/domain/modelos/participation_index.py:86`

All three declare `modelo: ModeloCode` and persist through the same encrypted
secure-object machinery as drafts, which establishes that the type round-trips
through the envelope serialiser.

### Consumers compensating for the untyped field

- `src/cadrumo/application/modelo/workspace.py:187,2192,2203` - read-boundary
  `ModeloCode(...)` re-wraps.
- `src/cadrumo/application/modelo/filing_actions.py:502,514` - a
  `str | ModeloCode | None` parameter coerced in the body.
- `src/cadrumo/application/filing/export_envelope.py:77-79,103-104,153` - the
  export boundary re-derives `Modelo` from the registry snapshot and separately
  asserts the draft's modelo equals the snapshot's, rather than trusting the draft
  field.

### Write and read paths

- `src/cadrumo/application/filing/draft_construction.py:147-193` - the sole
  production writer; `snapshot_ref` is built from `snapshot.modelo.id`
  (`ModeloDefinition.id: ModeloId`, `domain/calculations/registry/schema.py:1000`).
- `src/cadrumo/adapters/persistence/profile/filing_drafts.py` - the encrypted
  FINANCIAL repository; `save` re-derives and enforces the content address
  (lines 132-149), and enumeration verifies each record against the key it is
  filed under.
- `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py:1045-1054`
  - the filing-drafts namespace: FINANCIAL, profile-local, schema version 2,
  object-key grammar `{draft_id}`.

### Migration machinery

- `src/cadrumo/adapters/persistence/storage/schema_lineage.py` - the two-layer
  version policy and the one-hop upgrader registry, with the pre-release posture
  described in its module docstring: floors chase current versions and older
  shapes are deleted rather than migrated until the checkpoint flip.
- No production call to `register_secure_object_schema_upgrader` exists. The only
  registrations are in
  `adapters/persistence/storage/tests/test_schema_lineage.py:215,226` and
  `adapters/persistence/storage/sql/tests/test_secure_objects_schema_lineage.py:46`,
  all against scratch namespaces.
- Drift worth its own record: the `register_secure_object_schema_upgrader`
  docstring states that two namespaces register a real one-hop upgrader at the
  bottom of that file. The file registers none.

### Existing test surfaces to extend

- `src/cadrumo/domain/filing/tests/test_roundtrip_anti_tautology.py`
- `src/cadrumo/domain/filing/tests/test_secure_storage_roundtrip.py`

### What was not investigated

- No stored draft bytes were read; drafts are encrypted per-profile secure objects
  and no plaintext corpus exists in the repository. The on-disk acceptance claim
  is derived from the read path's invariants, not from sampling.
- The type checker was not run, so the exact diagnostic set the retype closes is
  not enumerated here.
- `ModeloIdentifier` and `ModeloId` consumers outside the draft aggregate were not
  surveyed; consolidating the four modelo shape types is a separate question.
