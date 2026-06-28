---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S201'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - "[[2026-05-30-declaracion-extraction-architecture-research]]"
  - "[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr]]"
---

# `declaracion-extraction-architecture` W10.P44.S201 — OCR evidence extraction discipline research

## Step

Research closure for the OCR/evidence invoice path deferred per W02 (tasklist #70).
Author the research document capturing the discipline analogue for the image-based
extraction class.

## Execution

### UNIT 1 — Existing OCR path audit

**Finding: OCR extraction is wholly unimplemented.**

`src/aeat/application/ledger/_evidence.py` — the sole entry point for purchase
invoice evidence — accepts PDF and image file inputs, hashes them, and persists
a `PurchaseInvoiceEvidence` record. The `media_kind` field is `"pdf" | "image"`.
All invoice fields (`supplier`, `invoice_number`, `invoice_date`, `taxable_base`,
`iva_rate`, `iva_amount`) are `Optional` and populated exclusively by manual
operator overrides. There is no OCR pipeline, no extraction confidence field, no
extraction method field, no `provisional_pending_specimen` equivalent, and no OCR
library dependency (`tesseract`, `pytesseract`, `pillow`, `pdf2image`, etc. are
absent from `pyproject.toml`).

The `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr` (accepted;
amended 2026-05-14) explicitly mandated `extraction_method`, `extraction_confidence`,
and `manual_review_state` fields. None are present in the current model.

**Error classes today:**
- `PurchaseInvoiceEvidenceInputError(AeatError)` — line 47; file/extension refusals.
- `PurchaseInvoiceEvidenceNotFoundError(AeatError)` — line 51; CRUD lookup failures.
Neither carries structured attributes. No OCR-specific classes exist.

**Test posture:** `src/aeat/application/ledger/test_evidence.py` tests CRUD
mechanics with a `b"%PDF-1.4 test"` fixture. No OCR, no image extraction tests.

### UNIT 2 — OCR silent-failure class enumeration

Seven classes distinct from the text-layer failure class that the declaración
discipline addresses:

1. **Image-quality degradation**: 150 DPI vs 300 DPI scan silently produces different
   character recognition — same template, different output.
2. **Supplier-layout variation**: two suppliers printing the same field label at
   different positions; a layout-anchored extractor trained on one silently misreads
   the other.
3. **Multi-page continuation drop**: an invoice total appearing only on page 2 is
   silently absent if the OCR pipeline processes only page 1.
4. **Thermal-paper fading**: partially-faded characters produce wrong digit recognition
   (8 → 3) without any extraction error.
5. **Non-Spanish-locale number formats**: a French invoice with `"1 234,56"` can
   silently become `"1234"` or `"123456"` depending on the OCR engine's locale model.
6. **OCR engine version drift**: Tesseract 4.x and 5.x produce different outputs on
   the same image — round-trip tests that pass under one version can fail after a
   package update with no source change.
7. **Aggregate-confidence false floor**: 85% overall confidence masks low-confidence
   clusters on exactly the amount fields; aggregate confidence is not a sufficient gate.

### UNIT 3 — Discipline analogue proposal

The provenance, gate, and structured-attribute mechanisms transfer with adaptation:

- **`InvoiceCorpusSource` provenance enum** (Literal):
  `"real_operator_invoice_sanitised"`, `"real_supplier_corpus"`,
  `"synthetic_from_layout_family"`, `"no_corpus"`. The `_sanitised` variant is
  novel — AEAT corpus PDFs are public; operator invoices require PII removal before
  use as fixtures.

- **Enrollment unit**: engine version + optional per-supplier corpus collection
  (Option B3/B1 hybrid). The unbounded supplier space makes per-revision enrollment
  impractical; per-field confidence threshold is the universally applicable gate.

- **`InvoiceOcrExtractionError`** structured attributes: `missing`, `malformed`,
  `ambiguous`, `coverage` (same semantics as `DeclaracionParseError`), plus three
  OCR-specific additions: `confidence_below_threshold`, `character_recognition_uncertain`,
  `multi_page_continuation_missing`. Error root: `PurchaseInvoiceEvidenceInputError(AeatError)`,
  not `PdfModeloImportError` — because supplier evidence is not an AEAT-issued
  modelo filing document.

- **Gate mechanism**: `provisional_pending_invoice_corpus` flag (analogous to
  `provisional_pending_specimen`) + engine-version pinning in the provenance record.
  Round-trip tests express expectations as `confidence >= threshold` rather than
  exact-string equality.

### UNIT 4 — Research document authored

`2026-05-30-declaracion-extraction-architecture-research.md` — all four units
documented in full. ADR amendment appended to
`2026-05-21-declaracion-extraction-architecture-adr.md` section
"2026-05-30 amendment — OCR research closure (W10.P44)".

### Honest verdict: separate ADR warranted

The OCR invoice surface is **architecturally distinct** from the declaración/
justificante/borrador surfaces:

- Surface layer: `application/ledger` (not `adapters.inbound.*`)
- Document class: operator-uploaded supplier invoices (not AEAT-issued filed modelos)
- Extraction technology: OCR over raster images (not text-layer PDF parsing)
- Enrollment space: unbounded suppliers (not bounded `(modelo, año, revision)` set)
- Determinism property: non-deterministic (not deterministic like `pdfplumber`)

A separate ADR `purchase-invoice-ocr-extraction-discipline` is the correct next-
campaign vehicle. The existing `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-
evidence-adr` established the surface; the new ADR specifies the implementation
contract it mandated.
