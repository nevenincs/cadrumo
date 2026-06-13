---
tags:
  - '#adr'
  - '#cross-domain-continuity'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-19-profile-lifecycle-disaster-adr]]"
  - "[[2026-05-29-cross-domain-continuity-audit]]"
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - '[[2026-06-04-cross-domain-continuity-research]]'
---


# `cross-domain-continuity` adr: `profile-portability` | (**status:** `accepted`)

Status becomes `accepted` when S104-S109 land and the roundtrip test (S107)
passes. Supersedes the deferred bundle-content decision in the 2026-05-18
lifecycle ADR (§Ruling 6 placeholder).

## Problem Statement

`aeat config profile export` currently serialises only the operator's
`UserProfileRecord` (identity facts: tax id, display name, status,
effective-dated fact tuples). The four financial-history stores attached to
a profile bucket — work units, ledger transactions, calculation revisions,
and filing records — are absent from the bundle. A colleague handover or
disaster-recovery restore therefore loses all financial history; only identity
facts survive.

In addition, the current import path discards the bundle's originating
`profile_id` and mints a fresh UUID, making idempotent re-import impossible
and orphaning any domain-object cross-references that were keyed on the
original identity. The re-import collision check is label-based, not
identity-based.

No ADR previously addressed: which domain objects belong in the bundle;
how encrypted material should be handled across custody boundaries; how
provenance fields must survive the serialisation round-trip; what the
schema-version contract is; or what the canonical idempotency strategy is.

This ADR supplies those decisions so that W06.P28-P29 (S104-S109) can
proceed with a stable contract.

## Considerations

**Bundle content scope.** A profile bucket holds five categories of
durable state: the `UserProfileRecord` (facts); `ModeloWorkUnit` and
`LedgerWorkUnit` records (work units); ledger transactions; `CalculationRevision`
records (including typed `CasillaObservation` envelopes); and filing records.
Event-log history (`WorkflowState` events) is diagnostic metadata.

All five financial-history categories belong in the bundle for colleague
handover to be viable. Event-log history is omitted: it is machine-local
audit trail, not portable financial state.

**Encrypted material custody.** Each bucket's data-encryption key (DEK)
is wrapped with the operator's key-encryption key (KEK), derived from their
passphrase via HKDF. Exporting wrapped DEK material is useless to the recipient
(they do not have the originator's passphrase) and expands the attack surface
of the bundle. The correct pattern is to serialise the decrypted domain-model
payloads into the bundle and let the import path re-encrypt each object under
the recipient's own bucket DEK.

**Provenance preservation.** `CalculationRevision.observations` is a typed
tuple of `CasillaObservation` records, each carrying `legal_refs`,
`source_refs`, and `formula_id`. The calculation-grounding rule requires
these provenance fields to survive every domain boundary. A serialisation
step that substitutes the flat `casilla_values` derived mapping for the typed
`observations` tuple erases provenance silently; the operator has no way to
detect the loss.

**Schema versioning.** The current `bundle_schema_version: int = 1` field
in `UserProfilePortableExport` is emitted and read back, but the import path
does not validate it against a supported range before parsing. A forward-
incompatible bundle from a newer version of the tool would be parsed without
error until a field mismatch surfaces at runtime.

**Idempotency.** The canonical use-case for `profile import` is disaster
recovery and colleague handover — both cases where re-running the import
command should not create a duplicate profile. The originating `profile_id`
(a UUID) is the stable identity for cross-object references; discarding it on
import makes re-import semantics undefined.

## Constraints

- The architecture-boundaries rule forbids `dict[str, Any]` at persisted
  record, wire payload, or CLI output boundaries. All bundle payloads must
  be typed pydantic models throughout the serialise/deserialise cycle.
- The calculation-grounding rule requires `legal_refs`, `source_refs`, and
  `formula_id` to be present on every `CasillaObservation` that crosses a
  domain boundary. These fields must not be dropped by `exclude_none` or
  by substituting the flat `casilla_values` view.
- The disaster-recovery ADR (`2026-05-19-profile-lifecycle-disaster-adr.md`)
  classifies `profile import` as a bootstrap-exempt verb: it must run without
  an active root session. The full-bundle import must preserve this property.
- The lifecycle ADR (`2026-05-18-profile-lifecycle-cli-adr.md`) requires every
  profile-create path — including import — to route through the single atomic
  provisioner (`register_active_profile`): bucket directory + manifest +
  encrypted record + active pointer in one all-or-nothing sequence with
  rollback on failure.

## Decisions

### D1 — Bundle content expansion

`UserProfilePortableExport` is extended to `bundle_schema_version = 2` with
four additional typed fields:

```
work_units: tuple[ModeloWorkUnit | LedgerWorkUnit, ...] = ()
ledger_transactions: tuple[LedgerTransaction, ...] = ()
calculation_revisions: tuple[CalculationRevision, ...] = ()
filing_records: tuple[FilingRecord, ...] = ()
```

All fields default to empty tuples so that a v2 serialiser is backward-
compatible with consumers that only read v1 facts. Event-log history is
excluded (machine-local audit trail, not portable financial state).

The serialiser reads each category from the active bucket's
`SecureObjectRepository` before constructing the bundle.

### D2 — Encrypted material handling

No encrypted blobs are included in the bundle. The bundle contains decrypted
pydantic domain-model payloads only. On import, each domain object is
re-encrypted under the recipient's own bucket DEK via the standard
`SecureObjectRepository.save()` path. This is the correct custody-transfer
pattern: data portability without key portability.

### D3 — Provenance preservation contract

Serialisation uses `model.model_dump(mode="json")` on the full pydantic
model throughout. Deserialisation uses `Model.model_validate(data)`. No
`dict[str, Any]` intermediate. `exclude_none=True` is forbidden in bundle
serialisation; optional provenance fields that are present must survive.

The `CalculationRevision.observations` typed tuple is the canonical field;
the flat `casilla_values` derived property must not substitute for it in the
bundle payload.

The S107 roundtrip test must assert strict pydantic equality on
`revision_a.observations == revision_b.observations` across the
export/import boundary.

**Anti-tautology proof (mandatory in S107):** Mutate one `legal_refs` entry
in the exported JSON before import. Assert that `Model.model_validate` raises
`ValidationError`, OR that the re-imported revision's `legal_refs` does not
equal the original. If neither condition fires, the provenance boundary is
tautological and the test must be rewritten.

### D4 — Schema versioning contract

`bundle_schema_version` is an integer field on `UserProfilePortableExport`:
- Version 1: facts-only bundle (current shape). Remains importable.
- Version 2: facts + work units + ledger + revisions + filings (this ADR).

A constant `SUPPORTED_BUNDLE_SCHEMA_VERSIONS: frozenset[int] = frozenset({1, 2})`
lives at the import boundary in `src/aeat/application/user_profile/`. The import
path validates `bundle.bundle_schema_version in SUPPORTED_BUNDLE_SCHEMA_VERSIONS`
before any further parsing. An unsupported version raises `CliRefusedBoundaryError`
with a user-readable message naming the received version and the supported range.

Incrementing `bundle_schema_version` is required only for backward-incompatible
shape changes. Adding optional fields with defaults is non-breaking and does not
require a version bump.

### D5 — Idempotency strategy: refuse-on-profile-id-collision

The import path preserves the bundle's `profile_id` (UUID) and does not mint
a fresh UUID. Identity is stable across the export/import boundary.

Before writing, a two-tier collision guard runs:

1. **UUID collision:** if `profile_id` from the bundle already exists locally,
   refuse with a translated `CliRefusedBoundaryError`: "profile already registered;
   use `profile delete NAME` before re-importing if you intend to replace it."
   This is the idempotent re-import case — the import is a no-op rather than a
   duplicate. Operators who need a fresh copy must delete first.

2. **Label collision with different UUID:** if the bundle's display name (or the
   `--label` override) is occupied by a **different** `profile_id` locally, refuse
   with: "label already taken by a different profile; pass `--label NEW_NAME` to
   import under a distinct name."

The current label-only collision check (which permitted silent UUID minting) is
retired. The `--label` option is retained for the label-collision case only.

All domain objects in the bundle are imported under the preserved `profile_id`.
Cross-object references (work unit → profile, revision → work unit) survive intact.

## Rationale

**D1 (full bundle):** A bundle that omits financial history is not viable for
colleague handover or disaster recovery. The current facts-only export is a
known gap documented in the W75 audit grounding. The four financial-history
categories are the minimum viable set for handover; event-log history is
machine-local metadata and adds no value to the recipient.

**D2 (strip encrypted material):** The recipient cannot use wrapped DEK material
without the originator's passphrase. Carrying it expands the bundle attack surface
without benefit. Decrypted payload + re-encrypt on import is the standard pattern
for data-portability across custody boundaries; it matches the existing
`SecureObjectRepository` write path with no new primitives.

**D3 (typed throughout):** The architecture-boundaries rule and the
calculation-grounding rule jointly forbid `dict[str, Any]` intermediates and
provenance erasure. Using pydantic `model_dump`/`model_validate` satisfies both
rules with one mechanism and catches schema mismatches at import time rather than
silently dropping fields.

**D4 (versioned schema):** An unvalidated `bundle_schema_version` field is a
documentation field, not a safety gate. The import path must validate it before
parsing to prevent a newer-version bundle from being silently misread.
Version-1 backward compatibility is preserved at zero cost because the new fields
default to empty tuples.

**D5 (profile-id-first idempotency):** The current label-based check is fragile:
labels are mutable (`profile rename`), and the same operator can legitimately have
two profiles with similar labels. UUID is the stable identity. Preserving the
bundle's `profile_id` allows work units, revisions, and ledger transactions to
reference the same profile UUID after re-import without orphaned foreign keys.
Refuse-on-collision is simpler than upsert or merge and avoids write-after-read
races in the concurrent agent setting.

## Consequences

- `UserProfilePortableExport` in `src/aeat/domain/user_profile/_values.py`
  gains four optional tuple fields and bumps `bundle_schema_version` default to 2.
- The export service in `src/aeat/application/user_profile/` must query the
  `SecureObjectRepository` for all four financial-history categories and populate
  the bundle fields.
- The import service must validate `bundle_schema_version`, preserve `profile_id`,
  run the two-tier collision guard, and write each domain object via the standard
  repository save path (which re-encrypts under the new bucket's DEK).
- `src/aeat/entrypoints/cli/_config/__init__.py` import verb: the fresh-UUID-mint
  path is removed; the collision check is replaced by the two-tier guard; the
  `--label` option is retained for the label-collision recovery path.
- The `SUPPORTED_BUNDLE_SCHEMA_VERSIONS` constant must be updated whenever a new
  version is introduced; this is the only forward-compat gate.
- S107 roundtrip test must include the anti-tautology proof (D3); a test that
  passes without mutating the exported JSON is tautological and must be rejected
  at review.
- Version-1 bundles (facts-only) remain importable; they produce a profile with
  empty financial-history collections, which is the correct behaviour for a
  facts-only backup.
