---
step_id: S04
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W01.P02.S04-S12 — migrate BucketId consumers to core.identity

## Scope

Nine Steps closed in one execution session: S04-S12 switch every
production consumer of `BucketId` from `aeat.domain.modelos._ids` to
`aeat.core.identity` per identity-primitives ADR Rule 2. The old
declaration in `domain.modelos._ids` stays in place at the close of
this Phase; it is deleted in W01.P03.S13.

## Outcome

### S04 — domain.transactions._repository
Repository module imports `BucketId` from `aeat.core.identity` instead
of `..modelos._ids`. Domain.transactions no longer crosses
domain.transactions -> domain.modelos for a typed identity primitive.

### S05 — domain.transactions._models
Models module imports `BucketId` from `aeat.core.identity`; the
`TransactionId` import is retained from `..modelos._ids` (its home until
a later ADR moves it).

### S06 — domain.invoices._models
Invoices models module imports `BucketId` consolidated with the
existing `aeat.core.identity` import for `validate_spanish_tax_id`.

### S07 — domain.attachments._models
Attachments models import `BucketId` from `aeat.core.identity`.

### S08 — adapters.persistence.storage.bucket._layout
The bucket layout module imports `BucketId` from `aeat.core.identity`,
closing the persistence adapter's reach into `domain.modelos` for a
storage-boundary identity.

### S09 — adapters.persistence.storage.bucket._export_header
Export-header module imports `BucketId` from `aeat.core.identity`.

### S10 — entrypoints.cli._review_payloads
Review payloads import `BucketId` from `aeat.core.identity`.

### S11 — entrypoints.cli._modelo_payloads
Modelo payloads import `BucketId` from `aeat.core.identity`; the
modelo-record aliases (`WorkUnitId`, `CalculationRevisionId`,
`FilingRecordId`) keep their `domain.modelos._ids` home.

### S12 — application-layer sweep
Nineteen application modules (auth, aggregation, evidence, ledger
(`_business_operation_invoice`, `_evidence`, `_models`, `_preflight`,
`_ratios`), live (`_borrador_100`, `_censo`, `_expedientes`,
`_notifications`, `_verify`), modelo (`_borrador_binding`, `_export`,
`_history`, `_reconcile`), review, setup, workflow) switched to
`aeat.core.identity`. Other modelo-record aliases that appeared in the
same import line are split off to keep their `domain.modelos._ids`
home.

## Verification

Per-Step pytest scopes ran sequentially and reported pass:
- `pytest src/aeat/domain/transactions/` — 81 passed (S04, S05)
- `pytest src/aeat/domain/invoices/` — 120 passed (S06)
- `pytest src/aeat/domain/attachments/` — 2 passed, 1 pre-existing
  failure (`test_blob_and_manifest_round_trip_without_plaintext_files`)
  unrelated to BucketId surface (peer storage-encryption regression).
- `pytest src/aeat/adapters/persistence/storage/bucket/` — 89 passed
  (S08, S09)
- Import smoke for `_review_payloads.ReviewQueueRowPayload` and
  `_modelo_payloads.WorkUnitPayload` resolves (S10, S11)
- `pytest src/aeat/application/` — 189 passed before halting on one
  pre-existing `aeat-i18n` regression in
  `aggregation.test_retenciones.TestAggregate111.test_unregistered_modelo_raises_domain_error`
  unrelated to BucketId surface; the assertion is on a translated error
  message, not a typed-id boundary.

## Commits

- `294bf5456` — S04 (transactions repository)
- `372271629` — S05 (transactions models)
- `f5e6bdc8f` — S06 (invoices models)
- `9c1a7041e` — S07 (attachments models)
- `efcca325c` — S08 (bucket layout)
- `8fb255a5b` — S09 (bucket export header)
- `886fd3695` — S10 (CLI review payloads)
- `9185b304c` — S11 (CLI modelo payloads)
- `1f7f8ddc8` — S12 (application-layer sweep)
