---
tags:
  - '#plan'
  - '#ledger-evidence-enforcement'
date: '2026-06-10'
modified: '2026-06-10'
tier: L2
related:
  - '[[2026-06-10-ledger-evidence-enforcement-adr]]'
  - '[[2026-06-10-ledger-evidence-enforcement-research]]'
---


# `ledger-evidence-enforcement` `Encrypted evidence bytes and advisory evidence gate` plan

### Phase `P01` - Delete add_link_attachment; rewire doclink to fetch-and-encrypt

Remove the URI-only attachment path, wire the doclink CLI verb to resolve_document_link then add_attachment, and refuse when bytes cannot be fetched.

- [x] `P01.S01` - Delete add_link_attachment from attachment service and remove its __all__ export; `src/aeat/domain/attachments/_service.py`.
- [x] `P01.S02` - Remove AttachmentKind.EMAIL_MESSAGE, AttachmentKind.DRIVE_DOCUMENT, AttachmentKind.OTHER doclink-only mappings from ledger_doclink if they are link-only artefacts; `confirm enum members still needed by byte-bearing paths are retained; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `P01.S03` - Rewire ledger_doclink to call resolve_document_link to obtain bytes, then add_attachment to store them under ATTACHMENT_BLOB_NAMESPACE and ATTACHMENT_MANIFEST_NAMESPACE with real sha256 and mime_type; `record original source and source_reference as manifest metadata; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `P01.S04` - Surface OutboundStoragePermissionError as an actionable CLI refusal message naming the scope-upgrade or manual-download path; `do not fall back to link storage on any error; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.
- [x] `P01.S05` - Remove the DocumentLinkSource-to-AttachmentKind mapping dict and any remaining add_link_attachment import in ledger_doclink; `confirm attach_manual_transaction_evidence call site unchanged to preserve C7 audit cross-referencing; `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`.

### Phase `P02` - Advisory evidence-presence gate on the verify path

Introduce a non-blocking ADVISORY finding on verify_modelo_revision for positive OUTGOING business expense or cuota-bearing INCOMING income rows with zero linked evidence.

- [x] `P02.S06` - Implement _missing_evidence_advisory_observations function that accepts a list of transactions and returns CalculationSourceDiagnostic entries for positive-amount ACTIVE OUTGOING business/mixed-expense rows with deductible IVA category and no purchase_invoice_evidence_id or attachment_ids; `src/aeat/application/aggregation/_evidence_advisory.py`.
- [x] `P02.S07` - Extend _missing_evidence_advisory_observations to cover positive-amount ACTIVE INCOMING rows whose IvaCategory is not in CUOTA_LESS_M303_IVA_CATEGORIES and which carry no attachment_ids; `add the CUOTA_LESS_M303_IVA_CATEGORIES exclusion import from aeat.domain.iva; `src/aeat/application/aggregation/_evidence_advisory.py`.
- [x] `P02.S08` - Integrate _missing_evidence_advisory_observations into verify_modelo_revision by calling it against the revision's source transactions and appending the resulting CalculationSourceDiagnostic entries as ADVISORY ModeloVerificationFinding rows; `src/aeat/application/modelo/_verification_actions.py`.
- [x] `P02.S09` - Add CalculationSourceDiagnosticReason literal entry MISSING_TRANSACTION_EVIDENCE to the reason Literal in _source_mesh.py; `cite legal_refs for the deductible-expense advisory finding; `src/aeat/application/aggregation/_source_mesh.py`.
- [x] `P02.S10` - Export _missing_evidence_advisory_observations from aeat.application.aggregation __init__ __all__ surface so the verify action can import it via the package boundary; `src/aeat/application/aggregation/__init__.py`.

### Phase `P03` - Secure-storage regression gate and roundtrip tests

Assert no text/uri-list manifest can be written; add a real-adapter fetch-and-encrypt roundtrip with anti-tautology blob-mutation proof; add the advisory-gate test with false-positive guard.

- [x] `P03.S11` - Add secure-storage regression test asserting no attachment manifest with mime_type text/uri-list can be written through the AttachmentStore; `use real SQLite-backed SecureObjectRepository and real AttachmentStore; `src/aeat/domain/attachments/tests/test_attachment_store_no_uri_list.py`.
- [x] `P03.S12` - Add fetch-and-encrypt roundtrip test: stub only the Drive transport seam (service.files().get_media), drive resolve_document_link then add_attachment against a real AttachmentStore over real SQLite, load the manifest back and assert stored bytes equal fetched bytes and manifest sha256/mime_type match; `src/aeat/adapters/outbound/google/tests/test_document_link_resolve_roundtrip.py`.
- [x] `P03.S13` - Add anti-tautology blob-mutation test within the same roundtrip module: mutate the on-disk blob payload after a successful store, reload, and assert the re-hash verification raises rather than returning the mutated content; `src/aeat/adapters/outbound/google/tests/test_document_link_resolve_roundtrip.py`.
- [x] `P03.S14` - Add refusal test asserting that a Gmail reference and a URL reference each raise OutboundStoragePermissionError and write nothing to the attachment store; `src/aeat/adapters/outbound/google/tests/test_document_link_resolve_roundtrip.py`.
- [x] `P03.S15` - Add advisory-gate test: build a positive OUTGOING BusinessClassification.BUSINESS_EXPENSE ACTIVE transaction with deductible IVA category and no evidence, run verify path, assert exactly one ADVISORY MISSING_TRANSACTION_EVIDENCE finding; `run same with attachment_ids populated, assert no such finding; `src/aeat/application/aggregation/tests/test_evidence_advisory.py`.
- [x] `P03.S16` - Add false-positive guard test: build an exempt IvaCategory OUTGOING row (member of CUOTA_LESS_M303_IVA_CATEGORIES) with no evidence, build a PERSONAL non-business OUTGOING row with no evidence, build a zero-amount row with no evidence, and assert each produces no ADVISORY evidence-presence finding; `src/aeat/application/aggregation/tests/test_evidence_advisory.py`.

### Phase `P04` - API-docs scaffold, locale drift check, and docs deliverable flag

Regenerate API-reference stubs after symbol deletion; confirm locale parity; flag the how-to docs rewrite as a separate vaultspec-documentation deliverable.

- [x] `P04.S17` - Run python -m dev.docs.apidocs scaffold to regenerate API-reference stubs after add_link_attachment deletion; `confirm scaffold --check exits clean; `docs/api/`.
- [x] `P04.S18` - Run python -m aeat.locales scaffold --check to confirm locale parity after any new translation keys added for the refusal message in ledger_doclink; `src/aeat/locales/`.
- [x] `P04.S19` - Flag docs/how-to/ledger-evidence.md and docs/how-to/import-bank-statements.md as separate user-facing documentation deliverables that must be authored through the vaultspec-documentation workflow; `do not edit those files in this plan; `docs/how-to/`.

## Description

This plan closes the C2 cluster of the ledger-evidence campaign, as specified in
the sibling ADR `2026-06-10-ledger-evidence-enforcement-adr` and grounded in
the sibling research `2026-06-10-ledger-evidence-enforcement-research`.

Two structural gaps remain after the campaign's discovery pass. First, the
`add_link_attachment` path in `src/aeat/domain/attachments/_service.py` stores
a Gmail/Drive/URL reference string as the attachment payload (`mime_type =
"text/uri-list"`) and never fetches the remote document, violating the campaign
binding invariant that every evidence record must carry encrypted bytes in the
per-profile bucket-scoped secure-object store. Second, nothing ties a
transaction's evidence presence to its economic role, allowing a positive-amount
business expense or cuota-bearing income row to file silently with no evidence
and no operator alert.

P01 removes `add_link_attachment` outright (`no-legacy-compatibility`) and
rewires the `aeat app ledger doclink` CLI verb to call the already-landed
`resolve_document_link` (`src/aeat/adapters/outbound/google/_document_link_resolver.py`)
to fetch document bytes, then store them through the existing byte-bearing
`add_attachment` path, keeping the original link reference as manifest metadata.
When `resolve_document_link` raises (Gmail link, out-of-scope Drive file, or
URL), the verb refuses with an actionable message naming the scope-upgrade or
manual-download path; it never falls back to storing a link.

P02 introduces a non-blocking ADVISORY finding on `verify_modelo_revision` for
the triggering set: positive-amount `ACTIVE` `OUTGOING` `BUSINESS_EXPENSE` or
`MIXED` rows with deductible IVA category and no linked evidence, and
positive-amount `ACTIVE` `INCOMING` rows whose `IvaCategory` is not in
`CUOTA_LESS_M303_IVA_CATEGORIES` and which carry no `attachment_ids`. The gate
uses the established `CalculationSourceDiagnostic` / `ADVISORY`
`ModeloVerificationFinding` surface (`no-silent-under-declaration`). Exempt,
zero-rated, not-subject, non-business, zero-amount, and non-ACTIVE rows are
excluded.

P03 delivers the test obligations: a secure-storage regression gate asserting
no `text/uri-list` manifest can be written; a real-adapter fetch-and-encrypt
roundtrip (transport seam only mocked) with an anti-tautology blob-mutation
proof; a refusal test for Gmail and URL references; an advisory-gate test
with an evidence-present counter-case; and an explicit false-positive guard for
cuota-less, non-business, and zero-amount rows.

P04 regenerates API-reference stubs after the symbol deletion, confirms locale
parity, and flags the `docs/how-to/ledger-evidence.md` and
`docs/how-to/import-bank-statements.md` rewrites as separate deliverables that
must ride the `vaultspec-documentation` workflow.

## Parallelization

P01 and P02 have no shared file dependency and may be executed in parallel by
two agents. P03 must follow P01 (the roundtrip and regression tests require the
rewired path) and P02 (the advisory-gate tests require the new advisory
function). P04 must follow P01 (the scaffold run requires `add_link_attachment`
to be absent). P04.S18 and P04.S19 have no dependency on each other and may
run in parallel once P01 is closed.

## Verification

- `uv run --no-sync pytest src/aeat/domain/attachments/ -q --tb=short` collects
  and passes with no failures, including P03.S11.
- `uv run --no-sync pytest src/aeat/adapters/outbound/google/ -q --tb=short`
  collects and passes including P03.S12, S13, S14.
- `uv run --no-sync pytest src/aeat/application/aggregation/ -q --tb=short`
  collects and passes including P03.S15, S16.
- `uv run --no-sync pytest --collect-only -q` exits clean with no collection
  errors.
- `python -m dev.docs.apidocs scaffold --check` exits clean (no drift).
- `python -m aeat.locales scaffold --check` exits clean (no locale drift).
- No `text/uri-list` mime_type appears in any attachment manifest written by any
  code path (`grep -r "uri-list" src/aeat/` returns nothing in production code).
- `add_link_attachment` does not appear in `src/aeat/` outside test files that
  assert its absence.
- `docs/how-to/ledger-evidence.md` and `docs/how-to/import-bank-statements.md`
  are unchanged by this plan (they are flagged as a separate deliverable at
  P04.S19).
