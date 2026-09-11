---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-11'
modified: '2026-09-11'
body_schema: 'body-v2'
body_hash: 'sha256:d67dcc1dad61b7f9758fa4cdcf435eb796b6723fd8cd67a0482cdacedfd8806a'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---
# `facts-registry` audit: `S77 category adapter retirement review`

## Scope

Reviewed W04.P15.S77 against the accepted governed-fact catalogue decision, the approved facts-registry plan, discovery research, and the adapted-family-normalization reference. The review covered authored category facts, the retained category authority projection, provider registration, the Wave 2 handoff ledger, direct-fact tests, and the retirement census.

## Findings

### direct-fact-window-gate | medium | The full supported filing window is no longer protected by a direct-fact regression gate

The removed raw-corpus entry in the exact-year coverage suite had asserted category coverage against the master supported-year declaration. The replacement test proves every category resolves for 2025 and refuses in 2099, but deleting a single supported historical or future yearly variant would still leave the category present and the new test green. Current inspection proves all 42 categories cover every master year 2022 through 2026, and the focused suite passes; the gap is preventive coverage for a future authoring error, not a current data-loss defect.

### direct-fact-window-gate | medium | Resolved by authored-facts coverage and an isolated mutation bite

The replacement gate derives the master supported filing years from the registry catalogue, reads only the normalized category profile fact through the ordinary fact loader, and requires exactly one category variant for every category/year pair. Its isolated candidate removes the 2024 `mutualidad_alternativa` variant and the same assertion fails with the missing context. The negative census remains the sole mention of the retired provider identifier; no legacy source or adapter participates in the test.

## Recommendations

- The direct-facts coverage-and-bite recommendation is complete.
- Retain the authored-facts gate as the regression boundary; do not reintroduce a category adapter, raw corpus, or provider registration.

## Verdict

Clear. No critical, high, or unresolved medium finding remains in the S77 category adapter retirement scope.
