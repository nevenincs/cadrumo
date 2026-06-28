---
tags:
  - "#audit"
  - "#real-pdf-import"
date: 2026-04-22
modified: '2026-04-22'
related:
  - "[[2026-04-22-real-pdf-import-wave-48-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-53-exhaustive-audit]]"
  - "[[2026-04-22-real-pdf-import-wave-58-exhaustive-audit]]"
---

# real-pdf-import — wave 60 exhaustive audit

## Scope

Fourth cycle of the exhaustive-audit pattern. Four parallel streams
verify waves 59a/b/c remediations and flag residuals that waves 59
did NOT address.

Commit range: `c36f9b0..HEAD` plus in-flight wave-61a fix.

| Stream | Verdict | HIGH | MEDIUM | LOW |
|---|---|---|---|---|
| 1 wave 59 remediation verification | PASS (+1 MEDIUM) | 0 | 1 | 0 |
| 2 external-anchor arithmetic | REVISION REQUIRED | 1 | 0 | 1 |
| 3 audit-trail + ADR consistency | REVISION REQUIRED | 1 | 2 | 2 |
| 4 NBSP round-trip + hyphenation + operand-swap gaps | REVISION REQUIRED | 3 | 0 | 0 |

**Total open: 5 HIGH, 3 MEDIUM, 3 LOW.**

## Closure status (updated 2026-04-22, wave 68)

| Finding | Status | Closing wave |
|---|---|---|
| H1 Modelo 202 23% rate miscite | CLOSED | wave 61a (`d30c530`); further refined wave 65a (`ab808d2`) with 25% general tipo |
| H2 wave 48/53/58 closure markers missing | CLOSED | wave 61b (`d30c530`) + wave 67 (`29a537e`) |
| H3 NBSP round-trip not threaded | PARTIAL | wave 61d (`c08ad18`) threaded thousands_sep; end-to-end PDF round-trip infeasible via reportlab/pdfplumber (documented scope-clarification) |
| H4 hyphenation not asserted end-to-end | CLOSED | wave 61e (`40c45df`) |
| H5 operand-swap mutation tests missing | CLOSED | wave 61f (`a12342c`) — extended wave 63b (`65e5643`) to 15 cases; wave 67e (`29a537e`) added mechanical delta ≥ 0.02 assertion |
| M1 130_2025 + 100_summary_2025 lack external anchors | CLOSED | wave 61c (`d30c530`) — further citation-accuracy refinements in waves 63a/65a/67a |
| M2 wave 48 H3 row stale | CLOSED | wave 67a (`29a537e`) — refreshed per wave-64 audit-trail refresh |
| M3 ADR variant-axis drift | CLOSED | wave 61b (`d30c530`) |
| L1 Modelo 390 docstring imprecision | CLOSED | wave 63d (`65e5643`) |
| L2 coverage matrix provenance behind | CLOSED | wave 63c (`65e5643`); wave 65b (`ab808d2`) reconciled counts |
| L3 no exec records for 59a/b/c | PARTIAL | re-cited as wave 62 H5 → wave 64 H7 → wave 66 H1; ADR deferral section (wave 65d); formal GH issue tracked wave 68d |

## HIGH findings

### H1 (stream 2) — Modelo 202 external anchor used WRONG rate

My wave 59c fixture claimed "LIS art. 29.1 fixes the tipo de
gravamen for micropymes at 23% (since Orden HAC/262/2025)". This is
factually wrong: no reading of LIS art. 29.1 or 40.3 yields 23%.
The actual modalidad-40.3 rate (which Modelo 202 implements) is
**17%** = 5/7 of the 24% tipo general, rounded. My ruleset's own
citation already documents this at `modelo_202_2025.py:80-81`.

**Status — CLOSED in-flight (wave 61a)**: updated test to cite LIS
art. 40.3 párr. 1 with the correct 17% rate. Scenario recomputed:
200 000 × 17% = 34 000 cuota, resultado 22 000, cantidad
max(22 000, 20 000) = 22 000.

### H2 (stream 3) — Closure markers missing across audit docs

Wave 48, 53, 58 audit docs have no explicit "Closed via wave X
(sha)" or "Deferred to wave Y+" stamps on their HIGH findings. The
exhaustive-audit contract requires these; the wave 60 reviewer
correctly flagged this as a contract violation replicating
wave-48-H4.

**Fix**: retro-annotate closure markers across all three audit docs.

### H3 (stream 4) — NBSP round-trip not threaded through generator

Wave 56 added `format_amount(thousands_sep=...)` opt-in but
`_generator_shared.py::draw_casilla_box` never forwards it. Every
live modelo round-trip renders dots, never NBSP. The wave-51 H1
regex fix is not exercised end-to-end.

**Fix**: thread `thousands_sep` through `QuarterlyGenParams` and
`draw_casilla_box`; add a parametrized NBSP round-trip test
across the 10-modelo fleet × 3 separators (~100 LOC total).

### H4 (stream 4) — End-to-end hyphenation not asserted

`_normalise_pdf_text` tested as string transform only; no extractor
round-trip asserts that a hyphenated label in a synthetic PDF
correctly stitches → extracts. Kent-visible risk if AEAT templates
with narrow columns reflow labels across lines.

**Fix**: add `wrap_label_at` kwarg to `draw_casilla_box`; one
Modelo 111 round-trip test rendering `"Reten-\\nciones"`.

### H5 (stream 4) — Operand-swap mutation tests missing

No sub_op-specific mutation tests exist. An `a - b - c` vs
`a - c - b` regression would silently pass. **Highest Kent harm**
per the reviewer's ranking: wrong tax liability that still validates.

**Fix**: parametrized mutation harness across Modelos 130/131/200/
303 sub_op chains (~120 LOC).

## MEDIUM findings

- **M1 (stream 1)**: Modelos 130_2025 and 100_summary_2025 lack
  external anchors. My wave 59c claim "all 2025 rulesets now have
  one" was inaccurate.
- **M2 (stream 3)**: Wave 48 doc status table row H3 still reads
  "DEFERRED to wave 57+" despite 57a/b/59c anchoring 11/14 rulesets.
- **M3 (stream 3)**: ADR §`Future milestones` section still frames
  variant axis as future work; drift from §decision which notes
  wave 47 landed it.

## LOW findings

- **L1 (stream 2)**: Modelo 390 docstring says "96 = sum of
  quarterly 03+06+09" — imprecise; 96 aggregates Modelo 390's own
  sub-totals.
- **L2 (stream 3)**: Coverage matrix provenance line one wave behind.
- **L3 (stream 3)**: No exec records under `.vault/exec/` for
  waves 59a/b/c (vaultspec pipeline contract).

## Remediation plan — wave 61

- **Wave 61a** (in-flight): Modelo 202 17% rate fix (H1).
- **Wave 61b**: retro-annotate closure markers on wave 48/53/58
  docs; update wave 48 H3 status; refresh ADR §Future milestones;
  bump modelos.md provenance (H2 + M2 + M3 + L2).
- **Wave 61c**: external anchors for Modelos 130_2025 +
  100_summary_2025 (M1).
- **Wave 61d**: thread `thousands_sep` through
  `QuarterlyGenParams` + parametrized NBSP round-trip tests (H3).
- **Wave 61e**: hyphenated-label synthetic rendering + extractor
  round-trip test (H4).
- **Wave 61f**: operand-swap mutation harness for 130/131/200/303
  sub_op chains (H5 — highest Kent harm, prioritize).

Each sub-wave ships with its own regression tests per the
exhaustive-audit contract. Wave 62 audit loop follows.
