---
tags:
  - '#research'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-27-schema-hardening-m180-legal-ref-drift-repair-exec]]'
  - '[[2026-05-27-schema-hardening-m202-label-drift-repair-exec]]'
  - '[[2026-05-27-schema-hardening-m100-marriage-citation-repair-exec]]'
---



# `schema-hardening` research: `m100-revision-drift`

Researched the remaining strict repeated-casilla drift after the M202 and
M180 repairs. The current corpus now concentrates strict drift in Modelo
100, whose annual revisions are non-overlapping legal forms.

## Findings

The production drift validator is registry-wide and generic, but it is
overlap-aware. It compares repeated casilla ids only when the two revision
period selectors overlap. Annual Modelo 100 revisions declare distinct
single-year `0A` selectors, so `2024` and `2025` are not compared by the
hard load-time drift gate.

Ignoring that overlap guard for inventory purposes shows large M100 drift:
`legal_refs`, `label`, `section`, `semantic_role`, and `data_type` all differ
across annual revision pairs. The largest adjacent-pair surfaces are:

| Pair | Drifted repeated ids | Main cause |
| --- | ---: | --- |
| `2024 -> 2025` | 2047 | legal-reference retrofit plus 2025 extraction/schema reshaping |
| `2020 -> 2021` | 1499 | legal-reference normalization mismatch |
| `2021 -> 2022` | 541 | mostly annual label evolution |
| `2023 -> 2024` | 484 | mostly annual label evolution |
| `2022 -> 2023` | 401 | mostly annual label evolution |

The drift is mixed, not a single typo class:

- Many `legal_refs` differences are grounding-retrofit debt where later
  revisions carry broader citation sets than earlier revisions.
- Many `label` differences are legitimate annual form evolution, including
  year windows and form text that changes per exercise.
- Some repeated numeric ids are genuinely repurposed between annual forms.
  This means a hard all-years repeated-id validator would fail valid annual
  form evolution.
- There is still clear normalization debt, including unresolved placeholder
  tokens such as `{0}` and accent-stripped Spanish terms such as `Reduccion`
  and `integro`.

## Decision Pressure

The original strict validator mandate is right for overlapping revisions:
if two revisions can both apply to the same filing period, the same casilla id
must not silently diverge. It is too blunt for non-overlapping annual forms
where AEAT can repurpose numeric ids or legally change form labels.

The next schema-hardening substrate should remain generic. The safe sequence
is:

1. Codify current overlap-only hard-fail semantics with focused tests using
   real `PeriodSelector` objects.
2. Add a non-failing cross-revision drift report for non-overlapping revision
   pairs, grouped by modelo, pair, field, and example casillas.
3. Add generic label-normalization diagnostics for obvious extraction
   artifacts across all modelos.
4. Consider a generic casilla continuity contract, such as a continuity key
   or explicit evolution record, before enforcing non-overlapping M100 drift.

No M100-specific exception should be added. The schema needs a cross-modelo
concept of continuity/evolution before non-overlapping annual drift can
become a hard validation error.
