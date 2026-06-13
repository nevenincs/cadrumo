---
tags:
  - '#audit'
  - '#calculation-correctness-campaign'
date: '2026-06-13'
modified: '2026-06-13'
related:
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-adr]]"
  - "[[2026-06-13-modelo-130-pagos-fraccionados-carry-plan]]"
  - "[[2026-06-13-first-filer-attestation-adr]]"
---




# `calculation-correctness-campaign` audit: `calculation-correctness campaign close honesty review`

## Scope

Mandated campaign-close honesty review (per the `aeat-campaign-close-honesty-review` rule) of the calculation-correctness plus blocker-sweep campaign on the `chore/eliminate-shims` branch. Reviewed as a fresh inheritor, with deep substance verification of the pieces NOT yet individually reviewed: the Modelo 130 casilla-05 pagos-fraccionados carry (the commits flipping casilla 05 to a bound carry, the casilla-16 not-captured tolerance, the verification gates, the verify fixture, and the P01 expanding-span selector), the verify-findings-onto-notices routing, the in-memory-bytes reconcile (temp-file elimination), the M130 calendar applicability surfacing, and the cross-period provenance gate. The M303 Stage-2 and first-filer-attestation features carried dedicated PASS reviews and were not re-litigated; the first-filer axis was checked only where the M130 carry couples to it.

Every touched test surface was run sequentially (no `xdist`, `-p no:cacheprovider`) and observed green at `HEAD`. The campaign-owned test directories collect clean. The single registry-tests collection error (profile-key registration ordering on the M100 registry test) reproduces in isolation, was not touched by this campaign, and is owned by a peer surface; per `full-tree-gate-must-distinguish-owner` it is attributed there, not to this campaign.

## Findings

### Confirmed correct (the load-bearing money path is sound)

The M130 casilla-05 carry was verified hard because it touches money owed, and it holds up on every axis the brief named.

The casilla-05 value is exactly the AEAT identity (the sum of per-quarter `max(0, prior 07_q)` minus the sum of prior `16_q`) over the same-ejercicio prior quarters. The positive-part rule is applied PER QUARTER before summing in `_aggregate_prior_pagos_fraccionados` (a negative prior 07 contributes zero, not its negative value), and the casilla-16 minoración is subtracted as a sum over the same quarters. The per-anchor value list preserves quarter pairing in `source_casillas` order (07_q, 16_q, 07_q, 16_q, and so on) because the resolver iterates anchors then source ids in order, and the op slices that grouping with an explicit modulo-group-size guard. The op refuses anything but exactly two source casillas.

The accumulation-identity gate is genuinely NON-tautological. The oracle helper re-expresses the AEAT identity by hand (a different code path than the span binding), the fixture includes a NEGATIVE prior 07 and a NON-ZERO prior 16, and the test pins the expected literal (860) plus the two regression failure modes (raw-sum-07 would give 710; dropped-minus-16 would give 1000). A binding that skipped the per-quarter max-0 or dropped the minoración fails loudly.

The first-quarter / alta-quarter empty span yields casilla 05 = 0 as null-not-error (absent-by-design, mirroring the casilla-15 1T path), and it binds to the SHARED first-filer activity-start axis, not a divergent one. This was verified in code, not just asserted: the carry registers as a direct `previous_filing` binding, so its prior-quarter requirements surface through `cross_period_dependency_requirements`, which feeds `partition_cross_period_requirements_by_activity_start` and `_period_strictly_before_activity_start`. A dedicated test drives a 2T-alta filer through `evaluate_cross_period_clean_state` and asserts the carry binding id appears in the suppressed-pre-activity-dependency origins, proving the suppression routes through the shared partition rather than a re-derived intersection inside the selector. The originally-planned in-selector intersection was deliberately NOT built; the exec record for that step documents the deviation and the safer shared-axis binding.

The casilla-16 not-captured advisory correctly distinguishes "filed 0" from "not captured". The discriminator is key presence in the observation's `casilla_values` mapping (built only from persisted observations, so a never-observed casilla is genuinely absent): a prior filing that declared casilla 16 = 0 has the key and is a silent no-op, while a prior filing carrying casilla 07 but no casilla-16 key fires the non-blocking `prior_payment_minoracion_not_captured` advisory naming the gap. The minoración is never silently dropped (the carry treats absent-16 as zero AND surfaces the gap), satisfying `no-silent-under-declaration`. Legal grounding is present: the binding and casilla `source_citations` carry the verbatim AEAT instrucciones `required_text`, and the ADR pins both terms. No tautological tests and no new type escapes in the touched modules.

verify-TASK-A (verify findings onto notices) is sound for the machine-consumer concern the brief raised: a not-granted (blocked) verify carries blocking findings, which project to at least one WARNING notice, so the envelope `status` resolves to `warning` (non-success) in lock-step with the exit-1. A machine consumer can no longer read a blocked verify as success. The blocking-vs-advisory distinction survives on `Notice.context` (`severity`, `kind`, plus `legal_refs` and `source_refs`), so it stays machine-distinguishable. The domain invariant guarantees a granted report can carry only WARNING findings (never BLOCKING), so the grant / exit / status relation is internally consistent.

The temp-file elimination is real and proven. `_materialized_capture_pdf` and all `tempfile` primitives are gone from the justificante reconcile path; decrypted bytes flow from the encrypted snapshot through `parse_justificante_bytes` and `modelo_reconcile_bytes` in process memory only. The disk-quiescence test uses two independent detectors (tripwires on every `tempfile` allocation primitive, plus a before/after snapshot of the process temp dir) and asserts the real reconcile verdict is `MATCHES`, so the path actually executes. This is a legitimate tripwire (a negative assertion that the path is not taken), not a behavior-faking mock. Honours `sensitive-financial-data-secure-storage-only`.

The M130 calendar applicability fix is well-grounded. An undeclared `irpf_estimation_regime` now resolves from the always-definite `uses_objective_estimation_irpf` boolean (default `False`, directa, M130 applicable), grounded in LIRPF art. 16 and RIRPF art. 32 (estimación directa is the default method; módulos is opt-in). M130's required set is `DIRECTA_NORMAL` plus `DIRECTA_SIMPLIFICADA` and M131's is `OBJETIVA`, so the boolean default lands in M130 and outside M131: the two stay mutually exclusive and a non-owing profile gets neither. The directa-normal-vs-simplificada distinction is immaterial to applicability, so the default's choice of `DIRECTA_NORMAL` for an undeclared-but-directa profile is harmless.

The cross-period provenance gate, the P04 continuity / parity gates, the validate-previous-filing-sources empty-span coverage gate, and the P01 selector unit test all pass at `HEAD` and are non-tautological (independent anchor enumeration, real encrypted-SQLite repositories, real registry authority).

### LOW-1 — plan checkboxes diverge from shipped reality (P01 done-but-unchecked, no P01 exec records)

Pathway: vault closure honesty. Location: plan steps `P01.S01` through `P01.S03`. The expanding-span selector mode, its mutual-exclusion validation, and its unit test are implemented, committed, and passing at `HEAD` (landed in the commit the brief lists as the already-committed P01 selector), yet the three P01 step checkboxes are unchecked and the feature's exec folder carries NO `P01` exec records (only `P02` through `P04`). Per `plan-closure-requires-exec-records`, a step checkbox is operator-facing truth only when backed by an exec record; here the inverse holds, real and tested work is invisible in the plan. This is a tracking-honesty gap, not a code defect: the code is correct and verified. Remediation: author the three missing `P01` exec records (or one consolidated record naming the selector commit) and check `P01.S01` through `P01.S03`, OR record in this audit why P01 is a deferred carry-forward; then rebuild the feature index. No code change required.

### LOW-2 — stale plan step text vs shipped mechanism (acceptable; reconciled in exec records)

Pathway: vault plan-vs-implementation drift. Location: plan steps `P02.S04` (says "aggregation op sum", "raw" anchors), `P02.S05` (says author a "casilla 05 registry formula"), and `P03.S08` (says intersect "in the selector"). The shipped implementation uses a dedicated `prior_pagos_fraccionados` aggregation op (not `op = sum` plus a registry formula), and the activity-start suppression lives in the application-layer shared partition (not a selector intersection). Each deviation IS documented in its corresponding exec record with a stated rationale, and the shipped mechanism is the safer and cleaner one (single auditable op; shared first-filer axis with no divergent intersection). This is acceptable per the documented-deviation pattern; the only residual is that the plan body's literal step text was never reconciled to match. Remediation: optional, when authoring the P01 exec records note the P02 / P03 mechanism deviations are intentional so a future reader does not mistake the stale plan prose for a gap.

### LOW-3 — leftover template scaffolding rows in the plan body

Pathway: vault hygiene. Location: the plan's wave / phase scaffolding carries unfilled template remnants (a display-path placeholder and `P02.S01` / `P02.S02` "imperative-verb action; path/to/file" template rows). These are not real steps. Remediation: remove via the `vaultspec-core vault plan` CLI verbs (structure-first discipline), not by hand-editing the markdown.

### LOW-4 — verification-report-notices parameter is untyped

Pathway: type-surface consistency. Location: `verification_report_notices` in the CLI rendering module. The `report` parameter has no annotation. This follows the established loose local convention (`verification_report_payload` and `verification_report_lines` are likewise untyped), so it introduces no NEW escape, but the trio would benefit from a `VerificationReport` annotation. Remediation: optional, annotate all three sibling helpers in one pass; out of scope for this campaign.

## Recommendations

- Status: PASS. No Critical or High findings. The load-bearing money path (M130 casilla-05 carry) is correct, non-tautologically tested, legally grounded, and correctly coupled to the shared first-filer activity-start axis. verify-TASK-A cannot mislead a machine consumer into reading a blocked verify as success. The temp-file elimination is real and proven. The calendar fix is well-grounded. No type escapes, no tautological tests, and no buried peer-WIP absorptions were found.
- Cross-commit absorptions are clean. The absorbed peer WIP (the `_file_flow_support` test-helper hoist fixing an `UnboundLocalError`, the deadlines `conftest.py` wizard-catalogue import side-effect restoration, the `emit_help_text` re-export promotion, and the in-memory bytes refactor) is all test-only or boundary-hygiene change, each documented in its commit message, none burying a behavioral problem. The sibling mark-complete cross-period refuse-guard was correctly left out as uncommitted peer WIP.
- Track LOW-1 as a follow-up Step (author the missing P01 exec records / check the P01 boxes, or record P01 as a deferred carry-forward). This is the only actionable item and it is a vault-tracking gap, not a code defect: it does not block merge but should close before the campaign is declared structurally complete.
- LOW-2, LOW-3, and LOW-4 are optional nits that can ride the P01 exec-record follow-up or a later hygiene pass.

## Codification candidates

None. Every constraint these findings touch is already codified: the casilla-05 carry's correctness disciplines are covered by `no-tautological-calculation-tests`, `no-silent-under-declaration`, `registry-calculation-legal-grounding`, and `carried-observations-stamp-their-revision`; the closure-honesty gap is covered by `plan-closure-requires-exec-records`; the notices-channel contract by `cli-notices-are-the-only-diagnostic-channel`; the bytes-not-temp-file invariant by `sensitive-financial-data-secure-storage-only`. The findings are applications of existing rules, not new durable cross-session lessons.
