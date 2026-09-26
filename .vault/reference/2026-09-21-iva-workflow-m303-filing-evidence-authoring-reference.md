---
tags:
  - '#reference'
  - '#iva-workflow'
date: '2026-09-21'
modified: '2026-09-21'
body_schema: 'body-v2'
body_hash: 'sha256:b6dac7c92c8c40e3f8f21aff9fec7f15f3339d46c553c13efa9b97d6b574cda7'
related:
  - "[[2026-09-21-iva-workflow-reference]]"
---
# `iva-workflow` reference: `M303 filing evidence production authoring map`

## Summary

This reference records the production ownership and missing authoring boundary
for the typed Modelo 303 filing-instance evidence consumed by calculation. It
is grounded in the installed CLI, domain models, application validation and
encrypted calculation-revision persistence as inspected on 2026-09-21.

## Typed envelope

`FilingInstanceEvidence` contains one M303 value
(`src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py:474`). The
M303 value records the period, joint-return election, annual-volume flag,
optional insolvency classification, Modelo 390 exemption evidence and simplified
regime evidence (`src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py:441`).

The exemption branch carries applicability, endpoint casillas and values,
ordered activity rows and the Modelo 347 decision
(`src/cadrumo/domain/modelos/calculation_revision_m303_evidence.py:42`). The
simplified-regime branch binds filing rows, an immutable authority snapshot,
optional DANA eligibility and the calculated result
(`src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py:329`). Its
scope, year, coordinates, ordering and evidence references are cross-validated
(`src/cadrumo/domain/modelos/calculation_revision_m303_handoff.py:340`).

## Current production flow

The installed CLI accepts a plaintext JSON path and validates it directly with
`FilingInstanceEvidence.model_validate_json`; it does not construct the value
(`src/cadrumo/entrypoints/cli/_m303_filing_evidence_input.py:17`). Calculation
then validates period, profile scope, authority snapshot, rows, calculated
result and exemption observations
(`src/cadrumo/application/modelo/m303_filing_evidence.py:55`). The validated
envelope is stored inside `CalculationRevision.filing_instance_evidence`
(`src/cadrumo/domain/modelos/calculation_revision.py:847`) and participates in
revision identity
(`src/cadrumo/domain/modelos/calculation_revision_identity.py:310`). Its
catalogue is encrypted by the existing calculation-revision repository
(`src/cadrumo/adapters/persistence/profile/modelos_calculation.py:78`).

No production constructor for the complete envelope exists. The complete
builder is test-only and consumes test authority fixtures
(`src/cadrumo/application/calculations/tests/filing_evidence.py:41`). Therefore
the missing installed journey is not only command registration.

## Fact ownership

- The bundled authority owns the record design, annual Orden, coefficients,
  scope vocabulary and DANA availability
  (`src/cadrumo/application/calculations/m303_orden_resolution.py:26`).
- The secure IVA profile owns simplified-regime scope
  (`src/cadrumo/application/modelo/m303_regimen_simplificado_scope.py:71`).
- Existing application calculation owns the simplified result from filing rows
  and the authority snapshot
  (`src/cadrumo/application/calculations/m303_regimen_simplificado.py:41`).
- Existing filing-evidence validation owns equality between exemption endpoint
  evidence and calculated observations
  (`src/cadrumo/application/modelo/m303_filing_evidence.py:131`).
- The operator is the only current source for joint-return election,
  annual-volume fact, insolvency date and subtype, exemption elections and
  activity facts, Modelo 347 decision, simplified activity/module quantities
  and claimed DANA eligibility.

The operator fields do not carry source identity. Evidence references are
nominal strings and are not resolved against secure invoice, ledger, attachment
or profile repositories (`src/cadrumo/domain/filing_evidence.py:8`). Insolvency
records have no evidence reference at all
(`src/cadrumo/domain/modelos/calculation_revision_m303_evidence.py:26`). Export
copies these values but does not establish their origin
(`src/cadrumo/application/filing/producer_snapshot.py:931`).

## Smallest production gap

A secure post-calculation owner already exists, but no pre-calculation
application operation composes the envelope from authoritative facts and
evidence-backed operator assertions. Treating a hand-authored complete JSON
envelope as production truth would let the caller override derived facts and
would leave nominal or absent evidence identities unresolved.

Ordinary 2025 Modelo 303 authoring can be separated from optional regimes. The
ordinary path still needs a typed transient request for genuine elections and
assertions, authoritative derivation of all other fields, secure reference
resolution where an assertion requires evidence, and direct handoff of the
validated envelope to existing calculation-revision persistence. Optional
insolvency, exemption and simplified-regime branches must refuse until each
branch's full grounding contract is available.
## Existing secure custody fit

The closest reusable production owner is the encrypted attachment store. An
`Attachment` already records immutable digest and identity, kind, source,
capture time, bucket, links and custody actor/command
(`src/cadrumo/domain/attachments/models.py:136`). The attachment adapter verifies
the encrypted manifest, digest, content and bucket when loading
(`src/cadrumo/adapters/persistence/storage/attachment.py:410`).

Purchase-invoice evidence adds invoice metadata but has no filing semantic role
(`src/cadrumo/application/ledger/evidence.py:112`). `EvidenceBundle` packages
audit records after the fact and likewise has no applicability role
(`src/cadrumo/application/evidence/models.py:141`). Neither is the correct owner
for a Modelo 390 non-applicability assertion.

The attachment record lacks the dimensions required for filing-evidence
resolution: a closed semantic role, filing year and period, and observation
validity. Its bucket is the existing secure profile scope; the resolver must
match that bucket rather than duplicate taxpayer identity in another store.
`captured_at` remains custody time and cannot substitute for observation
validity. New metadata requires the attachment manifest's normal schema-version
migration; an arbitrary `METADATA_BLOB` kind or purchase-evidence identifier does
not establish the missing semantics.
## Profile freshness witness

M303 scope uses the authenticated current `UserProfileRecord`
(`src/cadrumo/application/modelo/m303_regimen_simplificado_scope.py:40`). The
existing stable witness is its `profile_id`, monotonic `record_revision`,
canonical `content_digest`, `schema_id` and `schema_version`
(`src/cadrumo/domain/user_profile/values.py:319`). The secure row provenance
cross-binds those values to the profile UUID and custody envelope
(`src/cadrumo/application/user_profile/capsule_record.py:198`).

No IVA-only persisted digest exists. A filing attestation can therefore bind to
that existing tuple without creating another identity. This is conservative:
any profile revision makes the prior attestation stale, even when unrelated to
IVA, and requires a new attestation. The current M303 scope resolver remains the
only interpreter of the profile facts.
