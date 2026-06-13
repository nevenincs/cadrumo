---
tags:
  - "#audit"
  - "#real-pdf-import"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-22-real-pdf-import-wave-48-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-53-exhaustive-audit]]"
---

# real-pdf-import — wave 58 exhaustive audit

## Scope

Third cycle of the exhaustive-audit pattern. Four parallel streams
verify waves 54-57b remediations and flag residual gaps.

Commit range audited: `086b1dd..HEAD` (waves 54/55/56/57a/57b).

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 wave 54-57b remediation verification | PASS | 0 | 0 | 0 |
| 2 external-anchored fixture arithmetic | PASS | 0 | 0 | 0 |
| 3 coverage completeness | REVISION REQUIRED | 2 | 2 | 2 |
| 4 primitive + extractor regression | REVISION REQUIRED | 2 | 1 | 2 |

**Total open: 4 HIGH, 3 MEDIUM, 4 LOW.** All waves 54-57b
remediations cleanly closed their declared wave-53 findings
(streams 1+2 PASS). New findings surface coverage + regression
gaps that waves 54-57b did not fully close.

## Closure status (updated 2026-04-22, wave 61b per wave 60 stream 3 H2)

| Finding | Status | Closing wave |
|---|---|---|
| H1 digit-boundary regex | CLOSED | wave 59a (`7f678a9`) |
| H2 NBSP round-trip | OPEN | tracked as wave 61d (partially addressed in wave 56) |
| H3 10 tautological rulesets | PARTIAL | wave 59c (`c36f9b0`) anchored 6/10; 130_2025 + 100_summary remain (wave 61c) |
| H4 zero-boundary 13/18 missing | CLOSED | wave 59b (`7f678a9`) — all 18 rulesets covered |
| M1 soft-hyphen blind `.replace` | CLOSED | wave 56 (`38cbe6c`) + wave 59a refinement |
| M2 130_2025 drift-check anchoring | OPEN | tracked as wave 61c |
| M3 end-to-end hyphenation test | OPEN | tracked as wave 61e |

## HIGH findings

### H1 (stream 4) — `_normalise_pdf_text` stitches digit-boundary `-\n` pairs

`src/aeat/adapters/inbound/declaracion/_generic_extractor.py:274` regex
`(?<=\w)[-­]\n(?=\w)` uses `\w` which matches digits + underscore
in addition to letters. An adversarial PDF like
``importe de 9-\n10 euros`` collapses to ``910``. Real AEAT
templates rarely hyphenate across digits but OCR'd PDFs or
amount-wrap edge cases could trigger silent corruption.

**Fix**: tighten lookarounds to letters-only
`(?<=[A-Za-zÀ-ÿ])[-­]\n(?=[A-Za-zÀ-ÿ])`.

### H2 (stream 4) — NBSP primitive not exercised at extractor round-trip

Wave 56 added `format_amount(thousands_sep=...)` but
`_generator_shared.py:120` hard-codes the default `"."` — every
live modelo round-trip in `test_quarterly_extractors.py` goes
through the dot-separator path. The wave-51 H1 regex fix is
only exercised by synthetic line tests
(`test_label_regex.py::TestSpanishAmountGroupRegex`), not by an
end-to-end pdfplumber-text-stream round-trip.

**Fix**: thread `thousands_sep` through `CasillaBox` / `draw_casilla`
and add one NBSP round-trip test per live modelo.

### H3 (stream 3) — 10 rulesets still tautologically tested

Wave 57a/b anchored 4 rulesets (303_2025, 111_2025, 131_2025,
130_2024). The remaining 10 still compute happy-path values via
rate-mirror from the ruleset:

- 115_2024/2025 (19% arrendamientos)
- 123_2024/2025 (capital mobiliario)
- 130_2025 (drift-check of 130_2024 only)
- 180_2024/2025 (19% arrendamientos annual)
- 200_2024 (25% IS)
- 202_2025 (17% IS trimestral)
- 303_2024 (IVA)
- 390_2025 (IVA annual)
- 100_summary_2025 (aggregation)

Each needs one `test_external_worked_example_*` citing BOE/RIRPF/
LIVA/Manual Práctico as provenance.

### H4 (stream 3) — 13/18 rulesets lack zero-boundary tests

Only 111_2025, 130_2024, 180_2025, 303_2025 exercise a genuine
zero-input clean path. 13 gap: 115_2024/25, 123_2024/25,
131_2024/25, 130_2025, 180_2024, 111_2024, 200_2024, 202_2025,
303_2024, 390_2025, 100_summary_2025. A regression that misroutes
a zero to a division-by-something or NaN would ship silently.

**Fix**: parametrized zero-boundary test per ruleset (cheap —
~3 LOC each).

## MEDIUM findings

- **M1 (stream 3)**: 303_2024 mutation coverage thin. Only 3
  tests, 2 of which are constants/parity; only one substantive
  case. Add a non-parity mutation (e.g., wrong rate → BOE 10%).
- **M2 (stream 3)**: 130_2025 is a drift-check of 130_2024. Its
  `test_2025_no_drift_from_2024` is load-bearing for external
  anchoring; add a BOE-cited worked example to break the chain.
- **M3 (stream 4)**: End-to-end hyphenation stitching not
  asserted at extractor layer. Only the string-transform is
  tested; no extract → diff pipeline assertion.

## LOW findings

- **L1 (stream 3)**: Backfill test module consolidates 5 rulesets
  without per-backfill zero-boundary parametrization.
- **L2 (stream 3)**: `test_modelo_115_2025` asserts citation IDs
  in the ruleset but never a BOE-published number directly.
- **L3 (stream 4)**: Pre-existing 3 env-dependent test failures
  confirmed unrelated to wave 51/56 primitive changes.
- **L4 (stream 4)**: `_normalise_pdf_text` perf is linear on
  realistic PDFs (5.6ms for 680-casilla Modelo 390 text). No
  catastrophic backtracking. No action needed.

## Remediation plan — wave 59

- **Wave 59a** (primitive regression fix — stream 4 HIGH):
  tighten `_normalise_pdf_text` lookarounds to letters-only;
  add a digit-boundary regression test.
- **Wave 59b** (coverage breadth — stream 3 HIGH):
  parametrized zero-boundary tests for 13 gap rulesets.
- **Wave 59c** (external anchors — stream 3 HIGH): external-
  anchored fixtures for 115/123/180/200/202/390/100_summary
  (priority by Kent-traffic).
- **Wave 59d** (NBSP round-trip — stream 4 HIGH): thread
  thousands_sep through synthetic generator → add 1 NBSP
  round-trip per live modelo.
- **Wave 59e** (MEDIUMs): 303_2024 non-parity mutation;
  130_2025 BOE-cited worked example; end-to-end hyphenation
  extractor test.

Each sub-wave ships with its own regression tests and is paired
with a wave-60 audit loop per the exhaustive-audit contract.
