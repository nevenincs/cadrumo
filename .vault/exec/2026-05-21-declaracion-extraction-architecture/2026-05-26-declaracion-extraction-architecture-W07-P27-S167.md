---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W07.P27.S167'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
  - '[[2026-05-21-declaracion-extraction-architecture-adr]]'
---

# declaracion-extraction-architecture W07.P27.S167

Authored `test_corpus_sidecar_roundtrip.py` — a parametrized test over every
justified PDF+JSON sidecar pair in `tests/fixtures/justificantes/`. The test
derives ground truth from the sanitiser manifest (the `SANITIZED{modelo}{year}`
synthetic CSV token and the always-present `Y0000001S` NIE), not from running
the parser on its own output.

## Files created

- `src/aeat/adapters/inbound/justificante/test_corpus_sidecar_roundtrip.py`
  — 42 test items (41 parametrized + 1 corpus-count guard), all passing.

## Coverage summary

| Modelo | Pairs | Period range         |
|--------|-------|----------------------|
| 100    | 3     | 2021–2023 annual     |
| 111    | 4     | 2024 Q1–Q4           |
| 130    | 12    | 2021–2024 quarterly  |
| 190    | 1     | 2024 annual          |
| 303    | 12    | 2021–2024 quarterly  |
| 390    | 3     | 2021–2023 annual     |
| **Total** | **35** | — |

Plus 1 `test_corpus_pair_count` guard ensuring shrinkage is visible.

## Fields asserted per case (derived from sidecar)

1. `modelo` — exact string match against directory name encoded in `SANITIZED…`
2. `ejercicio` — year segment of `SANITIZED…` token
3. `period` — filename segment (with period-equals-ejercicio quirk table for
   M190, M390, M100/2023)
4. `tax_id` — always `Y0000001S` (synthetic NIE from every sanitiser manifest)
5. `csv` — the `SANITIZED{modelo}{year}` token the sanitiser injected; exact
   match ensures the parser cannot return a different noisy token silently
6. CSV shape (8–24 uppercase alphanum) — structural guard independent of value
7. `presented_at` not None — timestamp extraction live across every layout
8. `source_pdf_sha256` populated, 64 hex chars
9. `verification_url` contains `agenciatributaria.gob.es`

## Edge cases handled

- M190/M390 and M100/2023 layouts print only the ejercicio year in the PDF body
  — `_PERIOD_EQUALS_EJERCICIO` frozenset maps those to the year string, matching
  the observed parser output.
- Sidecars without a `SANITIZED…` replacement token (e.g. partially-sanitised
  or English-UI specimens) return `None` from `_load_ground_truth` and are
  silently skipped; the pair count guard provides a floor.

## Regressions now guarded

- Parser returning wrong modelo string (e.g. `"130"` → `"100"`).
- Parser losing the CSV or matching a noise token instead of `SANITIZED…`.
- Parser swapping ejercicio with periodo.
- Parser corrupting the tax_id across layout variants.
- Parser returning wrong ejercicio year.
- Parser breaking the CSV alphanumeric-uppercase shape constraint.
