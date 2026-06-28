---
tags:
  - '#plan'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
tier: L2
related:
  - '[[2026-06-19-crossperiod-filing-deadlock-adr]]'
  - '[[2026-06-19-crossperiod-filing-deadlock-research]]'
---








# `crossperiod-filing-deadlock` plan

### Phase `P01` - Decision A - admit late local work file for closed-window targets

Resolve the FILE-gate obligation schedule in the target period's filing year so a genuinely-existing but closed-window obligation is admitted as a late LOCAL filing (extemporanea, con recargo), seeding the next period's cross-period carry observation; a target that never had an obligation still refuses NO_PENDING_OBLIGATION.



- [x] `P01.S01` - Re-scope the FILE-gate obligation schedule to the target period's filing year for an explicit FILE target, leaving the as-of-today projection on today.year; `src/aeat/application/workflow/_engine.py`.
- [x] `P01.S02` - Guard the target-year compute against NoDeadlineWindowsError so a year with no registry windows degrades to NO_PENDING_OBLIGATION rather than UNHANDLED_EXCEPTION; `src/aeat/application/workflow/_engine.py`.
- [x] `P01.S03` - Admit an explicitly-targeted overdue obligation as a late local filing, stamping the extemporanea marker on the COMPUTING_DEADLINES step details instead of aborting DEADLINE_PASSED; `src/aeat/application/workflow/_engine.py`.
- [x] `P01.S04` - Skip the submission filing-window preflight for the local FILE purpose alongside VERIFY; `src/aeat/application/workflow/_engine.py`.
- [x] `P01.S05` - Update the workflow engine tests to Decision A semantics (targeted overdue admitted, closed-window FILE no longer aborts DEADLINE_PASSED); `src/aeat/application/workflow/tests/test_engine.py`.

### Phase `P02` - Decision B - within-year local-chain export with a disclosing advisory

Admit a same-filing-year app_filing local chain whose only blockers are the official-evidence delta to verify and export, clearing those blockers and surfacing a non-blocking advisory; cross-year priors, operator_manual sources, and value/revision divergence stay blocking.

- [x] `P02.S06` - Add the non_official_local_chain_advisory facet on CrossPeriodDependencyEvidence and the has_non_official_local_chain_advisory verdict property; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `P02.S07` - Add _relax_same_year_local_chain admitting a same-year app_filing dependency whose blockers are a subset of the official-evidence-delta set, clearing those blockers and stamping the advisory facet; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `P02.S08` - Emit the non-blocking WARNING non-official-local-chain advisory finding from the cross-period clean-state findings builder; `src/aeat/application/modelo/_verification_actions.py`.
- [x] `P02.S09` - Attach cross-period dependency legal grounding (LGT art 119/120, LIVA art 99 for compensacion, RGAT art 9 for activity-start) to every cross-period and iva-wallet finding; `src/aeat/application/modelo/_verification_actions.py`.
- [x] `P02.S10` - Reconcile the local cross-period carry tests to admit-with-advisory for same-year chains while keeping the cross-year prior blocking and preserving the app_filing-non-official invariant; `src/aeat/application/modelo/tests/test_local_cross_period_carry.py`.
- [x] `P02.S11` - Ratchet the owned _cross_period_clean_state.py SPLIT-CANDIDATE size budget from 1265 to 1300 for the feature addition; `src/aeat/tests/test_codebase_size_budgets.py`.

## Description

Backfill plan for the cross-period filing deadlock remediation (campaign finding C0). The authorizing ADR decomposes the deadlock into two cooperating gates and resolves each with a bounded change; the research frames the campaign mandate (make every correctly-computed filing reachable, replacing silent or over-strict refusals with evidence-disclosing, locally-completable paths). The engine arithmetic for every cross-period aggregation (M130 quarter-to-quarter pago-fraccionado carry, M303 1T-to-2T IVA compensacion carry, M100 M130-fold-in) is already correct; the deadlock made it operationally unreachable for any late filing or prior-year reconstruction, so a taxpayer could export only the first period of a chain.

Phase `P01` (Decision A) corrects the literal year-derivation bug in the FILE-gate obligation schedule: an explicit FILE target resolves its obligation in the target period's filing year, so a genuinely-existing but closed-window obligation is recognised as OVERDUE and admitted as a late LOCAL `work file` (extemporanea, con recargo) that persists the `app_filing` carry observation the next period reads. `NO_PENDING_OBLIGATION` still refuses a target for which no obligation ever existed; the as-of-today projection keeps its `today.year` basis, preserving the single-producer invariant.

Phase `P02` (Decision B, same-year scope) admits a same-filing-year `app_filing` local chain whose only remaining blockers are the official-evidence delta to verify and export, clearing those blockers and surfacing a non-blocking WARNING advisory that discloses the non-official basis (`no-silent-under-declaration`). The scope is deliberately narrow: a cross-YEAR non-official prior still blocks (the anti-laundering gate `local-filed-observations-are-non-official-evidence` was authored to protect), `operator_manual` sources and value/revision divergence stay blocking, the `app_filing` source kind stays out of `_OFFICIAL_SOURCE_KINDS`, and only the LOCAL verify/export path is relaxed, never an AEAT-acceptance assertion.

This plan is a retroactive backfill: the implementation landed on `chore/eliminate-shims` in commits `6e635f566` (Decision A) and `84add274d` (Decision B) before this plan was authored. Each Step's execution record names the landing commit; the companion code-review audit is the closure evidence.

## Steps







## Parallelization

Phase `P01` (Decision A) and Phase `P02` (Decision B) are end-to-end independent in code but ordered in effect: Decision A alone unblocks the carry value while leaving the dependent verify blocked on official evidence, and Decision B alone has nothing to be clean about because no observation is ever written. Neither phase alone delivers the end-to-end exports the campaign demands, so both are required for the feature. Within `P01`, steps `S01`-`S04` all touch `_engine.py` and were landed in one atomic commit; `S05` (the test update) rides the same commit. Within `P02`, steps `S06`-`S07` (clean-state facet plus relaxation), `S08`-`S09` (advisory emission plus legal grounding), `S10` (test reconciliation), and `S11` (size-budget ratchet) were landed in one atomic commit. The two phases landed as two separate commits and could in principle have been split across two sessions; in practice Decision B was authored after Decision A's reds were confirmed green.

## Verification

The plan is complete when every Step is closed and the C0 test surface is green. Mission success criteria, each a verifiable check:

- Decision A: `src/aeat/application/workflow/tests/test_engine.py` is 47/47 green, including `test_gate_aborts_when_projection_lacks_the_target` (never-existing obligation still refuses `NO_PENDING_OBLIGATION`), `test_deadline_passed_via_run_for_period`, and `test_verify_reaches_done_for_a_closed_filing_window`.
- Decision B: `src/aeat/application/modelo/tests/test_local_cross_period_carry.py` is 5/5 green, asserting (a) a same-year `app_filing` chain is admitted with the non-official-local-chain advisory, (b) a cross-year non-official prior is NOT relaxed and still blocks, and (c) `app_filing` stays absent from `_OFFICIAL_SOURCE_KINDS`.
- Cross-period clean-state boundary pins: `src/aeat/application/calculations/tests/test_cross_period_clean_state.py` is green, holding `operator_manual`, value/revision divergence, missing observation/filing, and group-member gaps BLOCKING.
- End-to-end reachability: `src/aeat/application/modelo/tests/test_e2e_ledger_m130_quarters_to_m100_annual.py` drives the M130 1T-to-4T chain through the real `work file` path and folds into M100, and `test_verify_gate_blocks_chain_carrying_non_official_prior_year` (the cross-year anti-laundering canary) stays green.
- Owned size-budget ratchet for `_cross_period_clean_state.py` (SPLIT-CANDIDATE) is satisfied at 1300.
- The companion code-review audit signs off the safety boundary (the locally-clean vs genuinely-unclean partition) and confirms no official-evidence laundering.

Known external state: at the time of authoring, 54 reds in the C0-adjacent test files are caused entirely by an unrelated peer campaign's in-flight registry edit (the M100/2024 mixed-income construct `renta-2024-mini-model-actividades-economicas-directa` and its new ledger bindings `0021`-`0025`, with an incomplete construct legal-grounding sweep). Those reds are registry-load failures owned by the mixed-income campaign, not this feature's surface; the C0 logic surfaces (`test_engine.py`, `test_local_cross_period_carry.py`) carry zero failures. See the companion audit for the owner-distinguished triage.
