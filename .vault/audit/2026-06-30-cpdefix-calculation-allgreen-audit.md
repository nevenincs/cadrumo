---
tags:
  - '#audit'
  - '#cpdefix-calculation-allgreen'
date: '2026-06-30'
modified: '2026-06-30'
related: []
---

# `cpdefix-calculation-allgreen` audit: calculation capability checkpoint

## Scope

This checkpoint records the calculation-adjacent verification campaign run on
2026-06-30 after the cpdefix follow-up work. The reviewed scope includes the
application modelo, application calculations, aggregation, registry, CLI modelo,
and declaration parser gates that were exercised during the closeout.

This is not a full-tree all-green certification. The full Vaultspec vault check
still reports pre-existing vault-wide documentation hygiene issues outside this
campaign.

## Findings

### calculation-gates | low | calculation capability gates passed

The closeout application gate passed:
`uv run --no-sync pytest src/aeat/application/modelo/tests src/aeat/application/calculations/tests src/aeat/application/aggregation/tests -q --tb=short`
reported 1575 passing tests on re-run during this audit update. The registry gate passed:
`uv run --no-sync pytest src/aeat/domain/calculations/registry/tests -q --tb=short`
reported 3475 passing tests on re-run during this audit update. The declaration
adapter gate passed:
`uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/tests -q --tb=short`
reported 218 passing tests after the Modelo 130 parser-boundary split. The
targeted registry parity/reviewability check passed:
`uv run --no-sync pytest -q --tb=short src/aeat/domain/calculations/registry/tests/test_formula_modelo_registry_parity.py src/aeat/domain/calculations/registry/tests/test_modelo_parity_coverage.py src/aeat/domain/calculations/registry/tests/test_registry_reviewability.py`
reported 6 passing tests.

### persona-risk-verifiers | low | testimonial residuals are covered by focused gates

The persona closeout found three residual risks that needed live verification
instead of assumption. Taller Norte's first-period Modelo 303 compensation path
is covered by `test_first_iva_period_m303_1t_uses_wallet_first_period_zero`,
`test_existing_activity_m303_1t_missing_prior_filing_blocks_wallet_zero`, and
`test_grounded_first_period_zero_decision_feeds_real_modelo_303_engine_and_lifecycle_gate`;
all passed. The gestor same-signature ledger twin import and cross-profile
refusal risks are covered by focused ledger/profile tests; the combined verifier
reported 36 passing integration tests after the test-helper drift below was
repaired, and the full ledger import UX file reported 11 passing integration
tests.

### test-helper-drift | low | ledger import UX helper used a retired profile id shape

The focused ledger/profile verifier initially exposed a setup error in
`src/aeat/entrypoints/cli/tests/_ledger_validation_support.py`: the helper used
`tester` as both label and profile id, but current profile registration requires
a UUIDv4 bucket/profile id. The helper now uses a stable UUIDv4 id and preserves
`tester` as the display label. The worker grounded the change with
`vaultspec-rag` before editing.

### review-scope | medium | full-tree and artifact-completeness remain unclaimed

An independent code-review pass found no blocking calculation findings and
confirmed that the profile-readiness work preserved the real readiness gate
rather than bypassing it. The review also confirmed that M115 and M210
completeness changes are consistent with their registry closure surfaces.
However, the claim remains scoped: the campaign does not certify full-tree
all-green, Vaultspec vault-wide cleanliness, or complete persona replay
artifact hygiene.

### persona-artifacts | low | transcript and final-summary coverage is mixed

The persona closeout inspection found no additional code-fixer dispatch clearly
required from `tmp/personas`. Canonical narrative testimonials for older
harnessed campaigns live under `.agents/testimonials/<slug>.md`, while many
`tmp/personas` directories are storage roots or scratch regression logs rather
than transcript stores. Several storage roots still lack a local transcript or
final-summary-like closeout artifact, so artifact hygiene remains separate from
the calculation gates that passed in this checkpoint.

## Recommendations

Use the green gates above for the scoped calculation-capability claim. Keep any
broader full-tree, Vaultspec-clean, or persona-artifact-complete claim open until
those separate surfaces are repaired and verified with their own gates.
