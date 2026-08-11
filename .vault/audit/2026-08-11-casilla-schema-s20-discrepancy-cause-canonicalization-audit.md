---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:76d7d2c6e77838a7fcb27eccf1297b23ee6ad8107c383d4a995c1300f551e208'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
  - "[[2026-08-10-casilla-schema-blocker-spine-adr]]"
  - "[[2026-08-10-casilla-schema-dead-surface-adr]]"
  - "[[2026-08-10-casilla-schema-research]]"
---
# `casilla-schema` audit: `S20 discrepancy cause canonicalization`

## Scope

Reviewed W02.P06.S20 against the accepted blocker-spine and dead-surface decisions, the campaign plan, research, and repository quality constraints. Scope was limited to the registry verification schema/facade/tests and the application verification schema, verifier, facade, and direct tests. The required contract is destructive reconciliation of the two discrepancy-cause enums into one canonical registry-owned `DiscrepancyCause`, a complete consumer sweep, deletion of the application declaration/export, preservation of the registry-authored lowercase persisted tokens, and no alias, bridge, tolerant hydration, or duplicate authority.

## Findings

No actionable S20 findings.

The survivor choice is architecturally correct. `_schema_verification.py` owns authored `VerificationExpectationDefinition.discrepancy_causes`, its coercion boundary, folded `RegistryVerificationPolicy`, and the lowercase TOML vocabulary. The accepted dead-surface decision schedules the competing `application/verification` package for later adjudication and deletion, so retaining its uppercase enum would move authority into the doomed surface. The survivor is renamed directly from `VerificationDiscrepancyCause` to `DiscrepancyCause` and exported through the registry facade.

The competing application enum class is deleted rather than aliased. `ClassifiedDiscrepancy` imports the registry facade identity directly; the verifier imports that same facade identity; and the application-verification facade removes `DiscrepancyCause` from both its import and `__all__`. Exact source inspection finds one `class DiscrepancyCause` declaration, at the registry owner, and zero `VerificationDiscrepancyCause` references across `src` and `dev`. There is no assignment alias, forwarding export, deprecated spelling, dual coercer, or compatibility fallback.

The wire-token consequence is deliberately destructive and internally consistent. The deleted application enum serialized uppercase values, while the registry authority persists lowercase tokens. `ClassifiedDiscrepancy` now serializes the canonical enum as `correctness_divergence` and the registry model continues to reject uppercase `ROUNDING`. All four member names remain unchanged while their single admitted values are `extraction_unreliable`, `unmodelled_rule`, `rounding`, and `correctness_divergence`. No code accepts or translates the superseded uppercase tokens.

Every scoped consumer is retargeted to the canonical identity: registry expectation hydration/folding, application verdict schema, verification classifier/status derivation, application helper tests, and registry schema/fold tests. The later S30 package deletion remains unblocked because S20 removes only the duplicated vocabulary while leaving the dead package's other semantics available for its required S29 adjudication.

The structural regression parses real source files and asserts the sole declaration path, canonical `__module__`, application facade absence, and lowercase token. It imports production symbols and does not implement classification business logic. Existing helper tests still exercise the real classifier precedence and status derivation. No fake, stub, mock, patch, monkeypatch, skip, expected-failure, or mirrored enum exists in the reviewed tests.

Shared worktree ownership was preserved. The unrelated indentation-only change in `application/verification/tests/test_verify.py` was not used as S20 evidence, and the broader pre-existing registry-test formatting/line-ending WIP was not treated as part of the canonicalization. The semantic S20 hunks in the pre-dirty registry schema test are limited to the import and exact enum assertions.

## Verification

- Fresh semantic discovery located both competing homes, their consumers, the accepted blocker-spine decision, and the scheduled dead-package deletion before exact inspection.
- Exact obsolete-name sweep over `src` and `dev`: zero `VerificationDiscrepancyCause` hits.
- Exact declaration sweep: one `class DiscrepancyCause`, owned by `_schema_verification.py`.
- Runtime identity: registry facade resolves directly to the owner; application-verification facade has no `DiscrepancyCause` attribute.
- Runtime member census: exactly four canonical members with lowercase values.
- Real application-schema JSON probe: `CORRECTNESS_DIVERGENCE` serializes as `correctness_divergence`.
- Registry refusal test retains uppercase `ROUNDING` as invalid; no uppercase compatibility admission exists.
- Independent owning lane: 83 passed and one transient concurrent registry-fingerprint refusal; the exact refused node passed on retry.
- Owner's full application-verification suite: 37 passed.
- Scoped Ruff: passed.
- Scoped strict BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed, with only existing line-ending warnings.
- Prohibited test-construct scan: no hits.

## Recommendations

No corrective action is required for S20. Preserve the destructive lowercase wire cutover and do not reintroduce an application alias during S29/S30 adjudication. S30 should delete the remaining application-verification package only after its per-capability S29 disposition, as already required by the dead-surface decision.

Verdict: **PASS.** W02.P06.S20 leaves exactly one registry-owned discrepancy-cause enum, retargets all current consumers, removes the losing declaration and facade export, deliberately standardizes the wire on lowercase registry tokens, and introduces no compatibility or duplicate authority.
