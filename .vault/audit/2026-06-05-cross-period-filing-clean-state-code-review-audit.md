---
tags:
  - '#audit'
  - '#cross-period-filing-clean-state'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
  - '[[2026-06-05-cross-period-filing-clean-state-research]]'
  - '[[2026-06-05-cross-period-filing-clean-state-reference]]'
---

# `cross-period-filing-clean-state` Code Review

## CROSS-PERIOD-001 | LOW | Grouped dependency proof cannot infer an unstored member roster

`evaluate_cross_period_clean_state` now detects `per_grupo_member` requirements and blocks when no member observations exist. It also compares observed member totals against the persisted aggregate calculation revision when member observations are present. The current domain surface does not expose a declarative expected-member roster for a target grupo filing period, so the proof cannot independently prove that every legal member was captured; it can only prove that the captured member observations are clean, filed, AEAT-accepted, externally evidenced, and internally reconciled. This is a modelling limitation, not a regression in the implemented guard. Future registry/profile work should add an explicit grupo membership calendar if legal completeness must be proven beyond captured source observations.

## CROSS-PERIOD-002 | INFO | No critical or high findings in the filing-grade guard

The review found the filing-grade guard wired through verification, export, and filing using the calculation package export surface and domain package reexports. Preview calculation remains permissive, while verification records blocking findings and export/filing raise `ModeloCrossPeriodCleanStateError` when required prior filings are missing, unaccepted by AEAT, lacking external evidence, unreconciled against local calculation values, or missing complete verification evidence.

## CROSS-PERIOD-003 | LOW | Workflow expected-member input is not yet profile-derived

The S37 backend proof accepts an explicit `CrossPeriodExpectedMemberSet` and blocks missing, incomplete, or unexpected member fan-in evidence. S38 verifies the Modelo 353 filing workflow can receive that expected roster and refuses incomplete `353<-322` fan-in. The remaining state-model edge is that no persisted profile/calendar roster surface exists yet for grupo-de-entidades members, so callers must provide the expected member set explicitly until that roster source is added.

## CROSS-PERIOD-004 | LOW | Modelo action decomposition temporarily broke clean-state test imports

During the S32-S35 validation pass, the Modelo action decomposition had moved action error classes to `_action_errors` while stale registry qualnames and missing `_actions` reexports left the clean-state workflow test unable to import. The error-code registry was aligned to `_action_errors`, and `_actions` now reexports the moved action errors and work-lifecycle functions expected by the public `aeat.application.modelo` package surface. Focused workflow tests and lint passed after the repair.

## CROSS-PERIOD-005 | INFO | Current S31 and W04.P10 review found no blocking findings

Reviewed the current justificante-grade clean-state gate, repair diagnostics, Modelo action reexports, and focused tests after the S31 and W04.P10 changes. No critical, high, or medium findings were found locally. The focused lint gate, package import contract check, plan check, and combined clean-state pytest gate passed. A read-only review subagent was started but did not finish within the verification window and was shut down without findings being returned.

## CROSS-PERIOD-006 | INFO | Final doctor failure is outside this feature

The W04.P11 gate refreshed the cross-period feature index and removed this plan's generated annotation warning. `vaultspec-core doctor` still exits non-zero because `live-censo-calendar-reconciliation` has a plan without ADR or research references, plus unrelated warnings for `codebase-monolith-decomposition`. No remaining doctor warning or error names `cross-period-filing-clean-state`.

## CROSS-PERIOD-007 | INFO | Final focused gates found no cross-period blockers

Reviewed the final W04.P11 evidence after closing S36 and S40-S43. Registry cross-dependency tests passed with 47 tests, focused calculation clean-state tests passed with 16 tests, and Modelo workflow clean-state tests passed with 20 tests. No critical, high, or medium findings were found in the cross-period feature-local evidence. The only unresolved verification limitation is that the full `application/calculations/tests` folder timed out during an attempted broad run; the focused clean-state calculation gate passed and the timeout is recorded in the S42 exec note.

## CROSS-PERIOD-008 | INFO | Profile-derived grupo roster gap is closed in the current tree

The earlier CROSS-PERIOD-003 finding is superseded by the current profile state surface: `CrossPeriodGroupMemberRoster` is carried on `TaxpayerProfile`, wizard axis parsing accepts group member roster keys, and Modelo verification/export project profile rosters into `CrossPeriodExpectedMemberSet` before evaluating cross-period clean state. Focused real-behavior coverage passed for taxpayer profile modelling, wizard roundtrip parsing, and Modelo clean-state enforcement with 101 tests, and ruff passed on the profile, wizard, verification, export, and enforcement-test files.

## CROSS-PERIOD-009 | INFO | Member-scoped group filing identity is now enforced

Reviewed the W05 member-aware group filing proof after implementation. `ModeloRecord` now carries an optional `member_nif`, preserves legacy non-member filing ids, and enforces one current filing per `(bucket, modelo, year, period, member_nif)` tuple. Clean-state evaluation now checks each expected group member's current filing record, AEAT acceptance, justificante-grade evidence, presented calculation revision, and member observation reconciliation independently. Focused domain and calculation tests passed with 22 tests, Modelo clean-state workflow tests passed with 12 tests, and ruff passed on the edited domain, calculation, and workflow surfaces. Remaining open plan edges are W06 external evidence grounding through import artifacts and W07 operator/full-matrix rollout gates.

## CROSS-PERIOD-010 | HIGH | Evidence matcher does not bind justificante tax identity to member filing identity

The W06 matcher resolves justificante/live-capture evidence by `reference_id` and rejects modelo, ejercicio, or period mismatches, but `_justificante_matches_filing` does not compare the resolved justificante `tax_id` with the filing identity. For member-scoped group dependencies, `ModeloRecord.member_nif` is already available, so a Modelo 322 filing record for member B can point at a persisted justificante for member A with the same modelo/year/period and still clear the clean-state evidence gate. The new tests exercise missing and stale period records, but the member helper seeds every justificante with the same `tax_id`, so this cross-member/cross-taxpayer evidence substitution is not covered. Bind `Justificante.tax_id` to `ModeloRecord.member_nif` when present, and add a real repository test where a member-scoped filing references a same-period justificante for a different NIF and receives `mismatched_external_evidence_record`.

Resolution: `_justificante_matches_filing` now requires `Justificante.tax_id` to equal `ModeloRecord.member_nif` whenever the filing record is member-scoped. `test_cross_period_clean_state_blocks_member_filing_with_wrong_tax_id_justificante` covers the wrong-member receipt case and expects `mismatched_external_evidence_record`. Focused calculation/modelo repair tests passed with 31 tests, and ruff passed on the touched files.

## CROSS-PERIOD-011 | HIGH | Non-member justificante evidence is not bound to taxpayer identity

W06 now requires justificante and live-capture references to resolve to persisted justificante artifacts, and member-scoped clean-state matching compares `Justificante.tax_id` with `ModeloRecord.member_nif`. The non-member path still accepts a same modelo/year/period artifact for any taxpayer: `_justificante_matches_import_target` checks only modelo, ejercicio, and period before `import_external_filing_evidence` stamps `aeat_accepted=True`, and `_justificante_matches_filing` treats `filing.member_nif is None` as sufficient without comparing `Justificante.tax_id` to the active filing taxpayer/profile. A receipt for taxpayer A can therefore be imported into taxpayer B's bucket for the same modelo/year/period and later clear the cross-period clean-state gate if the filed values and observations reconcile. The current tests cover missing objects, stale periods, CSV/live classification, and wrong member NIF, but not a non-member wrong-tax-id justificante. Bind non-member justificante matching to a durable taxpayer identity available at the workflow/import boundary, and add a real repository regression test where a same-period justificante with a different `tax_id` is rejected before import or yields `mismatched_external_evidence_record`.

Resolution: `import_external_filing_evidence` now requires the workflow/profile taxpayer id before accepting justificante-backed evidence (`aeat_justificante_pdf` or `aeat_live_capture`) and rejects artifacts whose `Justificante.tax_id` does not match that expected taxpayer. The Modelo records CLI supplies the active profile tax id when importing external evidence. Cross-period clean-state evaluation now receives the workflow profile tax id from verification, export, and filing gates, and `_justificante_matches_filing` compares non-member justificante evidence against that taxpayer id while retaining `member_nif` precedence for group-member filings. Regression coverage now rejects missing expected tax id, wrong-taxpayer imports, wrong-taxpayer non-member clean-state evidence, and wrong-member group evidence. Final focused verification passed with 88 tests, ruff passed on the touched Python surfaces, and both locale YAML files parsed successfully.

## CROSS-PERIOD-012 | INFO | Final W07 review found no new blocking findings

Reviewed the final W06/W07 delta after adding taxpayer-bound justificante import, profile-taxpayer clean-state matching, period compatibility hardening, and the operator-facing `aeat app modelo work dependencies` inventory. The CLI command uses the same registry inventory and clean-state evaluator as the verification/export/file gates, passes active profile taxpayer identity into the proof, and projects profile group rosters into expected member sets. JSON output is schema-registered under `modelo.work.dependencies` and the UX tests cover both inventory discovery and current blocker output. No critical, high, or medium findings were found in the final feature-local review.

Verification evidence: 88 focused cross-period application/modelo tests passed; 20 Modelo work UX integration tests passed; 88 cross-period calculation-family tests passed; 92 JSON schema conformance tests passed; ruff passed on touched Python surfaces; locale YAML parsing passed; feature index and feature-scoped vault check passed. `vaultspec-core doctor` still reports unrelated pre-existing global vault issues, including the non-standard `live-censo-calendar-reconciliation` exec filename, stale indexes in other features, and historical annotation/schema warnings.
