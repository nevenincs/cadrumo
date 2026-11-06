---
tags:
  - '#reference'
  - '#source-casilla-integration'
date: '2026-11-06'
modified: '2026-11-06'
body_schema: 'body-v2'
body_hash: 'sha256:41dad11b58b0989904d9cbdcc390fc74150dbd7cb54d27ed9d83a9f26c22c091'
related: []
---

# `source-casilla-integration` reference: `Profile provenance node fingerprint`

How the calculation path fingerprints the loaded profile record for a profile-sourced provenance node, where that fingerprint goes, who reads it, and how persisted revisions re-derive their identity. Read at tui `becf526c9f` on 2026-11-06.

## Summary

### What is hashed

- `src/cadrumo/application/modelo/profile_binding.py:139-144`: `_profile_record_fingerprint` digests `model_dump_json()` of the whole loaded profile record. The digest covers every stored fact, plus the record's own bookkeeping: `updated_at`, `record_revision`, `previous_record_digest`, `content_digest` and `setup_state`. These come from the record model in the user-profile domain. A save that changes no fact still changes the digest.
- `src/cadrumo/application/aggregation/atribucion_member.py:120` and `:457` repeat the pattern for the atribucion member source. That fingerprint is emitted only when the projection is complete.

### Where it flows

- The fingerprint becomes `CalculationSourceRef.fingerprint` on the profile node. Every provenance axis, fingerprint included, enters the content-addressed revision ID through `src/cadrumo/domain/modelos/calculation_revision_identity.py:348-375`, as `_source_provenance_revision_id_payload` feeding `derive_calculation_revision_id_from_identity_inputs` at `:470` and `:546`.
- The same value reaches tier evidence references in `src/cadrumo/application/modelo/calculation_resolution.py` and the calculation report digest.

### Who reads it

- No consumer compares a stored profile fingerprint against the live profile.
- Calculation staleness is screen-based.
- Draft approval uses its own profile activity fingerprint, in `src/cadrumo/application/filing/draft_review.py`.
- The cross-period clean-state gate does not read it.
- Header and contact export facts are read live at export, not from calculation provenance.

### Observable cost

- A recalculation after an unrelated profile edit, or after a bare save, derives a new revision ID. The persistence step at `src/cadrumo/application/modelo/revision_persistence.py:636-662` therefore mints a new BORRADOR instead of publishing the duplicate of the existing identity. The VERIFICADO state of the earlier revision is not reused, and the operator has to verify again.
- Filed revisions are unaffected because they are immutable.

The behaviour is pinned by `src/cadrumo/entrypoints/tests/profile_persistence/test_modelo_720_profile_contact.py:345-358`. Two calculations whose contact values match but whose `identity.email` differs, a fact no 720 binding consumes, must have different revision IDs and different profile fingerprints. The test came from step S04 of `2026-11-06-modelo-profile-bindings-plan`, which says to preserve profile-tier fingerprint provenance.

### Breadth

- About 65 `kind = profile` binding providers across Modelos 036, 100 (53), 130, 200, 202, 210, 303 and 720.
- Profile row bindings.
- The atribucion member source.

### Re-derivation of persisted identity

- Stored revisions are re-checked against their content address:
  - in the model validator at `src/cadrumo/domain/modelos/calculation_revision.py:651`;
  - on read at `src/cadrumo/application/modelo/registry_helpers.py:638`;
  - by the historical filing projection at `src/cadrumo/application/modelo/historical_filing_projection.py:193`;
  - in the override migration at `src/cadrumo/adapters/persistence/profile/calculation_revision_override_migration.py:303`.
- Each check hashes the persisted provenance, including the stored fingerprint string. None recomputes a fingerprint from a profile. A change to how new fingerprints are computed therefore leaves every persisted revision's ID derivable and unchanged.
- `calculation_revision_identity.py:355-358` already relies on the same property for rows persisted before `source_filing_year` existed.

### Governing records

- `2026-08-22-source-casilla-integration-adr` (accepted) defines `fingerprint` as the content identity of a provenance node. A node is per binding, but the record does not say which content a profile node carries.
- `2026-07-26-evidence-revision-identity-adr` (accepted) keeps an evidence gap out of revision identity, so that a re-run of unchanged inputs keeps its revision.
- `2026-07-24-evidence-revision-identity-adr` (accepted) records that a change to the content-address derivation needs operator sign-off.
