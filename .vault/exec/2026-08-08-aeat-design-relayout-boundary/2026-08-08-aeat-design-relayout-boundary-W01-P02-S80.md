---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:cb9eee593fe0b359eb73f8a0e35253f751c2c701a12257fe1df285379514520c'
step_id: 'S80'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Check that a revision's declared layout design applies to the years it claims

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Outcome

**Landed deliberately red. It states the campaign's core defect from registry metadata alone — two dates and a period selector, with no design parsed and nothing paired.**

    m303 '2009-y-siguientes'  claims 2009-2022  design applies from 2025  -> 14 years
    m303 '2023-y-siguientes'  claims 2023-2024  design applies from 2025  ->  2 years
    m390 '2010-y-siguientes'  claims 2010-2024  design applies from 2025  -> 15 years
    m720 '2013-y-siguientes'  claims 2012       design applies from 2013  ->  1 year

**31 mis-covered filing years across the three campaign revisions**, and **19 of 23 revisions are clean** — the divergence is concentrated rather than endemic, which is what makes narrowing a bounded intervention rather than a retreat from the whole surface.

**Why this check exists when the obvious one does not.** Every mechanism requiring a pairing measured as blocked: pairing Modelo 200's 6,537 layout fields to its design's 6,808 slots by box number matched 36.7% unambiguously, and there may be no such mapping to find because the layouts were never derived from a design. This needs neither a field-to-slot nor a record-to-sheet pairing, and no design is parsed at all.

It also states the harm in the unit that matters. A boundary count is a fact about the corpus; a filing-year count is a fact about taxpayers.

**What a divergence proves, and what it does not** — recorded in the module because any one sentence alone misleads:

- It proves the registry's own declaration is internally inconsistent: nothing in the registry asserts those bytes are right.
- It does NOT by itself prove the bytes are wrong, since a layout could coincidentally match an earlier design.
- The campaign independently proved at least one such case writes real values outside its record — Modelo 390's total cuota at byte 1628 against a record declared ending at 1526.

**Limits recorded.** Silent when a design window is WIDER than the claim, which is ordinary and present in the corpus (Modelo 180 covers 2014-2023 while claiming 2019-2022). Blind to wrong offsets within an applicable design. And it trusts the catalogue's dates, which are authored metadata rather than parsed from the design.

Open-ended `applies_to` and open-ended `year_to` are both bounded by the newest corpus year rather than a literal ceiling, so neither becomes a stale constant.

**Modelo 200 now reads clean here** — `claims 2025-2026 / covers 2025-2026` — which is the one-file narrowing from the pilot, visible in this inventory rather than asserted.

## Verification

    uv run --no-sync pytest <the new module> -p no:randomly -n0 -q
    1 failed in 11.45s

    modelo 303 revision '2009-y-siguientes' claims filing year(s) 2009-2022 (14 year(s)) but its
      declared layout design(s) ['aeat-dr-303-2025'] apply only from 2025
    ... and three more, named in full

    ruff check / ruff format --check / ty check   All checks passed!

## Notes

**Narrowing was NOT implemented in this Step.** The row scoped it to inventory. Applying it would take the three divergences to refusing their uncovered years, achieving correctness with no tree authored — at the cost of 31 filing years then served by nothing. That trade is a rescoping decision held by the operator.

**Modelo 720 is outside this campaign** and is a different shape: a one-year underhang rather than multi-year drift. Either its selector reaches a year before AEAT published a design, or the catalogue's `applies_from` is a year conservative. Reported for its owner rather than adjudicated, because deciding needs knowledge of the modelo's first filing year.
