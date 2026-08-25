---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e3772eaddf1163ed5e3c0e814daf7fe8bd0764a809898f33e4aa4465999c3740'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-W04-P07-S26]]"
---
# `cli-action-envelope-hardening` audit: `S26 canonical action-chain closure`

## Scope

Independently audited S26 after the accepted action-envelope ADR: verify and file must expose precondition-driven action chains or declared no-action outcomes, localize every operator-facing message, and preserve audit history without reconstructing a command from a persisted finding.

## Findings

### canonical-home-fixed-point | low | Application verdicts remain the single action authority

Semantic discovery found the accepted campaign ADR, the shared `require_revision_parent_active` guard, and the shared `verification_report_payload` projector. Targeted `rg` and the AST authority test confirmed that the CLI delegates continuation selection rather than rebuilding actions, translation fallbacks, or raw command strings. The AST proof passed 1 test in 0.80 seconds.

### discarded-parent-ordering | low | Verify and file refuse before every bypass path

The review required proof beyond an already-verified no-op. The direct lifecycle suite builds real calculated and verified state, discards its parent, then proves draft verify refusal, verified verify refusal before idempotence, and file refusal without catalogue mutation. The suite passed 3 tests in 17.84 seconds. The terminal verdict carries canonical condition identity and persisted-state provenance with no action rather than an invented continuation.

### fixture-grounding | low | The readiness fixture now satisfies real verification prerequisites

Initial direct preparation exposed actual cross-period dependency and activity-start findings, followed by a schema-invalid justificante reference. The repair used the established file-flow fixture path, a real taxpayer activity start, and a domain-valid CSV reference. It did not bypass verification gates or introduce a fake repository. The resulting report is granted and the persisted revision state is asserted before discarded-parent behavior is exercised.

### selector-envelope-and-locales | low | Address absence is explicit and locale-complete

The selector matrix passed 2 tests in 58.44 seconds across en, es, ca, and hu. Natural and exact missing targets expose the declared no-action verdict and its `operator_decision` outcome. The locale verifier passed all four catalogs with ten S26 keys each and identical placeholder shapes; no raw product command is embedded in the localized strings.

### persisted-history-wire-contract | low | Report history serializes a structural null action

The review gap was closed at the production renderer and schema boundary. The persisted report test asserts typed `findings[0].action` is absent and both `view` and `list` JSON payloads contain `action: null`. The report renderer module passed 6 tests in 14.51 seconds. Live report projections continue to expose only an application-paired verdict, not a report-derived command.

### focused-quality-evidence | low | The S26 surface is clean under collected gates

The live common-action resolver suite passed 14 tests in 38.08 seconds. Targeted report-view typing produced zero diagnostics. Scoped Ruff formatting and lint checks passed, and the scoped diff check was clean. An installed-console run against isolated storage previously confirmed natural verify and file absence emit the canonical persisted-state no-action envelope rather than relying on an in-process runner.

### workspace-wide-boundary | low | Broad gates remain non-attributable to S26

Full repository typing and global locale audit were intentionally not used to judge this step because concurrent import and locale churn produces unrelated workspace diagnostics. The focused acceptance evidence above is therefore the claimed boundary; it is not a claim of a green repository-wide gate.

## Recommendations

- Retain the application precondition profile and the shared lifecycle guard as the only sources for verify and file refusal identity, evidence, action, and no-recovery outcome.
- Keep persisted report rendering actionless unless the live application pairs the exact finding with a current precondition projection.
- Run the workspace-wide type and locale gates after unrelated concurrent import and locale work settles; do not reinterpret their current global diagnostics as S26 regressions without a path-level reproducer.
