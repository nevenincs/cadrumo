---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:059d4a0d54efb69482cbaeebf05a8bd90ca1b886f746d6145e86fc464e062b9a'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---
# `aeat-export-fragment-generator-authority` audit: `S60 producer and projection address formal review`

## Scope

This read-only formal review covered only `W04.P07.S60` and its named implementation and test surfaces. It checked that `taxpayer.tax_id` is a distinct closed producer resolving the filing snapshot taxpayer NIF rather than presenter identity; that simplified-regime module projection references use strict annual-Orden ordinals 1 through 7; that an absent higher ordinal yields `None`; that the retired projection-level `module_identity` has no alias or compatibility reader; that the filing-producer resolver remains exhaustive; that tests use real code without fakes, mocks, stubs, patches, monkeypatches, skips, xfails, or mirrored business logic; and that Spanish IVA naming remains unchanged.

Semantic discovery preceded inspection and exact-symbol sweeps confirmed the producer and projection sites. Initial focused validation ran the four named test modules: 53 tests passed in 36.60 seconds. Ruff passed across every named Python surface, and basedpyright reported zero errors, warnings, or notes across the same scope. After the finding below was corrected, the current core projection-reference and real DP30302 application proofs ran again: all 12 tests passed in 31.49 seconds. The changed application proof also passed Ruff and basedpyright with zero issues. Repository-wide tests, registry generation, emitted-byte gates, and campaign-wide verification were not run.

## Findings

### module-ordinal-positive-proof | medium | The positive module ordinal assertion is satisfied by an unrelated fact value

- [ ] The initial real DP30302 application test supplied `Decimal("1")` both as module ordinal 1's declared quantity and as every activity fact, then asserted only that `Decimal("1")` appeared somewhere in the collection of non-`None` projected values. The fact projection independently satisfied that assertion, so the test remained green if the module ordinal 1 projection returned `None` or another field was dropped. The separate `fields[2].value is None` assertion correctly proved the missing ordinal 7 behavior, but the required positive annual-Orden ordinal projection was not non-vacuously gated.

### module-ordinal-positive-proof-resolution | medium | Exact ordered field values resolve the proof gap

- [x] Resolved on re-review. The current application proof asserts the complete ordered field-value tuple: the real activity-specific IAE epigraph, module ordinal 1 as `Decimal("1")`, absent module ordinal 7 as `None`, and the independent fact as `Decimal("1")`. This assertion identifies each projection position, so neither the fact nor another field can mask a missing or misrouted module value. The 12 focused core and application cases pass on the live tree. The original open task above is closed by this resolution entry.

No unresolved critical, high, medium, or low findings remain. The distinct taxpayer producer resolves `snapshot.taxpayer_tax_id`, the presenter producer remains separate, the resolver is both structurally and dynamically exhaustive, `module_order` is an exact integer constrained to 1 through 7, canonical row validation precedes ordinal indexing, higher ordinals return `None`, and the retired projection-address `module_identity` is rejected without an alias or reader. Remaining `module_identity` uses belong to canonical evidence rows whose identity and order are validated against their activity-specific annual Orden, not to the retired projection reference.

## Recommendations

No further S60-specific remediation is required. Retain the exact ordered projection assertion so future ordinal, missing-module, or field-order regressions fail independently rather than being masked by equal values in adjacent activity facts.

Final verdict: approved. The medium proof gap is resolved, the scoped production contract satisfies S60, and the focused behavior and static checks are green within the stated validation boundary.
