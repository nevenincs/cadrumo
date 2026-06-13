---
tags:
  - '#adr'
  - '#purchase-invoice-ocr-extraction-discipline'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-30-declaracion-extraction-architecture-research]]"
  - "[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr]]"
  - "[[2026-05-28-financial-provider-extraction-discipline-adr]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - '[[2026-06-04-purchase-invoice-ocr-extraction-discipline-research]]'
---



# `purchase-invoice-ocr-extraction-discipline` adr: `ocr-evidence-extraction-discipline-for-operator-uploaded-supplier-invoices` | (**status:** `accepted`)

This ADR **supersedes** `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr`
with respect to OCR implementation contract, structured exception shape, provenance
discipline, and gate machinery. The superseded ADR surface decisions (verb set, bucket
events, `purchase_invoice_evidence` artifact kind) remain in effect; this ADR specifies
the implementation contract the superseded ADR mandated but did not specify.

## Problem Statement

The `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr` mandated that the
`aeat app ledger evidence add` verb store the source-file hash, extraction method,
extraction confidence, extracted fields, and manual-review state inside the active bucket.
The W10.P44 audit found that **zero** of these OCR-specific requirements have been
implemented: the `PurchaseInvoiceEvidence` model in `src/aeat/application/ledger/_evidence.py`
carries no `extraction_method`, no `extraction_confidence`, and no `manual_review_state`
field. There is no OCR library in `pyproject.toml`. All invoice fields are populated
exclusively by manual operator overrides.

The declaracion-extraction campaign (W10, 2026-05-28) established a discipline for
text-layer PDF surfaces -- provenance enum, provisional gate fields, structured exception
attributes -- and closed silent-failure classes on four parser surfaces. OCR for
purchase-invoice evidence introduces a structurally distinct failure class that the
text-layer discipline does not address, and operates in a different surface layer
(`application/ledger` vs `adapters.inbound`), on a different document class
(operator-uploaded supplier invoices vs AEAT-issued modelos), using a non-deterministic
extraction technology (OCR vs deterministic text-layer parsing), over an unbounded
enrollment space (any supplier vs bounded `(modelo, ano, revision)` set).

A separate ADR is warranted because these four architectural axes are each materially
different from every surface the declaracion ADR governs. This ADR ratifies the discipline
analogue for the OCR surface.

## Considerations

### Seven OCR-specific silent-failure classes

The W10.P44 research (UNIT 2) enumerated seven silent-failure classes that are distinct
from the text-layer failure class the declaracion discipline addresses:

1. **Image-quality degradation below extraction threshold.** A 150 DPI scan and a 300 DPI
   scan of the same invoice produce different Tesseract character recognition output. A
   confidently-extracted wrong value -- e.g., a curly-quote character misread into an
   amount field -- passes all `missing/malformed` gates and silently persists a wrong
   decimal. The existing four-attribute exception shape captures absence and malformation,
   not silent substitution caused by raster quality.

2. **Supplier-layout variation with the same template slot.** Two suppliers printing
   `BASE IMPONIBLE` at different XY positions cause a layout-anchored extractor to
   silently misread one. The text-layer discipline enrolls by `(modelo, ano, revision)`
   -- a registry-authoritative bounded set. There is no equivalent registry revision for
   "Proveedor Acme S.L. 2024"; the unbounded supplier space makes per-revision enrollment
   impractical.

3. **Multi-page continuation logic silently dropped.** An invoice total appearing only on
   the last page is silently absent if the OCR pipeline processes only page 1. AEAT
   declaracion PDFs have a fixed single-page structure per casilla; this failure class
   has no declaracion analogue.

4. **Thermal-paper character fading.** Partially-faded characters on petrol-station and
   point-of-sale terminals produce digit substitutions (8 to 3) without raising any
   extraction error. The corpus discipline detects this only if degraded specimens are
   collected and included in the fixture set.

5. **Non-Spanish-locale number formats.** A French supplier invoice using `1 234,56`
   (space-thousands, comma-decimal) can silently produce a wrong decimal when extracted
   by an OCR engine calibrated for Spanish convention. The `canonical_decimal` helper in
   `adapters.inbound.financial` addresses this for bank statements; it does not extend
   to OCR-extracted invoice text.

6. **OCR engine version drift.** Tesseract 4.x and Tesseract 5.x produce different
   recognition output on the same image, especially for low-contrast text. A corpus
   fixture suite that passes CI under engine version A may fail after a package update
   to version B with no source change -- the OCR analogue of "PDF layout changed between
   corpus capture and runtime".

7. **Aggregate-confidence false floor.** An OCR engine returning 85% per-character
   confidence across an entire invoice silently accepts all characters, even when the
   15% low-confidence pool clusters on exactly the amount fields. Aggregate confidence
   is not a sufficient gate; field-level confidence is required.

### Four architectural axes diverging from the declaracion discipline

The declaracion extraction discipline (`2026-05-21-declaracion-extraction-architecture-adr`,
W02 through W10) governs AEAT-issued declaracion PDFs with deterministic text-layer
parsing, a bounded `(modelo, ano, revision)` enrollment set, and a registry-profile
schema as the provenance carrier. The OCR invoice surface differs on every axis:

| Axis | Declaracion discipline | OCR invoice discipline |
|---|---|---|
| Surface layer | `adapters.inbound.declaracion` | `application/ledger` |
| Document class | AEAT-issued filed modelos | Operator-uploaded supplier invoices |
| Extraction technology | Deterministic text-layer PDF parsing (`pdfplumber`) | Non-deterministic OCR over raster images |
| Enrollment space | Bounded `(modelo, ano, revision)` -- registry-authoritative | Unbounded suppliers, any country, any format |

The bank-PDF discipline (`2026-05-28-financial-provider-extraction-discipline-adr`)
provides a closer structural analogue than the declaracion discipline: it enrolls by
provider class (not registry revision), uses ABC class variables (not schema fields), and
enforces provenance via a parametrized collection-time test. The OCR invoice discipline
adapts the same mechanisms with OCR-specific additions.

### Existing error hierarchy and missing structure

`src/aeat/application/ledger/_evidence.py` (W10.P44 audit state) defines:

- `PurchaseInvoiceEvidenceInputError(AeatError)` -- raised on file-path/extension
  refusals (line ~47). No structured attributes.
- `PurchaseInvoiceEvidenceNotFoundError(AeatError)` -- raised on CRUD lookup failures
  (line ~51). No structured attributes.

No OCR-specific error class exists anywhere in the codebase. The structured-attribute
pattern (`missing/malformed/ambiguous/coverage`) that `DeclaracionParseError`,
`JustificanteParseError`, `BorradorParseError`, and `BankStatementParseError` carry is
absent from the ledger evidence error surface.

### Determinism boundary

Text-layer PDF parsing through `pdfplumber` is **deterministic**: the same PDF byte
sequence always produces the same `extract_text()` output. A round-trip test that passes
today will pass after any `pdfplumber` upgrade that does not change the extractor.

OCR is **non-deterministic by class**: the same raster image may produce different text
depending on engine version, image preprocessing parameters, language model, and runtime
environment. This invalidates the core assumption that permits exact-string round-trip
tests on corpus PDFs. The discipline must substitute confidence-threshold assertion for
exact-match assertion.

## Constraints

- Must use `aeat.core.errors.AeatError` hierarchy. `InvoiceOcrExtractionError` is rooted
  at `PurchaseInvoiceEvidenceInputError(AeatError)` -- not at `PdfModeloImportError` --
  because supplier evidence is not an AEAT-issued modelo filing document. The two error
  root hierarchies are architecturally separate.
- Must use `aeat.core.config.Settings` for engine-version and confidence-threshold
  configuration. No naked `os.environ` reads; no hard-coded threshold constants outside
  `Settings`.
- Must use `aeat.core.i18n.tr()` for all user-facing OCR error messages. Structured
  exception attributes carry machine-readable tuples; human-readable strings go through
  the `tr()` facility.
- An `ErrorCode` registry entry is required for `InvoiceOcrExtractionError` in
  `src/aeat/core/errors/registry/` (pattern: `REFUSED_LEDGER_INVOICE_OCR_EXTRACTION`).
- No new top-level packages. All OCR evidence changes are within `application/ledger/`.
- No live AEAT write surfaces are touched by this discipline; this is an inbound-processing
  and evidence-persistence concern only.
- Real-behaviour tests only. No mocks, no monkeypatches, no `xfail`, no tautological
  assertions. Round-trip tests use real sanitised invoice fixtures and assert
  `confidence >= threshold`, not exact OCR-output strings.
- The decision on which OCR engine family (Tesseract-family local, cloud OCR API, or both)
  is **deferred** to the implementation phase. This ADR ratifies the discipline contract;
  the engine selection is an implementation-phase decision gated on this ADR.

## Implementation

### InvoiceCorpusSource provenance enum

A `Literal` type alias `InvoiceCorpusSource` is ratified as the provenance carrier for
the OCR invoice discipline. The four permitted values are:

- `"real_operator_invoice_sanitised"` -- real operator-supplied invoice with PII removed
  before fixture ingestion.
- `"real_supplier_corpus"` -- invoice collection from a named supplier (multi-specimen).
- `"synthetic_from_layout_family"` -- template-anchored synthetic invoice (analogous to
  `"synthetic_from_aeat_published_text"` in the bank-PDF discipline).
- `"no_corpus"` -- explicit absence of any corpus fixture; provisional by definition.

The `"real_operator_invoice_sanitised"` variant is novel relative to both
`CorpusVerificationSource` and the declaracion `verification_source` field.
AEAT-issued declaracion PDFs and bank-published statement PDFs are unambiguously public
documents; real operator invoices contain third-party PII (supplier NIF/CIF, amounts,
supplier names, addresses). Sanitisation is an explicit obligation, not an option. The
provenance enum distinguishes sanitised real specimens from synthetic templates to make
that obligation auditable.

`InvoiceCorpusSource` is placed in `src/aeat/application/ledger/_evidence.py` alongside
the existing error classes.

### InvoiceOcrExtractionError structured exception

`InvoiceOcrExtractionError` is ratified as a new `PurchaseInvoiceEvidenceInputError`
subclass. It carries **seven structured attributes**.

The first four mirror the established cross-surface pattern with identical semantics:

- `missing: tuple[str, ...] = ()` -- fields the OCR engine produced no candidate for.
- `malformed: tuple[str, ...] = ()` -- fields extracted but unparseable as target type.
- `ambiguous: tuple[str, ...] = ()` -- fields with multiple candidates; no single
  candidate could be selected.
- `coverage: Decimal | None = None` -- fraction of required fields successfully
  extracted, as a `Decimal` in `[0, 1]`.

Three OCR-specific attributes extend the base shape:

- `confidence_below_threshold: tuple[str, ...] = ()` -- fields extracted but
  with per-field confidence below `settings.ocr_confidence_threshold`. Distinct
  from `missing`: the engine produced a candidate below the confidence floor.
- `character_recognition_uncertain: tuple[str, ...] = ()` -- fields where
  per-character confidence is below threshold even when aggregate confidence passes.
  Captures the aggregate-confidence-false-floor class (failure class 7).
- `multi_page_continuation_missing: bool = False` -- `True` when a
  continuation page was expected (total absent on page 1) but subsequent pages were
  not present or not processed. Captures failure class 3.

`InvoiceOcrExtractionError` is placed in `src/aeat/application/ledger/_evidence.py` as a
sibling of the existing error classes, with an `ErrorCode` entry at
`src/aeat/core/errors/registry/` following the pattern for
`REFUSED_FINANCIAL_BANK_STATEMENT_PARSE`.

### Enrollment unit: engine-version pinning with optional per-supplier corpus

The research (UNIT 3b) evaluated three enrollment options. This ADR ratifies **Option B3
as the primary gate, with Option B1 as an optional corpus-collection mechanism**
(hybrid B3+B1).

The enrollment unit is: **OCR engine version + confidence threshold** (mandatory, from
`Settings`) **+ optional per-supplier corpus** (voluntary, from a fixtures directory).

Engine version is pinned via `Settings.ocr_engine_version`. When the pinned
version differs from the installed version, the discrepancy is surfaced as an
`ambiguous` attribute on affected fields and logged at WARNING level via
`aeat.core.logging` -- a hard failure is not appropriate because a package
upgrade may improve recognition.

### Gate machinery

Three complementary gates:

**Gate 1 -- `provisional_pending_invoice_corpus` flag.** OCR handlers that have not
collected sanitised invoice corpus fixtures must carry
`provisional_pending_invoice_corpus: ClassVar[bool] = True`. Setting this to
`False` without a corresponding corpus fixture directory fails the collection-time
test `test_ocr_handler_declares_corpus_posture`. This is the OCR analogue of
`provisional_pending_specimen` on `ExtractionProfileDefinition`.

**Gate 2 -- engine-version pinning.** Active OCR engine version is read from
`Settings.ocr_engine_version`. Any extraction invocation where the installed
version differs from the pinned version populates `ambiguous` on affected fields
and logs a structured warning.

**Gate 3 -- per-field confidence threshold.** Extraction results where any required
field confidence falls below `Settings.ocr_confidence_threshold` raise
`InvoiceOcrExtractionError` with the low-confidence field names in
`confidence_below_threshold`.

**Invariant test: `test_ocr_handler_no_corpus_implies_provisional`.** Any
registered OCR handler with `invoice_corpus_source = "no_corpus"` must have
`provisional_pending_invoice_corpus = True`. Mirrors
`test_provider_no_corpus_implies_provisional` from the bank-PDF discipline.

### Model fields mandated by the superseded ADR

The following fields, mandated by
`2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr` but absent
from the current `PurchaseInvoiceEvidence` model, are ratified as the first
implementation obligation:

- `extraction_method: Literal["ocr", "manual"] | None = None`
- `extraction_confidence: Decimal | None = None`
- `manual_review_state: Literal["pending", "reviewed", "accepted", "rejected"] | None = None`

These fields are added to `PurchaseInvoiceEvidence` in
`src/aeat/application/ledger/_evidence.py` as the first implementation step,
before any OCR pipeline is wired.

### Corpus collection discipline

Invoice corpus fixtures reside at `tests/fixtures/invoices/<supplier_id>/`.
For operators who contribute real invoices: the sanitiser removes supplier NIF/CIF,
operator NIF, all amounts (replaced with round synthetic values), and any personally
identifying reference numbers before fixture ingestion. Sanitised fixtures are tagged
`"real_operator_invoice_sanitised"`. Synthetic fixtures generated from layout
families are tagged `"synthetic_from_layout_family"`.

Corpus fixture round-trip tests assert:
- `confidence >= settings.ocr_confidence_threshold` for each required invoice field.
- Extracted amounts parse as `Decimal` within `Decimal("0.01")` of the
  ground-truth synthetic value.
- No `missing` fields for required fields (`taxable_base`, `iva_rate`,
  `iva_amount`, `invoice_date`).
- `multi_page_continuation_missing` is `False`.

Tests do **not** assert exact OCR output strings. The non-determinism boundary means
an exact-string assertion is a brittle tautology against the current engine version.

## Rationale

The declaracion discipline three-mechanism model (provenance enum + gate fields +
structured exception attributes) is the correct pattern. The W10 campaign confirmed
it across four text-layer surfaces; the research (UNIT 3) validated it as transferable
to the OCR surface with structural adaptation.

A separate ADR is preferred over amending the declaracion ADR because:

- The surface is `application/ledger`, not `adapters.inbound` -- placing OCR discipline in the declaracion ADR scope would misstate the architecture.
- The enrollment mechanism (engine-version + confidence threshold, not
  `(modelo, ano, revision)`) requires different gate machinery.
- The determinism boundary is categorically different: the declaracion ADR
  corpus_round_trip_verified = true semantics (the author confirmed extraction
  works end-to-end) cannot carry the same guarantee for non-deterministic OCR.
- The superseded ADR established the surface; this ADR provides the implementation
  contract it mandated. The relationship is precursor -> implementation-specification,
  not amendment.

The bank-PDF discipline provides the closer structural template: provider-level
provenance declaration, ABC class variables as the provenance carrier, collection-time
parametrized tests as the enforcement gate, and
`BankStatementParseError` `missing/malformed/ambiguous/coverage` as the structured exception shape. The OCR discipline extends this pattern with the
three OCR-specific attributes and the confidence-threshold gate.

Rooting `InvoiceOcrExtractionError` at
`PurchaseInvoiceEvidenceInputError(AeatError)` rather than at
`PdfModeloImportError` is the correct taxonomy decision. Supplier invoice evidence
is not an AEAT-issued modelo filing artifact; conflating the two error hierarchies
would misrepresent the domain boundary between AEAT filing documents and
operator-managed evidence.

## Consequences

- **Supersession.** `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr` is superseded by this ADR with respect to OCR implementation contract, structured
  exception shape, provenance discipline, and gate machinery. Its surface decisions
  (CRUD verb set, bucket events, `purchase_invoice_evidence` artifact kind) remain
  authoritative and are not modified by this ADR.
- **First implementation obligation.** `PurchaseInvoiceEvidence` must be extended
  with `extraction_method`, `extraction_confidence`, and `manual_review_state` before any OCR pipeline is wired. This satisfies the 2026-05-12 mandate outstanding
  since that ADR was accepted.
- **`InvoiceOcrExtractionError` is the mandatory exception class** for all OCR
  extraction failure paths. Callers inspect the seven structured attributes; no
  message-string parsing is permitted.
- **Every registered OCR handler must declare** `invoice_corpus_source` and
  `provisional_pending_invoice_corpus`. Omitting either fails the collection-time
  structural test. A handler with `no_corpus` must set
  `provisional_pending_invoice_corpus = True`.
- **`Settings` is the sole configuration boundary** for `ocr_engine_version` and
  `ocr_confidence_threshold`. Any naked `os.environ` read violates the standing mandate.
- **`tr()` is mandatory** for all user-facing OCR error messages.
- **OCR engine selection is deferred.** This ADR does not mandate Tesseract, a cloud
  OCR API, or any specific engine. The discipline is engine-agnostic.
- **Round-trip tests must not assert exact OCR strings.** Confidence-threshold
  assertion replaces exact-match as the corpus quality signal.
- **Corpus sanitisation is an explicit obligation.** Real operator invoices carry
  third-party PII and must be sanitised before fixture ingestion. The
  `real_operator_invoice_sanitised` provenance tag makes this auditable;
  un-sanitised real invoices must not appear in corpus directories.

## Enrollment pattern for future OCR handlers

Adding a new OCR engine or layout-family extractor requires:

1. A module implementing the OCR handler under `application/ledger/`.
2. Three mandatory `ClassVar` declarations:
   `invoice_corpus_source: ClassVar[InvoiceCorpusSource]`,
   `provisional_pending_invoice_corpus: ClassVar[bool]`,
   `ocr_engine_family: ClassVar[str]` (e.g., `"tesseract"`, `"cloud_vision"`).
3. If no corpus fixtures: `invoice_corpus_source = "no_corpus"`, `provisional_pending_invoice_corpus = True`.
4. When corpus fixtures are acquired: set appropriate `invoice_corpus_source` and
   `provisional_pending_invoice_corpus = False`.
5. Corpus fixtures at `tests/fixtures/invoices/<handler_id>/` with sanitised PDF or
   image files and ground-truth sidecar JSON.
6. A parametrized round-trip test asserting confidence-threshold compliance for all
   required fields across all corpus fixtures.
7. An `ErrorCode` registry entry for any new exception types.
