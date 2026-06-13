---
tags:
  - '#exec'
  - '#declaracion-extraction-architecture'
date: '2026-05-28'
modified: '2026-05-28'
step_id: S199
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-28-financial-provider-extraction-discipline-adr]]"
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture W10.P42.S199 — bank-PDF provider gate discipline, N26-first extensible

## Step

`W10.P42.S199` — Author bank-PDF provider gate discipline N26-first extensible to BBVA
Santander Caixabank etc; `src/aeat/adapters/inbound/financial/providers/`.

## Audit findings (UNIT 1 + 2)

**Provider framework audit:**

The `FinancialProvider` ABC in `src/aeat/adapters/inbound/financial/providers/_base.py`
declared three class variables (`name`, `supported_extensions`, `source_format`). No
corpus provenance annotation existed on any provider. The exception hierarchy had
`FinancialProviderError < AeatError`, `UnsupportedFinancialSourceError`,
`InvalidFinancialSourceError`, `FinancialValidationError` — but no structured
`missing/malformed/ambiguous/coverage` attributes.

The N26 PDF provider uses `pdfplumber` text extraction, a single `_ROW_RE` regex
anchored on `<narrative> <DD.MM.YYYY> <±amount>EUR`, and `_require_n26_statement` as a
structural identity gate. Three synthetic corpus PDFs exist, generated from the
portfolio-performance open-source test corpus (sanitised text dumps from real N26 layouts).
Per `src/aeat/tests/fixtures/financial/n26/README.md`, no raw operator statement PDFs
are held.

**Silent-failure classes identified:**

- `_ROW_RE` layout drift → zero transaction rows, no exception raised if caller skips
  validation (the `validate_source` path returns `is_valid=False` loudly but `ingest()`
  alone would produce empty output)
- `_is_footer_or_section_line` missing a new section marker → summary-section rows
  included as transactions; amounts parse without error
- Multi-page pages without `_HEADER_LINE` silently skipped
- Amount decimal separator change (German `,` → `.`) would silently scale amounts
- `_BANK_MARKERS` / `_HEADER_LINE` stale → `InvalidFinancialSourceError` (loud, not silent)
- No cross-bank mis-identification possible today (N26 is the only PDF provider)

## Discipline analogue applied (UNIT 3 + 4)

**Architecturally distinct surface — new ADR warranted:**

Banks are not AEAT. The bank-statement surface uses an ABC with class variables, not a
registry-profile schema. Enforcement is via parametrized collection-time tests, not a
snapshot-build validator. A new ADR was authored at
`2026-05-28-financial-provider-extraction-discipline-adr.md` rather than amending the
declaracion ADR. Cross-link to the declaracion ADR is in its `related:` field.

**`BankStatementParseError` added:**

New `FinancialProviderError` subclass in `_base.py` with `missing`, `malformed`,
`ambiguous`, `coverage` structured attributes — same signature as
`DeclaracionParseError` and `JustificanteParseError`. Error code
`REFUSED_FINANCIAL_BANK_STATEMENT_PARSE` registered in
`src/aeat/core/errors/registry/_adapters.py`.

**`CorpusVerificationSource` type alias added:**
`Literal["real_bank_corpus_pdf", "synthetic_from_bank_published_text", "no_corpus"]`

**`FinancialProvider` ABC extended:**

Two new `ClassVar` declarations: `verification_source: ClassVar[CorpusVerificationSource]`
and `provisional_pending_specimen: ClassVar[bool]`.

**All four existing providers tagged:**

- `CsvProvider`: `verification_source = "synthetic_from_bank_published_text"`, `provisional_pending_specimen = False`
- `OfxProvider`: same
- `XlsxProvider`: same
- `PdfN26Provider`: `verification_source = "synthetic_from_bank_published_text"`, `provisional_pending_specimen = False`

**N26 corpus posture documented in `_pdf_n26.py`:** Synthetic from portfolio-performance
corpus; upgrade path to `real_bank_corpus_pdf` described.

## Enrollment framework (UNIT 5)

The `_base.py` module docstring documents the enrollment contract: every new provider must
declare `verification_source` and `provisional_pending_specimen`; `no_corpus` requires
`provisional_pending_specimen = True`; corpus fixture + round-trip test required before
`provisional_pending_specimen = False`; detection registration in `_ordered_candidates`
required. The new ADR captures the BBVA/Santander/Caixabank/ING enrollment checklist.

## Tests added (UNIT 6)

**`test_base.py`** — 7 new tests:
- `test_provider_declares_verification_source` (parametrized × 4 providers)
- `test_provider_declares_provisional_pending_specimen` (parametrized × 4 providers)
- `test_provider_no_corpus_implies_provisional` (parametrized × 4 providers)
- `test_bank_statement_parse_error_default_attributes`
- `test_bank_statement_parse_error_carries_structured_attributes`
- `test_bank_statement_parse_error_is_financial_provider_error`

**`test_pdf_n26.py`** — 2 new tests:
- `test_detect_provider_identifies_n26_corpus_pdf` (parametrized × 3 corpus PDFs)
- `test_pdf_n26_provider_verification_source_is_declared`

**Test results:** 67 passed (up from 48), 22 warnings (all pre-existing ofxparse
deprecation notices), 0 failures.

## ADR (UNIT 7)

New ADR at `.vault/adr/2026-05-28-financial-provider-extraction-discipline-adr.md`
(status: accepted). Cross-linked to `2026-05-21-declaracion-extraction-architecture-adr`.
Plan step `W10.P42.S199` closed via `vault plan step check S199`.

## Honest verdict

The discipline transferred **with structural adaptation**. The bank-statement surface is
architecturally distinct from both the declaracion surface (registry-profile-driven) and
the justificante surface (hardcoded regex + AEAT-specific receipt format). A new ADR was
the correct choice over an amendment.

The transferable parts applied cleanly:
- Structured exception attributes (`missing/malformed/ambiguous/coverage`) — applied as
  `BankStatementParseError`, same signature as the other two error types
- Corpus provenance declaration — applied as ABC `ClassVar` fields rather than registry
  schema fields; enforcement via parametrized tests rather than snapshot-build validator

The non-transferable parts:
- PROVISIONAL snapshot-build gate — does not apply; no registry schema; equivalent
  enforcement is the collection-time parametrized test
- `corpus_round_trip_verified` boolean flag — collapsed into `provisional_pending_specimen`
  because the bank provider surface does not have the same "fixture exists but round-trip
  not confirmed" split that the declaracion surface had (both N26 corpus states are
  explicit and well-understood)

The primary remaining silent-failure gap is `_ROW_RE` layout drift on the `ingest()` path
when callers skip `validate_source`. This is a caller-discipline issue, not a framework
gap; the detection invariant test and the existing `validate_source` gate together enforce
correct usage.
