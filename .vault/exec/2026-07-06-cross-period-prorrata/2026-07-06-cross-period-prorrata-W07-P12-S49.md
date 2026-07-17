---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S49'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# run W07 promotion close review

## Scope

- `.vault/audit/2026-07-06-cross-period-prorrata-audit.md`
- `.vault/exec/2026-07-06-cross-period-prorrata/`
- `src/aeat/application/calculations/tests/test_prorrata_regularizacion_oracle.py`
- `src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py`
- `src/aeat/application/modelo/tests/test_verification_m303_prorrata_advisory.py`

## Description

- Re-run `vault plan status` at HEAD and confirm only `W07.P12.S49`
  remains open with no missing exec records.
- Re-ground the W07 promotion surface through semantic search and targeted
  grep before reviewing the selector, registry bindings, resolver, source-mesh
  enrollment, source-kind parity tests, AEAT manual oracle tests, M303 advisory
  behaviour, and bienes-inversion dependency reconciliation.
- Append the S49 close-review section to the existing cross-period prorrata
  audit, preserving the earlier S45 review content already present in that
  audit.
- Record each surfaced close-review item as a formal deferral with blocker and
  follow-up named: M303 casilla 44 target consumption and remaining
  bienes-inversion live resolver work.
- Rebuild the cross-period-prorrata feature index and run the feature,
  frontmatter, and plan gates after the audit update.

## Outcome

S49 is complete as a promotion close review. The source-kind promotion itself is
structurally landed: `prorrata_regularizacion` is enrolled in the live source
mesh and calculation source policy, no longer sits in the deferred source-kind
target set, carries a caller-override carry disposition, and has live resolver
and mesh coverage tied to the bundled AEAT manual oracle.

The review does not declare the product surface closed. The audit formally
defers the remaining work because the live resolver value is not yet consumed
by Modelo 303 casilla `[44]`, and `BIENES_INVERSION_REGULARIZACION` still needs
its own governed live resolver and target proof. The Modelo 390 annual binding
is covered by the live source-mesh test that resolves it from stamped Modelo 303
source-period observations.

Verification passed: focused ruff over the changed source and tests, 36 focused
prorrata/source-kind pytest tests, cross-period-prorrata feature index rebuild,
frontmatter check, feature check, plan check, and plan status.

## Notes

No destructive git operations were run. No new source kind, resolver convention,
validator convention, plan, or ADR was introduced. The existing audit file
already carried S45 review edits; S49 was appended after them rather than
rewriting settled content.
