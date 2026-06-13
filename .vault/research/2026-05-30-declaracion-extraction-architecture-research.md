---
tags:
  - '#research'
  - '#declaracion-extraction-architecture'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-research]]"
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-30-purchase-invoice-ocr-extraction-discipline-adr]]"
---



# `declaracion-extraction-architecture` research: `ocr-evidence-extraction-discipline`

Research closure for `W10.P44.S201`. The declaration-extraction campaign reached
structural mission-complete (45+ verified chain proof points; discipline parity
across four PDF parser surfaces). This research documents the OCR/evidence path
deferred per the W02 ADR — auditing the current state, defining the OCR-specific
silent-failure class, and proposing the discipline analogue as the durable input
for a follow-up campaign.

## UNIT 1 — Audit of the existing OCR path

### What is implemented today

The entry-point for purchase-invoice evidence is `PurchaseInvoiceEvidenceService`
in `src/aeat/application/ledger/_evidence.py`. The service exposes five CRUD verbs
(`add`, `remove`, `update`, `view`, `list`) over a `PurchaseInvoiceEvidence` pydantic
record. The `add` verb:

1. Resolves the supplied `source_path` and determines `media_kind` —
   `"pdf"` or `"image"` — via `_resolve_media_kind` (line 94).
2. SHA-256-hashes the file via `_hash_file` (line 107).
3. Persists a `PurchaseInvoiceEvidence` record to a per-bucket JSONL file.
4. Emits a `BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED` event.

The `media_kind` field accepts `"image"` extensions: `.png`, `.jpg`, `.jpeg`,
`.tif`, `.tiff`, `.webp`, `.heic`, `.heif` (line 42).

**The OCR path does not exist.** Despite the module docstring describing the
scope as "PDF and image inputs handled by the OCR path", there is no OCR,
no text extraction, no field detection, no confidence score, no extraction
method field, and no manual-review-state field on the persisted record.
The structured invoice fields (`supplier`, `invoice_number`, `invoice_date`,
`taxable_base`, `iva_rate`, `iva_amount`) are all `Optional` and are populated
exclusively by manual operator-supplied overrides passed through the CLI.
There is no `extraction_confidence`, no `extracted_by`, and no
`provisional_pending_specimen` equivalent on the model.

### What "OCR path" means here

The `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr` (accepted,
amended 2026-05-14) mandated:

> Store the source file hash, **extraction method, extraction confidence,
> extracted fields, manual-review state**, and transaction link inside the
> active bucket.

The amendment (P0 audit finding #4) locked the construction verb as
`aeat app ledger evidence add` with:

> The verb's `--format json` payload MUST surface the **OCR confidence and
> manual-review state** already specified by this ADR's implementation section.

None of these fields are present in the current `PurchaseInvoiceEvidence` model or
service. The OCR pipeline, extraction-method field, extraction-confidence score,
and manual-review-state field are **documented-intent without implementation**.

### Existing error classes

`src/aeat/application/ledger/_evidence.py` defines:

- `PurchaseInvoiceEvidenceInputError(AeatError)` — raised when a CLI-supplied
  path violates the typed contract (missing file, unsupported extension).
- `PurchaseInvoiceEvidenceNotFoundError(AeatError)` — raised when a lookup
  targets a missing evidence record.

Neither class carries structured attributes. There are no OCR-specific failure
classes anywhere in the codebase. No `tesseract`, `pytesseract`, `easyocr`,
`pix2text`, `pillow`, `pdf2image`, or equivalent library is in `pyproject.toml`.

### Test posture

`src/aeat/application/ledger/test_evidence.py` tests the CRUD service with a
minimal real `.pdf` file created by `p.write_bytes(b"%PDF-1.4 test")`. All
tests exercise event emission and CRUD mechanics. None test OCR extraction,
image-to-text conversion, field detection, or confidence thresholds — because
none of those capabilities exist.

### Artifact kind and surface name

The artifact kind is `"purchase_invoice_evidence"`, the surface is the
application-layer ledger service, not an inbound adapter. The `media_kind`
field is `"pdf" | "image"`. There is no adapter surface analogous to
`adapters.inbound.declaracion` or `adapters.inbound.justificante` for
invoice evidence — the `application/ledger/` layer is the only consumer.

### Summary verdict

OCR extraction for purchase-invoice evidence is **entirely unimplemented**.
The scope is limited to file ingestion (hash + persist) with optional
manual field overrides. The W70 ADR that mandated OCR confidence and
extraction-method tracking was not implemented. The current codebase has no
OCR dependencies and no OCR infrastructure.

---

## UNIT 2 — Silent-failure class for OCR-based invoice extraction

When OCR extraction is implemented, it will inherit a structurally distinct
failure class from every text-layer PDF surface. The declaración/justificante
discipline closes silent failures on text-layer PDFs; OCR introduces seven
additional failure classes that the existing discipline does not address.

### Failure class 1 — Image quality silently degrades below extraction threshold

A supplier invoice scanned at 150 DPI is structurally different from one
scanned at 300 DPI. The same Tesseract invocation silently produces different
character recognition on each. The existing `missing/malformed/ambiguous/coverage`
attributes capture whether an expected field was found, but cannot capture whether
the character recognition was correct — a confidently-extracted wrong value
(e.g., `"8.456,12"` misread as `"8.456,12"` with a closing-curly-quote character)
passes the structured attribute gates and silently persists a wrong amount.

### Failure class 2 — Supplier-layout variation with the same template slot

Supplier A prints "BASE IMPONIBLE" in a fixed position, left-aligned.
Supplier B prints "BASE IVA" at the same Y coordinate with right-aligned text.
A layout-anchored extractor trained on Supplier A silently extracts the wrong
field for Supplier B. The text-layer discipline requires a corpus per
`(modelo, año, revision)` triple; the invoice surface has no equivalent
enrollment unit — there is no registry revision for "Proveedor Acme S.L. 2024".

### Failure class 3 — Multi-page invoice continuation logic silently dropped

A multi-page invoice where the total appears only on the last page can silently
lose the total if the OCR pipeline processes only page 1. This has no analogue
in AEAT declaración PDFs, which have a fixed single-page structure per casilla.

### Failure class 4 — Thermal paper character fading

Thermal paper receipts (petrol stations, point-of-sale terminals) can have
partially-faded characters. An 8 becomes a 3; an IVA amount silently changes.
The existing corpus-round-trip discipline detects this only if the corpus
includes degraded specimens — which requires active effort to collect.

### Failure class 5 — Non-Spanish-locale receipts

A purchase invoice from a French supplier uses `.` as the thousands separator
and `,` as the decimal separator, or vice versa relative to Spanish convention.
The `canonical_decimal` helper in `adapters.inbound.financial` addresses this
for bank statements; it does not extend to OCR-extracted text. An OCR engine
that produces `"1.234,56"` from a French invoice with `"1 234,56"` silently
inserts a wrong decimal.

### Failure class 6 — OCR engine version drift

Tesseract 4.x and Tesseract 5.x produce different recognition outputs on the
same image, especially for low-contrast text. A corpus captured against
Tesseract 4.x may produce false-green round-trip tests when run against
Tesseract 5.x. This is the OCR analogue of the "PDF layout changed between
corpus capture and runtime" class — except the change is in the tool, not the
document.

### Failure class 7 — Confidence threshold as a false floor

An OCR engine returning 85% per-character confidence on an entire invoice
silently accepts all characters, even though the 15% low-confidence pool may
cluster on exactly the amount fields. Aggregate confidence is not a sufficient
gate. Field-level confidence is required but is not a universally available
OCR API primitive.

### Why the existing discipline is insufficient for OCR

The declaración corpus discipline (`provisional_pending_specimen`,
`corpus_round_trip_verified`, `verification_source`) operates on text-layer PDFs
where the parser output is deterministic: the same PDF always produces the same
`pdfplumber.extract_text()` output. OCR is **fundamentally non-deterministic**:
the same image may produce different text depending on engine version, image
preprocessing parameters, language model, and runtime environment. This means:

- A round-trip test that passes today may fail after a Tesseract package update
  without any change to the invoice image or the extraction code.
- A corpus fixture that passes CI may not reflect production performance on
  real operator invoices.
- The `corpus_round_trip_verified = true` semantic — "the author confirmed this
  works end-to-end" — cannot carry the same determinism guarantee it carries
  for text-layer PDFs.

---

## UNIT 3 — Discipline analogue proposal

The declaración-extraction discipline uses three interlocking mechanisms:
(a) provenance enum (`verification_source`) declaring how the corpus was obtained,
(b) gate fields (`provisional_pending_specimen`, `corpus_round_trip_verified`)
enforced at registry snapshot build, and (c) structured exception attributes
(`missing/malformed/ambiguous/coverage`) enabling caller-side assertion without
message-string parsing.

The OCR analogue must adapt all three.

### 3a — Provenance enum: `InvoiceCorpusSource`

The financial provider uses `CorpusVerificationSource` as a `Literal` type alias
on a `ClassVar` of the provider class. The declaración registry profile uses
`verification_source: Literal[...]` in `ExtractionProfileDefinition`.

For invoice OCR, the enrollment unit is not a registry revision — it is a
**supplier template** (per-supplier or per-layout-family). The proposed provenance
enum, named `InvoiceCorpusSource`, would cover:

```
"real_operator_invoice_sanitised"    # real operator invoice with PII removed
"real_supplier_corpus"               # invoice collection from a named supplier
"synthetic_from_layout_family"       # template-anchored synthetic (like synthetic_from_aeat_published_text)
"no_corpus"                          # explicit absence — provisional by definition
```

The key difference from `CorpusVerificationSource` (`real_bank_corpus_pdf`,
`synthetic_from_bank_published_text`, `no_corpus`) is the addition of
`real_operator_invoice_sanitised`. For AEAT declaration corpus collection,
real AEAT-issued PDFs are unambiguously public documents. Real operator
invoices contain third-party PII (NIF/CIF, amounts, supplier names) and require
explicit sanitisation before use as test fixtures. The provenance enum must
distinguish sanitised real specimens from synthetic templates.

### 3b — Enrollment unit: supplier template, not registry revision

The declaración discipline enrolls by `(modelo, año, revision)` — a small,
bounded, registry-authoritative set. The bank-PDF discipline enrolls by provider
class (`PdfN26Provider`, future `PdfRevolut`, etc.) — a discoverable set bounded
by the financial institution count.

Invoice OCR has no natural enrollment boundary. Options:

**Option B1 — Per-supplier enrollment.** One template registration per supplier
(e.g., `SupplierTemplate(supplier_id="acme-sl", layout_family="standard-a4-es")`).
Mirrors the per-provider bank discipline. High granularity but fragile when
the same supplier changes invoice layout across years.

**Option B2 — Per-layout-family enrollment.** Categorize invoices into layout
families (e.g., `"spanish-a4-vat-standard"`, `"thermal-receipt-eur"`,
`"international-b2b"`). Lower granularity, more robust to single-supplier changes,
but requires a layout-detection step before extraction.

**Option B3 — Engine-level enrollment with per-field confidence thresholds.**
Enroll the OCR engine version and parameters as a configuration artifact. Each
extraction attempt produces per-field confidence. The gate is whether each
field's confidence exceeds a threshold, not whether a specific supplier template
matched. This is the closest analogue to the `min_coverage` gate.

The research recommendation is **Option B3 as the primary gate, with Option B1
as the optional corpus-collection mechanism**. The rationale: invoice layouts
are unbounded (any supplier, any country, any format); a per-layout-family
taxonomy is a pre-classification problem that predates extraction. The confidence
threshold is the universally applicable gate.

### 3c — Structured exception attributes for OCR

Extend `PurchaseInvoiceEvidenceInputError` (or introduce a sibling class
`InvoiceOcrExtractionError`) with OCR-specific structured attributes:

```
missing: tuple[str, ...]          # fields the OCR engine produced no candidate for
malformed: tuple[str, ...]        # fields extracted but unparseable as target type
ambiguous: tuple[str, ...]        # fields with multiple extraction candidates
coverage: Decimal | None          # fraction of required fields successfully extracted
confidence_below_threshold: tuple[str, ...]   # fields extracted but below confidence floor
character_recognition_uncertain: tuple[str, ...]  # fields where the engine's per-character confidence is below threshold
multi_page_continuation_missing: bool          # True when a continuation page was expected but absent
```

The first four attributes (`missing`, `malformed`, `ambiguous`, `coverage`)
mirror the existing pattern exactly and should use the same semantics. The three
OCR-specific attributes capture failure modes that have no text-layer analogue.

The class should root at `PdfModeloImportError` — the same root used by
`JustificanteParseError`, `DeclaracionParseError`, and `BorradorParseError`.
For OCR failures of supplier invoices (not AEAT filing documents), rooting
directly at `AeatError` via the `PurchaseInvoiceEvidenceInputError` hierarchy
is also acceptable, as supplier evidence is not a modelo-filing artifact.

**Recommendation:** Keep the OCR error class in the application/ledger layer,
rooted at `PurchaseInvoiceEvidenceInputError(AeatError)` — not in
`adapters.inbound.pdf` — because the OCR-evidence surface is application
layer logic over operator-uploaded files, not an inbound adapter for AEAT-issued
documents.

### 3d — Gate mechanism

The text-layer discipline has two complementary gates:
- `provisional_pending_specimen`: author explicitly acknowledges absence of a
  corpus PDF, preventing silent green.
- `corpus_round_trip_verified`: author asserts that extraction works end-to-end
  against corpus PDFs.

OCR adds a third mandatory gate due to non-determinism:

**Engine version pinning gate.** Any OCR extraction implementation must pin the
engine version (Tesseract version, cloud OCR API version, or equivalent) in the
provenance record. A test that passes under engine version A is not guaranteed to
pass under version B. The gate is: if the pinned engine version differs from the
installed version, emit a structured warning rather than a hard failure (since
upgrading the engine may improve recognition) — but log the discrepancy as an
`ambiguous` attribute on the affected fields.

**Corpus determinism note.** The round-trip test pattern can still apply to OCR
with real scanned invoices, but the test expectation should be expressed as
`confidence >= threshold` rather than exact text equality. A test asserting that
`taxable_base` is extracted with `confidence >= 0.95` and parses to within
`0.01` of the ground-truth amount is a better OCR gate than asserting the exact
OCR-output string.

---

## UNIT 4 — Recommended ADR direction

### Honest verdict: separate ADR warranted

The OCR invoice evidence surface is **architecturally distinct** from every
surface addressed by the `2026-05-21-declaracion-extraction-architecture-adr`.
The declaración ADR governs AEAT-issued declaración PDFs parsed by
`adapters.inbound.declaracion._parser.py` — text-layer PDFs, registry-driven
profiles, deterministic extraction, bounded enrollment set.

OCR for purchase-invoice evidence operates in the application/ledger layer on
operator-uploaded arbitrary supplier documents with non-deterministic extraction
and an unbounded enrollment space. The analogy to the bank-PDF discipline
(`FinancialProvider` + `CorpusVerificationSource`) is closer than the analogy
to the declaración discipline.

A separate ADR should be authored titled:
`purchase-invoice-ocr-extraction-discipline`. The existing
`2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr` already established
the surface and mandated OCR confidence tracking; the new ADR would define
how OCR is implemented and governed, including the engine contract, the provenance
enum, the structured exception shape, and the test-collection discipline.

### What the new ADR should not do

It should not re-open the receipt-OCR-pdf-evidence ADR's accepted decisions
(surface naming, CRUD verb set, bucket-event types). It adds the _implementation
contract_ the existing ADR mandated but did not specify.

### Relationship to existing ADRs

| Existing ADR | Relationship |
|---|---|
| `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr` | Precursor — established the surface; the new ADR implements what it mandated |
| `2026-05-21-declaracion-extraction-architecture-adr` | Sibling — established the declaración discipline; OCR discipline mirrors it for a different surface class |
| `2026-05-12-cli-workflow-redesign-evidence-bundle-shape-adr` | Consumer — the evidence bundle shape the OCR extraction must populate |

---

## UNIT 5 — Scoped follow-up plan

The pattern mirrors the W02 (ADR) then W09/W10 (execution) structure of the
declaration-extraction campaign.

### Phase 1 — ADR authoring (research now complete)

- Author `purchase-invoice-ocr-extraction-discipline-adr` covering:
  - `InvoiceCorpusSource` provenance enum
  - `InvoiceOcrExtractionError` structured exception class (rooted at `PurchaseInvoiceEvidenceInputError`)
  - OCR engine pinning requirement
  - Corpus collection discipline (sanitised real invoices vs synthetic templates)
  - Gate mechanism: confidence threshold as the enrollment-level gate
  - Enrollment unit recommendation (Option B3 with optional B1 corpus collection)
  - Explicit decision: which OCR engine family is in scope (Tesseract-family local, cloud API, or both)
  - Decision: whether OCR runs in the service layer or in a new `adapters.inbound.invoice_ocr` adapter

### Phase 2 — Model and error hierarchy implementation

- Add OCR-specific fields to `PurchaseInvoiceEvidence`:
  `extraction_method`, `extraction_confidence`, `manual_review_state`
  (fields mandated by the 2026-05-12 ADR but absent from the current model).
- Introduce `InvoiceOcrExtractionError` with the seven structured attributes
  defined in UNIT 3c.
- Add `InvoiceCorpusSource` as a `Literal` type alias.
- Gate test: mirror `test_provider_declares_verification_source` in
  `test_base.py` for registered OCR handlers.

### Phase 3 — OCR pipeline implementation

- Decide and implement the OCR engine adapter.
- Wire through `aeat app ledger evidence add` with confidence output.
- Corpus collection: gather and sanitise real operator invoice specimens,
  establish the `tests/fixtures/invoices/` corpus root.
- Round-trip tests: confidence threshold assertion, not exact-string equality.

### Phase 4 — Gate enforcement

- Implement the engine-version pinning gate in the service layer.
- Implement the `provisional_pending_invoice_corpus` flag (OCR analogue of
  `provisional_pending_specimen`) on whatever enrollment unit the ADR selects.
- CI gate: any registered OCR handler without a declared `invoice_corpus_source`
  fails the structural test.

---

## Conclusion

The OCR evidence surface is **wholly unimplemented** today. The 2026-05-12 ADR
mandated OCR confidence tracking and extraction-method storage; the current model
and service carry neither. The first implementation obligation is to satisfy the
existing ADR's model requirements (`extraction_method`, `extraction_confidence`,
`manual_review_state`) before any OCR pipeline is wired.

The discipline analogue transfers from the declaración/bank-PDF work with a
structural adaptation: provenance tracking and provisional flags are the right
mechanism, but the enrollment unit must shift from registry-revision to
engine-version + optional corpus-per-supplier, and the test expectations must
accept confidence-threshold assertions rather than exact-match round-trips.

A **separate ADR** is the correct vehicle — not an amendment to the declaración
ADR — because the surface layer (application/ledger), the document class
(operator-uploaded supplier invoices), and the extraction technology (OCR vs
text-layer PDF parsing) are all distinct from what the declaración ADR governs.
