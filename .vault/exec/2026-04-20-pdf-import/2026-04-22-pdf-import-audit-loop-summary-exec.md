---
tags:
  - '#exec'
  - '#pdf-import'
date: '2026-04-22'
modified: '2026-07-17'
body_hash: 'sha256:70333c8f2c99f6e74ca102061e76fad6df2925583d2337528a4db4d46b6a7219'
related:
  - '[[2026-04-20-pdf-import-plan]]'
  - '[[2026-04-22-real-pdf-import-wave-60-exhaustive-audit]]'
  - '[[2026-04-22-real-pdf-import-wave-62-exhaustive-audit]]'
  - '[[2026-04-22-real-pdf-import-wave-64-exhaustive-audit]]'
  - '[[2026-04-22-real-pdf-import-wave-66-exhaustive-audit]]'
  - '[[2026-04-22-real-pdf-import-wave-68-exhaustive-audit]]'
---

# `pdf-import` audit-loop summary: waves 59–68

Back-fill exec record for EPIC #305 sub-waves 59a/b/c through 67g/68a–c. Each entry
states the sub-wave identifiers, the landed commit SHA, what shipped, and which
exhaustive-audit wave confirmed closure. The audit docs under `.vault/audit/` remain the
load-bearing pipeline artefact and contain full finding-by-finding closure tables.
Closes [issue #313](https://github.com/nevenincs/aeat/issues/313).

## Sub-wave closure table

- **59a + 59b** — `7f678a9` — fix(pdf-import,formulas): digit-boundary regex refinement
  (trailing-digit false-positive) + zero-boundary coverage for `DecimalExtractor`.
  Closed against **wave 60 audit** (`2026-04-22-real-pdf-import-wave-60-exhaustive-audit`).

- **59c** — `c36f9b0` — test(formulas): external-anchored worked examples for
  Modelos 115/123/180/200/202/390; first six rulesets to carry BOE-sourced fixture
  values per the external-anchoring convention mandated by `vaultspec-codify`.
  Closed against **wave 60 audit**.

- **61a + 61b + 61c** — `d30c530` — test(formulas): correct Modelo 202 17% rate
  (LIS art. 40.3 párr. 1, not 23%); external anchors for Modelos 130_2025 and
  100_summary_2025; retro-annotated closure markers on wave 48/53/58 audit docs;
  ADR §Future milestones refreshed to reflect variant-axis already live (wave 47).
  Closed against **wave 62 audit** (`2026-04-22-real-pdf-import-wave-62-exhaustive-audit`).

- **61d** — `c08ad18` — feat(pdf-import): thread `thousands_sep` through
  `QuarterlyGenParams` and `draw_casilla_box`; parametrized NBSP round-trip
  coverage across the ten-modelo fleet. Partial close of wave 60 H3 (end-to-end
  PDF round-trip via reportlab/pdfplumber confirmed infeasible; scope documented).
  Closed against **wave 62 audit**.

- **61e** — `40c45df` — test(pdf-import): hyphenated-label synthetic rendering
  plus extractor round-trip test (`wrap_label_at` kwarg on `draw_casilla_box`;
  Modelo 111 renders "Reten-\nciones" and stitches correctly).
  Closed against **wave 62 audit**.

- **61f** — `a12342c` — test(formulas): operand-swap mutation harness for
  `sub_op` chains across Modelos 130/131/202/303 (one exemplar per modelo;
  extended to 15 cases in wave 63b).
  Closed against **wave 62 audit**.

- **63a + 63b + 63c + 63d** — `65e5643` — test(formulas,pdf-import): citation
  accuracy — `art. 103` → `arts. 79+99` in Modelo 100 summary test; `110.1.b` →
  `110.1.a` in Modelo 130 test (wave 63a); mutation harness expanded to every
  `sub_op`-bearing casilla across 130/131/200/303 including Modelo 200 casilla
  00611 (wave 63b); wave 48 H3 audit row refreshed + modelos.md row-15 drift
  corrected (wave 63c); Modelo 390 docstring, 202 operand-swap docstring,
  `thousands_sep` pattern validator, test rename, y-ordering comment (wave 63d).
  Closed against **wave 64 audit** (`2026-04-22-real-pdf-import-wave-64-exhaustive-audit`).

- **65a + 65b + 65c + 65d** — `ab808d2` — test(formulas): five citation-accuracy
  fixes across Modelos 130/131/202/100_summary (RIRPF 110.1 subsections, 110.2 →
  110.1.c, 110.4 → 110.1.b, LIS 24% → 25% general tipo, LIRPF art. 77 → art. 73)
  (wave 65a); modelos.md provenance and mutation-harness docstring invariant
  corrected (wave 65b); ADR citation-accuracy author checklist added (wave 65c);
  ADR deferral section added naming the consolidated artefact path (wave 65d).
  Closed against **wave 66 audit** (`2026-04-22-real-pdf-import-wave-66-exhaustive-audit`).

- **67a + 67b + 67c + 67e** — `29a537e` — test(formulas): wave 64 audit closure-
  status table added (wave 67a); LIRPF arts. 62/67/73/77/79/99 disambiguated in
  Modelo 100 summary test; Modelo 111 citations corrected to RIRPF arts. 99/100 +
  LIRPF arts. 99/101.2/101.7; Modelo 200 art. 125 → art. 30; ADR narrative updated
  to "12 of 14 anchored, only 303_2024 remains" (wave 67b); ADR checklist bullet 5
  reframed as grep-checkable literal-string gate; bullet 6 added requiring BOE
  consolidated-text retrieval date (wave 67c); mutation-harness delta assertion
  `abs(baseline − mutated) >= Decimal("0.02")` added mechanically (wave 67e).
  Closed against **wave 68 audit** (`2026-04-22-real-pdf-import-wave-68-exhaustive-audit`).

- **67g + 68a + 68b + 68c** — `fe8fa85` — fix(formulas): RIRPF art. 100.3.a
  cross-cutting sweep — `100.3.a` → `100.1` across Modelos 115/180 production
  `_CITATIONS` tuples + tests (5 files, confirmed no sub-letter structure in
  BOE-A-2007-6820) (wave 67g / 68a); Closure-status tables back-filled into wave 60
  and wave 62 audit docs (wave 68b); GH issue #313 (this issue) filed for exec-record
  back-fill; GH issue #314 filed for 9 uncovered `sub_op` chains (wave 68c);
  Modelo 131 production `_CITATIONS` corrected (art. 110.4 → 110.1.b,
  art. 110.2 → 110.1.c) + 131_2024 clone swept (wave 68a).
  Confirmed closed by **wave 70 audit** (wave 68 doc retroactively records closure
  table; wave 70 stream 4 confirmed all H/M/L findings closed).
