---
tags:
  - '#audit'
  - '#arch-remediation-modelo-surface'
date: '2026-07-04'
modified: '2026-07-17'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
  - "[[2026-07-02-arch-remediation-modelo-surface-adr]]"
---

# `arch-remediation-modelo-surface` audit: `campaign close honesty review`

## Scope

Fresh-context campaign-close honesty review for the modelo-surface campaign
after `vaultspec-core vault plan status
2026-07-02-arch-remediation-modelo-surface-plan` reported 21 of 21 steps
complete. The review treated the plan as newly inherited: re-read the plan and
ADR, checked the exec record set, inspected live source for the four promised
representation moves, and ran focused real gates for the typed unresolved
outcome, M100 parameter relocation, iva-wallet ownership declaration,
precedence ladder, and generic-module ratchet.

Evidence used:

- `vaultspec-core vault plan status
  2026-07-02-arch-remediation-modelo-surface-plan`: 21 of 21 complete.
- Direct grep found no remaining `M210_RATE_SENTINELS`,
  `_rewrite_m210_sentinels`, or `_M100_IMPUTATION_YEAR_DAYS` in the live
  implementation surface.
- Direct source inspection confirmed `RegistryCalculationUnresolvedOutcome`
  consumption in `src/aeat/application/modelo/_verification_actions.py`, the
  shared iva-wallet ownership declaration in
  `src/aeat/domain/calculations/registry/_validate_relation_sources.py`, the
  same declaration consumed by
  `src/aeat/application/modelo/_calculation_actions.py`, and
  `CALLER_OVERRIDE_PRECEDENCE_LADDER` driving the aggregation guard shape.
- `uv run --no-sync pytest -q
  src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py
  src/aeat/application/calculations/tests/test_modelo_210_irnr_continuity.py
  src/aeat/application/aggregation/tests/test_precedence_ladder_conformance.py
  src/aeat/tests/test_generic_module_modelo_carveouts.py
  src/aeat/application/modelo/tests/test_iva_wallet_decision_binding.py
  src/aeat/application/modelo/tests/test_local_cross_period_carry.py`: 59
  passed.
- `uv run --no-sync pytest -q
  src/aeat/domain/calculations/registry/tests/test_modelo_100_imputed_real_estate_art85.py`:
  5 passed.

## Findings

### campaign-close-honesty-review | low | Structural closure is supported

No missing modelo-surface implementation item was found. The plan is fully
checked, all 21 step exec records are present, and the focused gates pass for
the ADR's four moves. The old M210 negative-Decimal sentinel channel and rewrite
shim are gone; the M100 Art.85 year-days value is no longer a generic runtime
constant; iva-wallet ownership is a single shared declaration consumed by both
validator and orchestrator code; the caller-override precedence ladder is
declared data with a conformance test; and the generic-module ratchet is active.

### m210-legal-source-hash-inventory | low | Registry source-hash assertions fail outside this campaign

An intentionally broader M210 registry run surfaced three failing SHA
assertions in `test_modelo_210_registry.py`. The parallel run failed 3 tests and
passed 54; the required sequential rerun of the same three tests also failed,
so this is not the known registry loader-cache race. The live registry legal
metadata now reports `c40939b99cd2091b924a78e0690977a0f7c1f82c734fb0275f1085234c91a21d`,
`b901936072eb6bd8213dd84e9bd493a65d10b652b3b62dbe42228e1094f38074`, and
`a954f18028c83634641e2197b7ca67fc540686f0117bcae69fc96c51bc15ed83` where the
tests expect older hashes. This is formally deferred to the legal/IRNR corpus
hash reconciliation follow-up because it is a registry source-metadata parity
issue, not a modelo-surface representation issue, and fixing it here would
expand the campaign beyond its ADR scope.

## Recommendations

- Treat `arch-remediation-modelo-surface` as closed for Wave 2 after its
  feature index is rebuilt and feature check is clean.
- Add no new modelo-surface steps from this honesty review.
- Route the M210 legal-source hash mismatch to the legal/IRNR corpus hash
  reconciliation follow-up; do not repair it in this campaign.
