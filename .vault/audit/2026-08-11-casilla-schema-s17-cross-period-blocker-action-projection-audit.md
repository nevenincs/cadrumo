---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:32d60a3290bbc70efea0369d366ba28e160508f755a17ccdadaa764c5ab4eae5'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-blocker-spine-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S17 cross-period blocker action projection`

## Scope

Reviewed W02.P06.S17 against the accepted blocker-spine decision, campaign plan, research, and repository quality constraints. Scope was limited to `_cross_period_models.py`, the application-calculations facade, and `test_cross_period_blocker_action_projection.py`. The required contract is one facade-exported, total, import-asserted mapping from every native `CrossPeriodCleanStateBlocker` to an `OperatorActionAxis`, preserving the native blocker rather than replacing it.

## Findings

No actionable S17 findings.

`OPERATOR_ACTION_BY_CROSS_PERIOD_CLEAN_STATE_BLOCKER` is declared beside the native 21-member enum and is typed as `Mapping[CrossPeriodCleanStateBlocker, OperatorActionAxis]`. Its key set is exact and its values partition the native blockers into the accepted operator actions: six prior-obligation or filing-state blockers map to `FILE_PRIOR_PERIOD`; six absent, incomplete, or operator-manual evidence blockers map to `CAPTURE_EXTERNAL_EVIDENCE`; the incomplete verification report maps to `RE_VERIFY`; the duplicate filing, mismatched external record, and observation/revision value divergence map to `RESOLVE_VALUE_DIVERGENCE`; unresolved taxpayer identity maps to `RESOLVE_IDENTITY`; the three group-roster/member-set blockers map to `CONFIRM_GROUP_MEMBERSHIP`; and registry revision divergence maps to `RESOLVE_REVISION_MISMATCH`.

The mapping retains each native blocker as the key and adds the shared action as its projection value, so no native machine code is collapsed or deleted. The module compares the complete mapping key set to the complete native enum at import and raises with the sorted missing native values. The supplied bite removed the `REGISTRY_REVISION_DIVERGENCE` row, made a clean import fail naming `registry_revision_divergence`, restored the row, and returned the import and focused gates to green. This follows the accepted `BLOCKING_REASON_BY_DISCREPANCY_KIND` exemplar rather than introducing a partial fallback.

The application-calculations facade imports and exports the mapping directly. Exact symbol inspection found one mapping declaration, one totality assertion, one facade import, one facade export, and the scoped tests; no compatibility alias, secondary mapping, consumer-side default, or native-enum replacement was introduced.

The tests import the production facade and assert total key coverage, action-axis typing, and one exact representative for every semantic action group. They do not reproduce the full mapping, construct a shadow enum, or use a fake, stub, mock, patch, monkeypatch, skip, or expected-failure construct.

The broader `test_cross_period_clean_state.py` lane currently has eight failures unrelated to S17. Seven stop during pre-verdict justificante fixture construction because `JUST-322-A00000000` violates the uppercase-alphanumeric pattern or `JUST-1T` is shorter than the admitted eight-character minimum. One stops during profile setup because `iva.m303_regime_composition` is not explicitly declared. None reaches clean-state evaluation or reads the new mapping. The current independent result is 22 passed and 8 failed; it is recorded as a broader repository boundary, not an S17 finding.

## Verification

- Fresh semantic discovery located the projection, native enum, tests, and accepted blocker-spine decision before exact inspection.
- Focused S17 tests: 2 passed.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed, with only the existing facade line-ending warning.
- Runtime projection census: 21 native keys; action groups 6 filing, 6 evidence, 3 divergence, 3 group membership, and one each verification, identity, and revision mismatch.
- Facade identity and action typing: passed.
- Exact symbol sweep: one declaration and one public facade route; no duplicate projection.
- Import-totality bite: deleting the registry-revision row failed import naming the missing blocker; restoration passed.
- Prohibited test-construct scan: no hits.
- Broader clean-state module: 22 passed, 8 unrelated fixture/profile setup failures.

## Recommendations

No corrective action is required for S17. Repair the stale justificante CSV strings and explicitly compose the M303 regime in their owning test fixtures before claiming the broader clean-state module green; do not fold those unrelated repairs into this projection step.

Verdict: **PASS.** W02.P06.S17 publishes one total action projection over all 21 native cross-period blockers, preserves native codes, refuses an unmapped future member at import, and introduces no fallback or duplicate authority.
