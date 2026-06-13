---
tags:
  - '#adr'
  - '#financial-provider-extraction-discipline'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
  - '[[2026-06-04-financial-provider-extraction-discipline-research]]'
---



# `financial-provider-extraction-discipline` adr: `bank-pdf-provider-corpus-discipline-n26-first-extensible` | (**status:** `accepted`)

## Problem Statement

The financial-provider layer at
`src/aeat/adapters/inbound/financial/providers/` ingests bank statement
files (CSV, OFX, XLSX, PDF) and converts them to typed `RawTransaction`
records. The PDF provider (`PdfN26Provider`) uses regex-anchored text
extraction from `pdfplumber`. This creates a structural silent-failure
class identical to the one addressed for AEAT declaración PDFs: a bank
changes its statement layout in a quarterly update, the regex silently
produces zero transactions or wrong amounts, and downstream
reconciliation breaks without an explicit failure signal.

The declaración extraction discipline (formalised in
`2026-05-21-declaracion-extraction-architecture-adr`) established
`corpus_round_trip_verified`, `provisional_pending_specimen`, and
`verification_source` as structured schema fields to gate extraction
profiles. The bank-statement surface needs an analogous but
architecturally distinct discipline: banks are not AEAT; their provenance
semantics differ; the provider framework uses an ABC not a registry-profile
schema; and the failure mode is extraction regression, not missing TOML
configuration.

The task also addressed two gaps in the existing exception hierarchy:
`FinancialProviderError` subclasses had no structured `missing /
malformed / ambiguous / coverage` attributes, forcing callers to parse
message strings to identify the failure kind — the same brittleness class
closed for `DeclaracionParseError` (task #51) and `JustificanteParseError`
(task #67).

## Considerations

**UNIT 1 — Provider framework audit**

The `FinancialProvider` ABC in `src/aeat/adapters/inbound/financial/providers/_base.py`
declares three class variables: `name`, `supported_extensions`,
`source_format`. No corpus provenance is declared. The four concrete
providers (`CsvProvider`, `OfxProvider`, `XlsxProvider`, `PdfN26Provider`)
did not carry any corpus-status annotation.

The N26 PDF provider (`PdfN26Provider`) uses:
- `pdfplumber` for text extraction
- `_ROW_RE` — a single regex anchored on the German-language transaction
  table line format `<narrative> <DD.MM.YYYY> <±amount>EUR`
- `_require_n26_statement` — structural identity gate (bank marker +
  heading + table-header present)
- Three synthetic corpus PDFs generated from the portfolio-performance
  open-source test corpus (sanitised text dumps from real N26 layouts)

The exception hierarchy had: `FinancialProviderError < AeatError`,
`UnsupportedFinancialSourceError`, `InvalidFinancialSourceError`,
`FinancialValidationError`. No `BankStatementParseError` with structured
attributes existed.

**UNIT 2 — Silent-failure classes on the bank-PDF surface**

- *`_ROW_RE` layout drift*: N26 changes the spacing or date/amount
  format between the narrative, booking date, and amount columns.
  `_iter_page_rows` produces zero rows silently; `validate_source`
  returns `is_valid=False` with a human-readable warning string — this
  is a loud failure for the validation path but silent if the caller
  skips validation. The ingest path calls `_require_n26_statement`
  (which passes) and then yields nothing.
- *`_BANK_MARKERS` / `_HEADER_LINE` stale*: If N26 renames the entity
  or changes the header line, `_require_n26_statement` raises
  `InvalidFinancialSourceError` loudly. This is a loud failure.
- *`_is_footer_or_section_line` missing a new section marker*: rows
  from a new summary section are included as transactions. Amounts
  parse correctly; only reconciliation downstream catches the excess.
  This is a silent failure.
- *Multi-page continuation*: `_iter_page_rows` requires
  `_HEADER_LINE` on each page to be present. A page without the
  header is silently skipped. This is a silent failure for continuation
  pages that carry transactions but omit the header line.
- *Amount decimal separator change*: `parse_amount_value` is called
  with `decimal_separator=","` (explicit, correct for German locale).
  A N26 locale change to period-decimal would silently multiply amounts
  by 1000 on comma-thousands-formatted values.
- *Detection mis-identification*: `detect_provider` walks providers in
  priority order; for `.pdf` suffix, `PdfN26Provider` is tried first.
  If `_require_n26_statement` rejects a non-N26 PDF, the next candidate
  (CsvProvider) is tried — it will also reject. No cross-bank
  mis-identification is possible today because N26 is the only PDF
  provider; this becomes relevant when BBVA/Santander PDF providers are
  added.

**UNIT 3 — Discipline analogue design**

The declaración discipline uses a registry-profile schema field
(`provisional_pending_specimen`, `corpus_round_trip_verified`,
`verification_source`). The bank-statement surface uses an ABC with
class variables — a different mechanism for the same structural purpose.

The analogue maps as follows:

| Declaración discipline | Bank-provider discipline |
|---|---|
| `provisional_pending_specimen` on `ExtractionProfileDefinition` | `provisional_pending_specimen: ClassVar[bool]` on `FinancialProvider` |
| `corpus_round_trip_verified` on `ExtractionProfileDefinition` | implied by `provisional_pending_specimen = False` with a non-`no_corpus` source |
| `verification_source` on `ExtractionTargetDefinition` | `verification_source: ClassVar[CorpusVerificationSource]` on `FinancialProvider` |
| snapshot-build validator gate | parametrized test `test_provider_declares_verification_source` at collection time |
| `DeclaracionParseError.missing/malformed/ambiguous/coverage` | `BankStatementParseError.missing/malformed/ambiguous/coverage` |

The PROVISIONAL gate (registry validator fires when fixture exists but
flags absent) does not transfer literally — there is no registry schema
to carry the gate. The equivalent enforcement is a parametrized test
at collection time that asserts the class variables are present and valid.

## Constraints

- Must use `AeatError` hierarchy — `BankStatementParseError` roots at
  `FinancialProviderError < AeatError`, not at `PdfModeloImportError`
  (banks are not AEAT filing; the two domains are architecturally
  separate).
- `ErrorCode` registry entry required for every new `AeatError` subclass
  (`REFUSED_FINANCIAL_BANK_STATEMENT_PARSE` added to
  `src/aeat/core/errors/registry/_adapters.py`).
- No new top-level packages; all changes are within the existing
  `financial.providers` module.
- Real-behaviour tests only — the existing three N26 corpus PDFs are
  used for the detection invariant test.

## Implementation

**`BankStatementParseError`** added to `_base.py` as a new
`FinancialProviderError` subclass. Carries `missing`, `malformed`,
`ambiguous`, `coverage` structured attributes with the same signature
as `DeclaracionParseError` and `JustificanteParseError`. The
`REFUSED_FINANCIAL_BANK_STATEMENT_PARSE` error code is registered in
`src/aeat/core/errors/registry/_adapters.py`.

**`CorpusVerificationSource`** type alias added to `_base.py`:
`Literal["real_bank_corpus_pdf", "synthetic_from_bank_published_text", "no_corpus"]`.

**`FinancialProvider` ABC** gains two new `ClassVar` declarations:
`verification_source: ClassVar[CorpusVerificationSource]` and
`provisional_pending_specimen: ClassVar[bool]`. All four existing
providers are tagged:

- `CsvProvider`: `verification_source = "synthetic_from_bank_published_text"`,
  `provisional_pending_specimen = False`
- `OfxProvider`: same as CSV
- `XlsxProvider`: same as CSV
- `PdfN26Provider`: `verification_source = "synthetic_from_bank_published_text"`,
  `provisional_pending_specimen = False` — corpus is three synthetic PDFs
  from the portfolio-performance open-source test corpus; structural family
  is confirmed against real N26 layouts

**New tests** in `test_base.py`:
- `test_provider_declares_verification_source` — parametrized over all
  four providers, asserts the class var is declared and valid
- `test_provider_declares_provisional_pending_specimen` — asserts bool type
- `test_provider_no_corpus_implies_provisional` — asserts invariant
- `test_bank_statement_parse_error_default_attributes` — asserts defaults
- `test_bank_statement_parse_error_carries_structured_attributes` — asserts
  named kwargs populate correctly
- `test_bank_statement_parse_error_is_financial_provider_error` — asserts
  hierarchy

**New tests** in `test_pdf_n26.py`:
- `test_detect_provider_identifies_n26_corpus_pdf` — parametrized over
  all three N26 corpus PDFs, asserts `detect_provider` returns
  `PdfN26Provider`
- `test_pdf_n26_provider_verification_source_is_declared` — asserts the
  N26 provider's specific corpus posture

**Future-provider enrollment pattern** is documented in the `_base.py`
module docstring.

## Rationale

The declaración discipline established the pattern for both registry-profile
and hardcoded-extractor surfaces (justificante used the latter analogue in
task #67). The bank-PDF surface is a third architectural context — neither
registry-profile-driven nor AEAT-specific — but the silent-failure class
is identical. Applying the same structured-attribute shape on the exception
and the same corpus-status declaration on the provider class maximises
consistency while respecting the architectural difference.

A separate ADR (this document) is preferred over amending the declaración
ADR because: (a) banks are not AEAT; provenance semantics, corpus
acquisition, and failure modes differ; (b) the enforcement mechanism is
ABC class variables + parametrized tests, not a snapshot-build validator;
(c) future bank providers enrol via a documented ABC extension, not by
authoring TOML profiles.

## Consequences

- Every new bank provider subclass must declare `verification_source` and
  `provisional_pending_specimen`. Omitting them fails the collection-time
  parametrized test `test_provider_declares_verification_source`.
- A provider with `no_corpus` must set `provisional_pending_specimen =
  True`; attempting to set it `False` with `no_corpus` fails the invariant
  test `test_provider_no_corpus_implies_provisional`.
- `BankStatementParseError` is available for future use in the N26 provider
  and any future PDF provider that encounters partial-extraction failures
  (as opposed to structural-identity failures which remain
  `InvalidFinancialSourceError`).
- The three N26 corpus PDFs are confirmed as `synthetic_from_bank_published_text`
  until an operator donates real sanitised statements, at which point
  `verification_source` is upgraded to `"real_bank_corpus_pdf"`.
- The detection invariant test guarantees that adding a second PDF
  provider without updating the detection logic will surface as a test
  failure.

## Enrollment pattern for future bank PDF providers

Adding a provider for BBVA, Santander, Caixabank, or ING PDF statements
requires:

1. A new `_pdf_<bank>.py` module containing a subclass of `FinancialProvider`
2. The subclass must declare all five class variables:
   `name`, `supported_extensions`, `source_format`,
   `verification_source`, `provisional_pending_specimen`
3. If no real corpus PDF is available, set
   `verification_source = "no_corpus"` and
   `provisional_pending_specimen = True`
4. When corpus PDFs are acquired, move to
   `verification_source = "real_bank_corpus_pdf"` or
   `"synthetic_from_bank_published_text"` and set
   `provisional_pending_specimen = False`
5. A corpus fixture directory at `tests/fixtures/financial/<bank>/`
   and a parametrized round-trip test in `test_pdf_<bank>.py`
6. Registration in `_detection.py`'s `_ordered_candidates` — PDF suffix
   must try the new provider in addition to `PdfN26Provider`
7. Registration in `_detection.py`'s `_ALL_PROVIDERS` (or the test must
   be updated to include the new provider explicitly)
8. An `ErrorCode` registry entry for any new exception types
