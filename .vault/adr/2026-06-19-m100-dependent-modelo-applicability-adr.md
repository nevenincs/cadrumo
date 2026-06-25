---
tags:
  - '#adr'
  - '#m100-dependent-modelo-applicability'
date: '2026-06-19'
modified: '2026-06-19'
related:
  - '[[2026-06-19-m100-dependent-modelo-applicability-research]]'
---
# `m100-dependent-modelo-applicability` adr: `Suppress cross-period dependencies on modelos the taxpayer does not file (C3)` | (**status:** `accepted` — implemented via the grounded `taxpayer_files_source` classification distinction, commit `fd14bdf01`; Option 1's schedule heuristic was reverted)

## Problem Statement

Finding C3 (filing-persona campaign): Modelo 100 is unreachable for a normal salaried/rental taxpayer. M100 declares unconditional cross-period dependencies (bindings + relations, construct `renta-2024-dependent-modelos`) on the withholding/instalment modelos `111`/`115`/`123`/`130`/`131`/`193`. A taxpayer who SUFFERS retenciones (employee, landlord) does not file these — the PAYER does — so the upstream filings are absent and M100 verify hard-blocks on ~33 `cross_period_dependency_unclean` findings. The first-filer pre-activity suppression does not reach them (they are in-activity, same year). Root cause: the registry conflates "retenciones I suffered" (an income fact) with "retenciones I withheld and declared via 111" (a real cross-period filing dependency). See research `2026-06-19-m100-dependent-modelo-applicability-research`.

## Considerations

A wrong suppression here is a silent under-declaration of a regulated return, so the design must (a) suppress ONLY a dependency on a modelo the taxpayer genuinely does not file, (b) surface every suppression explicitly (`no-silent-under-declaration`), and (c) fail closed (never relax on uncertainty). The existing first-filer attestation (ADR 2026-06-13) is the structural precedent: an application-layer partition over the registry-derived requirements, producing a clean, facet-stamped evidence row, grounded in an authoritative profile signal.

## Decision

Adopt **Option 1 (interim)**: suppress a cross-period dependency whose source modelo is NOT in the taxpayer's applicable-modelos set, where that set is the deadline engine's obligation-schedule modelos — its `applies_to` authority for which modelos a profile files. The suppression is an explicit, auditable `modelo_not_applicable_advisory` facet (a clean evidence row, never a silent drop). The applicable set is computed fail-safe: any deadline-engine error yields `None` → NO suppression (the gate stays strict). A modelo the taxpayer DOES file is never suppressed.

**Option 2 (durable, deferred):** split the conflated concept in the registry so retenciones SUFFERED become income-sourced casilla inputs (no cross-period dependency), and only the WITHHELD-and-filed case keeps the 111/115/123/193 dependency, gated by a profile predicate. This needs grounding against the AEAT M100 dictionary (which casillas are payee-retenciones vs payer-declared) and is left for a follow-up.

## Implementation

- `src/aeat/application/calculations/_cross_period_clean_state.py`: `partition_cross_period_requirements_by_modelo_applicability` (origin-agnostic split by an `applicable_source_modelos` set), `_suppressed_modelo_not_applicable_evidence` (clean, advisory-stamped row), the `modelo_not_applicable_advisory` facet + verdict property, and an optional `applicable_source_modelos` param on `evaluate_cross_period_clean_state` (default `None` = no suppression). Commit `944d58b28`.
- `src/aeat/application/modelo/_verification_actions.py` + `_filing_actions.py`: `_applicable_source_modelos(profile, filing_year)` computes the obligation-schedule modelos (fail-safe `None`); verify and file thread it through `_require_cross_period_clean_state` / the verdict helper into the evaluation. Commit `784cc0517`.

## Rationale

The deadline engine's obligation schedule is the project's existing authority for which modelos a profile files; reusing it for suppression keeps the signal grounded rather than inventing a new one. Making the suppression an explicit advisory (not a silent omission) keeps `no-silent-under-declaration` intact and lets an operator catch a wrong suppression. Failing closed on any engine error preserves the gate's strictness. Option 1 unblocks the common employee case immediately; Option 2 resolves the residual dual payee+payer conflation once grounded.

## Consequences

Gains: a normal salaried/rental taxpayer's M100 is reachable (the withholding-modelo deps they never file are scoped out with disclosure); a taxpayer who files those modelos still blocks until they are evidenced. Pitfalls: Option 1 is a heuristic over the obligation schedule — a taxpayer who is BOTH a payee and a payer of the same modelo still keeps the (correct-for-the-payer) dependency while their suffered retenciones come from income data; the conflation is only fully resolved by Option 2. The deadline-engine call adds one schedule computation per verify/file (cached). The suppression is bounded to the modelo-applicability axis and never touches the value-divergence / revision-divergence / operator-manual / official-evidence blockers.

## Safety analysis

Adversarial tests (`src/aeat/application/calculations/tests/test_decision_b_adversarial.py`) prove the boundary: a modelo the taxpayer files is NEVER suppressed (across multiple applicable sets); `None` suppresses nothing (fail-safe); a suppressed row is clean with the explicit advisory facet; and against the real M100 snapshot, an employee (`applicable = {"100"}`) gets 111/115/123/130/131/193 scoped out while a 130-filer keeps 130. No regression across 114 carry/e2e/clean-state/verify/file tests.

## Codification candidates

- **Rule slug:** `cross-period-suppression-must-be-explicit-and-fail-closed`. **Rule:** Any cross-period dependency suppression (pre-activity, modelo-not-applicable, …) MUST be an explicit, auditable facet (never a silent drop), MUST suppress only on a grounded authority (activity-start date, deadline-engine applicability), and MUST fail closed (no suppression) on any uncertainty — never relax the gate on missing data.

## Update — Option 1 reverted; RAG-grounded corrected design

Option 1 (deadline-engine obligation-schedule applicability) was implemented (`944d58b28`+`784cc0517`+`365d7d6a3`) and then **reverted** (`6204ba381`+`0bed90e9f`+`838912782`). The full-tree gate caught that it OVER-SUPPRESSES: `test_cross_period_clean_state_enforcement.py::test_file_refuses_declared_cross_period_modelos_without_clean_sources[180/190/193/200/202]` regressed because the obligation schedule is not a complete "which modelos does this taxpayer file" signal — it omits modelos that are legitimately-enforced cross-period sources, so the suppression scoped out deps that MUST block. A `vaultspec-rag` semantic pass then surfaced the correct, grounded surface I had missed.

### The grounded mechanism (registry `dependency_classifications`)

The registry already classifies each M100 cross-period dependency under `dependency_classifications` with a `treatment` field (M100/2024: 111/115/123/130/131 = `direct_annual_settlement`, 193 = `factual_evidence`; the requirement carries `dependency_treatment`, asserted by `test_cross_dependency_contract.py`). Crucially, `dependency_treatment` is NOT honored anywhere in `_cross_period_clean_state.py` — the gate treats every cross-period dep identically (requires upstream official filing evidence), which is what blocks the employee's M100.

### Why the treatment alone is insufficient, and the corrected design

`direct_annual_settlement` conflates two distinct cases the fix must separate:
- **Payee-suffered** (111/115/123): retenciones the taxpayer SUFFERS; the payer files the return, the taxpayer's value comes from the income certificate. These must NOT require an upstream filing the taxpayer never makes.
- **Self-filed settlement** (130/131): pagos fraccionados the autónomo FILES; these correctly require the upstream filing (now locally satisfiable via the C0 Decision A+B work).

The grounded corrected design: (1) add a registry treatment value distinguishing suffered (`suffered_retencion_credit`) from self-filed (`self_filed_settlement_credit`) across the M100 `dependency_classifications` (all revisions); (2) have `_cross_period_clean_state.py` HONOR `dependency_treatment` — a `suffered_retencion_credit` dependency carries no upstream-filing-evidence requirement (its value is income-sourced), an explicit auditable not-required facet; (3) verify the suffered-retenciones M100 casilla is income/ledger-sourced (RAG hits `test_modelo_100_retenciones_credit_fold_in_live.py`, `_modelo_bindings.py:336`) so the credit is not lost. This is grounded in the existing registry classification authority rather than the unreliable schedule signal, and it preserves enforcement for self-filed and `factual_evidence` deps.

### Status of the fix

This is a grounded, multi-revision registry change plus an application-layer treatment-honoring change, with a real silent-under-declaration risk if a suffered casilla is suppressed without an income source. It is therefore left for a grounded ADR-execution pass (research `2026-06-19-m100-dependent-modelo-applicability-research` + this ADR), NOT a single-pass patch — the Option 1 reversion is the recorded evidence that rushing this surface regresses the enforcement contract.

## Codification candidates (updated)

- **Rule slug:** `cross-period-suppression-must-be-grounded-in-registry-classification-not-schedule`. **Rule:** A cross-period dependency may be scoped out / treated as not-requiring-evidence ONLY on a registry-authoritative signal (the dependency's `treatment` classification), never on the deadline-engine obligation schedule (which is incomplete and omits legitimately-enforced sources); a schedule-based suppression over-suppresses and breaks the enforcement contract (evidenced by the reverted Option 1).

## Update 2 — RAG-grounded sourcing finding (the fix is larger than treatment-honoring)

A further `vaultspec-rag`/grounding pass pinned the exact sourcing and shows treatment-honoring ALONE is insufficient. The M100 suffered-retenciones casillas are VALUE-sourced from the withholding-modelo cross-period relations, not from income data:

- Casilla `0596` (retenciones del trabajo) is `binding = "renta-2024-modelo-111-retenciones-periodicas"`, which is the `target_binding` of relation `renta-2024-rel-111-retenciones-trimestrales` (`kind = cross_model_output`, `source_modelo = 111`, `source_output = 28`, summed over quarters).
- Casilla `0597` (retenciones capital) is bound to `renta-2024-modelo-123-retenciones-periodicas` (the 123 relation).

So for an employee with no filed 111/123, the casilla resolves to 0 (the relation has no source) AND the clean-state gate blocks. Honoring the `dependency_treatment` to drop the filing-evidence requirement would unblock the gate but leave the credit at 0 — a SILENT UNDER-DECLARATION (the employee loses their suffered-retenciones credit). The credit must instead be re-sourced.

The credit's true source is the salary/income certificate's withheld IRPF, which is NOT in the ledger today (a bank statement shows NET salary; the withheld tax is withheld at source). So the durable C3 fix is a multi-part, grounded change:

1. Introduce a typed income input for suffered retenciones (the certificate's withheld IRPF per income type — trabajo, capital, actividades), grounded against the M100 dictionary for which casillas carry payee-suffered retenciones.
2. Source the suffered-retenciones M100 casillas (0596/0597/…) from that income input for the payee case, while preserving the cross-period relation for the path where the value genuinely folds from a filed return.
3. Then (and only then) classify those dependencies so the clean-state gate does not require an upstream filing the taxpayer never makes, with the value provenance carried explicitly.

This is ADR-execution-scale (new input model + casilla re-sourcing + classification + tests + grounding), with a regulated silent-under-declaration risk if any step is partial. It is the correct, grounded successor to the reverted Option 1, and is sized for its own plan rather than a red-team single-pass.

## Update 3 — IMPLEMENTED (classification-driven, grounded, proven)

The correct fix landed in commit `fd14bdf01`. Rather than the schedule heuristic (Option 1, reverted) or a value re-sourcing (Update 2's worst case), RAG grounding showed the operator value-override already works (`--casilla`/`--relation`, the `_lift_previous_filing` pattern), so the fix is the grounded payee/payer distinction the registry classifications were missing:

- **Schema:** `taxpayer_files_source: bool = True` on `DependencyClassificationDefinition` — True for modelos the taxpayer is the obligor of (130/131 pagos fraccionados), False for retenciones the taxpayer SUFFERS but the PAYER files (111/115/123/193, LIRPF art. 99).
- **Registry:** `taxpayer_files_source = false` on the M100 suffered classifications (111/115/123/193) across revisions 2020–2025.
- **Clean-state gate:** `evaluate_cross_period_clean_state` reads the snapshot's OWN `dependency_classifications` (never the obligation schedule) to scope a not-filed-source dependency out as not-applicable (clean, `modelo_not_applicable_advisory`), surfaced by a non-blocking operator advisory (no-silent-under-declaration).

Why this succeeds where Option 1 failed: the classification is per-modelo registry authority, so suppression is scoped to exactly the suffered set — self-filed 130/131 stay enforced, and the different-target enforcement contract (180/190/193/200/202) is untouched. Proven: enforcement suite 50 green (Option 1 regressed 5), retenciones-fold/e2e/carry/contract/registry 53 green, and `test_m100_suffered_retencion_deps_scoped_out_self_filed_enforced` asserts the suffered set scopes out while 130/131 do not.

The `cross-period-suppression-must-be-grounded-in-registry-classification-not-schedule` codification candidate is now demonstrated across a full execution cycle (Option 1 reverted, classification fix proven) and is ready to promote.

## Related follow-up (out of C3 scope) — first-filer M100 self-carry for salaried taxpayers

The end-to-end verification (`test_verify_salaried_taxpayer_m100_has_no_cross_period_withholding_block`) confirmed C3 scopes out every withholding/pagos dependency for a declared employee, but surfaced a DISTINCT, separate concern: the M100→M100 prior-year **self-carry** (`previous_filing_binding`, e.g. base liquidable negativa) still blocks a *first-time* salaried filer. The existing first-filer suppression (`partition_cross_period_requirements_by_activity_start` + `NoPriorObligationProvenance`) keys on `TaxpayerProfile.activity_start_date`, which is an economic-activity (autónomo) signal a salaried employee does not carry. So:

- A **continuing** salaried filer is unaffected — they filed the prior M100, the self-carry evidence exists.
- A **first-time** salaried filer (no prior M100, nothing to carry) is still blocked by the self-carry, because no "first IRPF/M100 filing year" signal exists for non-activity taxpayers to drive the first-filer suppression.

This is the first-filer *mechanism* (NoPriorObligationProvenance), not C3's registry-classification withholding-dep mechanism, and needs its own grounding (when is a prior-year M100 self-carry genuinely not-applicable, and what profile signal proves "first M100 year" for a salaried taxpayer). Recorded here so it routes to an owner rather than scope-creeping into C3; the C3 withholding/pagos fix is complete and verified independently of it.
