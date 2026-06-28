---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S215'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - "[[2026-05-30-declaracion-extraction-architecture-research]]"
  - "[[2026-05-30-purchase-invoice-ocr-extraction-discipline-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr]]"
---

# `declaracion-extraction-architecture` W10.P56.S215 -- purchase-invoice OCR ADR ratification

## Step

Author and commit `2026-05-30-purchase-invoice-ocr-extraction-discipline-adr.md`,
ratifying the discipline analogue derived from the W10.P44 OCR evidence research
closure (W10.P44.S201). The ADR supersedes the 2026-05-12 receipt-OCR ADR on OCR
implementation contract, structured exception shape, provenance discipline, and gate
machinery.

## Execution

### UNIT 1 -- Source documents read

Four documents read in full before authoring:

- `2026-05-30-declaracion-extraction-architecture-research.md` -- W10.P44 research
  closure: audit findings, 7 silent-failure classes, discipline analogue proposal,
  ADR direction (UNIT 4), and scoped follow-up plan (UNIT 5).
- `2026-05-12-cli-workflow-redesign-receipt-ocr-pdf-evidence-adr.md` -- precursor
  ADR; status accepted; `extraction_method`, `extraction_confidence`, `manual_review_state` mandated
  but not yet implemented.
- `2026-05-28-financial-provider-extraction-discipline-adr.md` -- bank-PDF
  discipline ADR (structural template for the OCR discipline).
- `2026-05-21-declaracion-extraction-architecture-adr.md` -- parent ADR with
  W10.P44 amendment mandating the separate ADR.

### UNIT 2 -- ADR authored

`.vault/adr/2026-05-30-purchase-invoice-ocr-extraction-discipline-adr.md` created.

The ADR covers:

- **Supersession.** 2026-05-12 receipt-OCR ADR superseded on OCR implementation
  contract; surface decisions (CRUD verbs, bucket events) remain authoritative.
- **Four architectural axes** establishing why a separate ADR is warranted:
  surface layer (`application/ledger` vs `adapters.inbound`),
  document class (operator-uploaded invoices vs AEAT-issued modelos),
  extraction technology (non-deterministic OCR vs deterministic `pdfplumber`),
  enrollment space (unbounded suppliers vs bounded `(modelo, ano, revision)`).
- **Seven OCR-specific silent-failure classes**: image-quality degradation,
  supplier-layout variation, multi-page continuation drop, thermal-paper fading,
  non-Spanish locale, engine version drift, aggregate confidence false floor.
- **InvoiceCorpusSource**: `Literal[`real_operator_invoice_sanitised, real_supplier_corpus,
  synthetic_from_layout_family, no_corpus]`. The sanitised-real variant is
  novel: AEAT corpus PDFs are public; operator invoices require PII removal.
- **InvoiceOcrExtractionError** rooted at `PurchaseInvoiceEvidenceInputError(AeatError)`
  with seven structured attributes: `missing`, `malformed`, `ambiguous`, `coverage` (base)
  + `confidence_below_threshold`, `character_recognition_uncertain`,
  `multi_page_continuation_missing` (OCR-specific).
- **Hybrid B3+B1 enrollment**: engine-version + confidence threshold (mandatory) +
  optional per-supplier corpus.
- **Three complementary gates**: `provisional_pending_invoice_corpus` flag,
  engine-version pinning, per-field confidence threshold.
- **First implementation obligation**: `extraction_method`, `extraction_confidence`,
  `manual_review_state` on `PurchaseInvoiceEvidence` (satisfies the 2026-05-12 mandate).
- **Constraints**: `AeatError` hierarchy, `Settings` for config, `tr()` for messages,
  real-behaviour tests only, engine selection deferred.

### UNIT 3 -- Cross-links and plan

- Research doc `2026-05-30-declaracion-extraction-architecture-research.md`:
  `related:` extended with ``2026-05-30-purchase-invoice-ocr-extraction-discipline-adr``.
- Declaracion ADR `2026-05-21-declaracion-extraction-architecture-adr.md`:
  `related:` extended with ``2026-05-30-purchase-invoice-ocr-extraction-discipline-adr``.
- Plan `W10.P56` added to `2026-05-21-declaracion-extraction-architecture-plan.md`.
- `W10.P56.S215` added and checked (closed) in the plan.

### Honest verdict

The ADR captures the complete discipline analogue as defined by the research.
All seven silent-failure classes are documented. All three transfer mechanisms
(provenance enum, gate fields, structured exception attributes) are ratified.
The enrollment unit decision (hybrid B3+B1) is made and justified.

Two axes remain as explicitly deferred pending the implementation phase:

1. **OCR engine selection** (Tesseract-family local, cloud OCR API, or both) --
   deferred; the discipline contract is engine-agnostic by design.
2. **Service layer vs adapter layer** for the OCR engine boundary -- the ADR places
   OCR in `application/ledger/` (research recommendation); whether a separate
   `adapters.inbound.invoice_ocr` adapter is introduced is an implementation
   decision gated on this ADR.

Next-campaign unblock: add `extraction_method`, `extraction_confidence`,
`manual_review_state` to `PurchaseInvoiceEvidence`; then introduce
`InvoiceOcrExtractionError` and `InvoiceCorpusSource` per this ADR.
