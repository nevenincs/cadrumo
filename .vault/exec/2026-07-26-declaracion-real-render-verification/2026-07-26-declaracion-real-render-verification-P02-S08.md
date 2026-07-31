---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:ec4024262403a45a2815f243b39ebbe5e412e7da727b5531b67c5751dde28817'
step_id: 'S08'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Sweep route R9 across all 29 profiles, checking each profile legal_refs equals the union of its targets own refs

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`
- `.vault/audit`

## Description

- Parsed every revision fragmented `casillas/` subdirectory with
  `tomllib` and read each casilla own `legal_refs` list.
- For each of the 29 profiles, built the union of `legal_refs` across
  its retained target casillas and compared it against the profile
  own `legal_refs` field in both directions, missing-from-profile and
  extra-on-profile.

## Outcome

Found exactly two profiles with a discrepancy, both Modelo 100:
100/2024 and 100/2025 omit rd-439-2007:art-109 and
rd-439-2007:art-110, both carried by their own casilla 0604, while
the 100/2021, 100/2022 and 100/2023 sibling profiles correctly
include both. 100/2025 additionally omits orden-hac-277-2026:art-3,
carried individually by every one of its targets. No other direction
of mismatch was found anywhere in the 29-profile sweep, and the
remaining 27 profiles are clean.

The team lead independently confirmed this measurement, 14 legal_refs
against 16 in the 2021-2023 siblings, and routed the fix to the coder
owning the M100 profile TOMLs.

Findings and full detail: see the specimen-less static route audit
document for this feature, sections r9-two-modelo-100-revisions-
omit-legal-refs-their-own-retained-targets-carry and
r9-clean-across-the-other-27-profiles.

## Notes

This sweep validates only that a profile own legal_refs equals the
union its retained targets declare, not that the citation is the
correct binding provision; that is a separate, narrower claim from
the one registry-calculation-legal-grounding governs.
