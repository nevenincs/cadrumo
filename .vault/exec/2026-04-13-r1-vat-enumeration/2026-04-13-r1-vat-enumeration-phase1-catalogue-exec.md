---
name: r1-vat-enumeration-phase1-catalogue
description: Execution record for phase 1 — rate table, catalogue, lookup, corpus, verify.
type: exec
tags:
  - "#exec"
  - "#r1-vat-enumeration"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-r1-vat-enumeration-plan]]"
  - "[[2026-04-13-r1-vat-enumeration-adr]]"
---

# r1-vat-enumeration phase 1 — catalogue

## what was done

- Populated `_rates.py` with `VAT_RATE_TABLE`, a
  `MappingProxyType`-wrapped mapping covering all 27 EU member
  states and carrying 61 `VATRate` entries in aggregate (ES fully
  expanded with general/reduced/super-reduced/zero; DE/FR/IT/NL
  expanded; every remaining state at least GENERAL). Each rate
  carries `effective_from=2025-01-01`, `effective_until=None`, and
  a BOE / Directive reference string.
- Populated `_catalogue.py` with `VAT_CATALOGUE_2025`, one
  `VATRegulation` per `VATCategory` member (16 total) and two
  Ley 37/1992 citations per regulation for a total of 32 Citation
  records. Every Citation carries a faithful Spanish paraphrase of
  the cited article's operative language, retrieval_date
  2026-04-13.
- Added `_lookup.py` with `lookup_rate` (window-aware) and
  `cite` (canonical-citation renderer with
  source-label mapping).
- Added `_corpus.py` with `load_vat_rules_from_manual(year)` —
  returns `VAT_CATALOGUE_2025` for 2025 with an INFO fallback log,
  raises `VatCatalogueError` for any other year.
- Added `_verify.py` with `verify_catalogue(catalogue)` mirroring
  the `aeat.domain.normatives._verify` pattern; checks category coverage,
  citation presence, `quoted_text_es` non-emptiness, normative id
  shape, modelo number shape.
- Wired the public surface in `src/aeat/domain/financial/vat/__init__.py`.
- Added colocated unit tests: `test_categories.py`, `test_rates.py`,
  `test_rules.py`, `test_corpus.py`, `test_verify.py`.

## files touched

- `src/aeat/domain/financial/vat/_rates.py` (new)
- `src/aeat/domain/financial/vat/_catalogue.py` (new)
- `src/aeat/domain/financial/vat/_lookup.py` (new)
- `src/aeat/domain/financial/vat/_corpus.py` (new)
- `src/aeat/domain/financial/vat/_verify.py` (new)
- `src/aeat/domain/financial/vat/__init__.py` (new)
- `src/aeat/domain/financial/vat/test_categories.py` (new)
- `src/aeat/domain/financial/vat/test_rates.py` (new)
- `src/aeat/domain/financial/vat/test_rules.py` (new)
- `src/aeat/domain/financial/vat/test_corpus.py` (new)
- `src/aeat/domain/financial/vat/test_verify.py` (new)

## gate results

Deferred to end-of-feature consolidated run — see the phase-1 summary.
