---
tags:
  - '#exec'
  - '#modelo-verify-nonzero-guards'
date: '2026-07-01'
modified: '2026-07-17'
step_id: 'S29'
related:
  - "[[2026-07-01-modelo-verify-nonzero-guards-audit]]"
  - "[[2026-06-30-modelo-verify-nonzero-guards-plan]]"
---

# M123 exoneration grounding re-verification

This record documents a code-review-driven grounding pass, not an originally
planned Step. `W03.P09.S27` (independent code review) raised a MEDIUM finding
against the already-shipped M123 `06->09`
ADVISORY guard (`W01.P02.S06`): the guard's false-positive-freedom claim had
not been corroborated against RIRPF/RIRPF-reglamento retención-exoneration and
partial-reduction cases. This exec record captures the corroboration pass and
its conclusion; `W03.P09.S29` is the plan Step that converts review findings
into tracked Steps or documented deferrals and should cross-reference this
record and its audit.

## Description

- Re-read the `modelo-verify-nonzero-guards` ADR, research, and the M714
  `W02.P06` audit to model the required rigor.
- Read the M123 `2024-y-siguientes` casillas and formulas
  (`src/aeat/_data/registry/aeat/modelos/123/revisions/2024-y-siguientes/`) to
  confirm casillas `04`/`05`/`06` are declared as `base_retenciones` (the base
  on which retention is computed), not gross income paid.
- Read the bundled `rd-439-2007:art-90` corpus text in full: a flat 19 percent
  rate, reduced 60 percent (to 7.6 percent) only for capital-semilla income
  under `ley-35-2006:art-68.4.h`; confirmed the reduction never reaches zero.
- Read the bundled `rd-439-2007:art-108` corpus text, which confirms the
  general reglamento mechanism for a "declaracion negativa" filed "por razon
  de su cuantia" -- and confirmed (via the absence of any cuantia floor on the
  bundled `art-90`, plus an independent corroborating citation found in the
  bundled `ley-35-2006.html` tying RIRPF art. 81.1's cuantia table to
  rendimientos del trabajo/pensiones, not capital mobiliario) that this
  general mechanism has no capital-mobiliario application under the bundled
  corpus.
- Searched the full registry tree and the full bundled corpus for RD 439/2007
  arts. 74/75/76 (the type-based retention-exoneration list) and confirmed
  neither is present: zero legal-catalogue entries, zero bundled corpus files.
- Cross-checked M193 (the annual informativa mirror of M123) for a parallel
  exempt-base reporting channel; found none, consistent with exonerated
  capital-mobiliario income falling outside this modelo family's declared
  scope entirely rather than being reported at a zero-retention rate inside
  it.
- Searched `orden-hac-56-2024.html` (the M123 form-amendment order, bundled)
  for cuantia/exoneration language relevant to M123's own casillas; found none
  applicable (the matches present concern the unrelated M296 IRNR subclave
  table).
- Persisted the conclusion as a new audit document
  (`.vault/audit/2026-07-01-modelo-verify-nonzero-guards-audit.md`) rather than
  editing the shipped predicate or its tests.

## Outcome

Conclusion (i): no legitimate base-positive/zero-retencion case was found
within the M123 `06->09` guard's structural scope. The guard, its
`legal_refs`, and its two-tier test pair (`test_modelo_123_registry.py`,
`test_verification_m123_advisory.py`) are left unchanged. One residual
grounding gap is recorded as a follow-up recommendation rather than a
guard change: RD 439/2007 arts. 74-76 (the type-based retention-exoneration
list) are not bundled in the corpus and are not cited anywhere in the legal
catalogue, so the "exonerated income never reaches the base casillas"
argument rests on the casillas' own `base_retenciones` semantic role plus the
M193 cross-check rather than on a verbatim exoneration-article citation.

## Notes

No code, registry TOML, or test file was modified by this pass. No incidents,
data loss, or skipped work. The residual corpus gap (RD 439/2007 arts. 74-76)
should be bundled and cross-checked against M123's income categories as a
follow-up if a future review wants a fully closed-form citation rather than
the structural argument this pass relied on.
