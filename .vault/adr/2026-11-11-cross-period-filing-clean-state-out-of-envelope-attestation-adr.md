---
tags:
  - '#adr'
  - '#cross-period-filing-clean-state'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:0f3c5947e80a7c0577213adabd30cd836bdeb75ad173b6184a9bf4121c3b0b93'
related:
  - "[[2026-06-05-cross-period-filing-clean-state-adr]]"
  - "[[2026-11-08-prior-carry-attestation-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - '[[2026-06-05-cross-period-filing-clean-state-reference]]'
  - '[[2026-11-08-prior-carry-attestation-reference]]'
---

# `cross-period-filing-clean-state` adr: `operator-attested value for a dependency outside the support envelope` | (**status:** `accepted`)

Accepted 2026-11-11 by PRIME under the operator's delegation (confirmed 2026-11-11), after reading it in full: the envelope mark comes from the pinned catalogue and no in-envelope dependency is loosened; it reuses the prior-carry attestation path on the operator layer; `value_attestations` is persisted on `CalculationOperatorLayer` with stored identities unchanged when empty. Accepted as written. The amendment is applied to `2026-06-05-cross-period-filing-clean-state-adr` as its dated 2026-11-11 section.

## Problem Statement

`2026-06-05-cross-period-filing-clean-state-adr` blocks every filing-grade cross-period dependency until a clean upstream filing proves it. When the source year lies below the floor of `src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml`, the product refuses to hold that return, so the proof can never exist. A Modelo 130 at the floor year reads `irpf.previous_year_economic_activity_net_income` from the Modelo 100 of year minus one (`src/cadrumo/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/bindings/0001-declarations.toml:55-59`). The operator can enter the figure as an override (`src/cadrumo/application/modelo/edit_admission.py:190-247`), but verification still raises `cross_period_dependency_unclean` (`src/cadrumo/application/modelo/verification_cross_period.py:385-395`). The requirement builder applies no envelope check (`src/cadrumo/application/calculations/cross_period_clean_state.py:66-94`, `:783-805`). The create door is closed below the floor (`src/cadrumo/application/modelo/verification_cross_period.py:705-724`). The only exemption is an all-zero override (`:241-256`). The declaration can never be sealed or exported.

This record amends `2026-06-05-cross-period-filing-clean-state-adr`, which carries the amendment as a dated section.

## Considerations

- RIRPF art. 110.3.c bases the minoracion on the taxpayer's net activity income of the previous ejercicio, up to 12.000 euros (`src/cadrumo/_data/corpus/normatives/html/rd-439-2007-art-110.html:31`, legal key `rd-439-2007:art-110`). That figure comes from the taxpayer's own earlier Renta, so the operator can state it.
- The envelope floor is a hard gate. Out-of-envelope years are refused, not recorded as gaps (`2026-08-14-registry-temporal-coverage-adr`). Envelope membership comes from `SupportedFilingYearsCatalogue.admits_filing_year` (`src/cadrumo/domain/calculations/registry/snapshot_globals.py:74`), the predicate the temporal resolver's refusal gate uses (`src/cadrumo/domain/calculations/registry/temporal.py:271`).
- `2026-11-08-prior-carry-attestation-adr` already records an operator statement on the revision's operator layer (`src/cadrumo/domain/modelos/calculation_revision_operator_layer.py:71`). Its set may hold only zero overrides (`:87-94`).
- Rule 07 keeps absent, unknown, operator-entered and proven states distinct.

## Considered options

- Treat any override on an out-of-envelope dependency as clean: rejected. A typed value would read as proof, and nothing would show it rests on the operator's word.
- Widen the envelope or hold an out-of-envelope return: rejected. It contradicts the operator's 2026-11-04 floor ruling.
- An explicit value attestation, admitted only for out-of-envelope sources and shown as operator-attested: chosen.

## Constraints

- Coordinator ruling of 2026-11-11 (PRIME, under the operator's delegation) decided it, and PRIME accepted this record the same day.
- Scope is limited to `previous_filing_binding` requirements on the decimal channel whose source filing year the envelope does not admit.
- An in-envelope source year whose return is not in the application stays blocked as today. Its create door and blockers are unchanged.
- A blank binding, or a plain `SET_OVERRIDE_VALUE` without attestation, does not satisfy the dependency.
- No year literal is allowed. The envelope comes only from the pinned catalogue.
- The existing all-zero exemption (`src/cadrumo/application/calculations/cross_period_clean_state.py:482-495`) is unchanged by this record.

## Implementation

We will let an explicit operator attestation of the value satisfy a cross-period dependency whose source year lies outside the support envelope.

- Envelope check: `_requirements_from_previous_filing` marks each requirement it builds with whether the snapshot's pinned `SupportedFilingYearsCatalogue` admits the source filing year. The verifier reads that mark. It never compares years itself.
- Intent: a new binding intent, `ATTEST_PRIOR_VALUE`, carries a canonical decimal value. Admission serves it only on a writable carry override whose requirement is marked outside the envelope. It reuses the `ATTEST_NO_AMOUNT` admission path and withdrawal rules: `SET_OVERRIDE_VALUE` or `REMOVE_OVERRIDE` on the same binding withdraws it. This extends D4 of `2026-08-24-modelo-edit-contract-adr` by one kind.
- Shape and persistence: `CalculationOperatorLayer` gains `value_attestations`, keyed by binding id. Each entry holds the source modelo, filing year and period. The value stays in `binding_overrides`. The provenance is operator entry. The identity payload names the field only when it is non-empty, so stored revisions keep their identity. Hypothesis: the attestation instant is the one the edit-apply event records for the revision. It is not part of the content identity.
- Clean state: an out-of-envelope requirement whose bindings are all value-attested yields clean evidence of a new kind, `operator_attested_outside_envelope`. If even one binding is unattested, the requirement stays blocking. Its remedy serves the attest action in place of the closed create door.
- Report: verification emits a non-blocking finding, `cross_period_dependency_operator_attested`. Its message facts give the source modelo, year, period, binding id and value. The backend serves its words. Results carry operator-attested provenance for the resolved casillas.

## Rationale

The figure is the taxpayer's own fact, and no source can be held for it. An explicit, revision-bound statement gives the operator a way forward. It also keeps the statement visibly distinct from a figure proven by a filing, and from one that was merely typed.

## Consequences

- Floor-year Modelo 130 rows can verify, seal and export. Dependent floor-year Modelo 100 rows get real expectations instead of a permanent block.
- The edit contract, the operator layer, the clean-state evidence vocabulary, the finding catalogue and the locale keys all change shape. The operation contract manifest is regenerated.
- Reconsider this record if the envelope floor moves or a source of out-of-envelope returns becomes admissible.

## Amendment 2026-11-11: attestation whenever the upstream return is absent

Accepted 2026-11-11 on the operator's own decision, relayed by PRIME. The operator's words: "registry is projected, yes attestation is enough". The question put was the in-envelope case: the earlier return is for a supported year, but it is not in the application.

This amendment replaces the constraint above that an in-envelope source year whose return is not in the application stays blocked. An explicit operator attestation of the value satisfies a cross-period dependency whenever the application holds no upstream return for that source, whether the source year lies outside or inside the support envelope.

- Absence is a fact of the stores. The attestation applies only when the application holds no work unit, filing record or captured observation for that source modelo, year and period. Where one exists, the dependency follows it as before. An attestation on such a requirement is refused at admission. If an attestation is recorded and a conflicting source appears later, verification raises a blocking conflict finding. The attestation is never preferred over a source.
- Inside the envelope the existing doors (create, import, capture) stay, and the attest action is served beside them, not instead of them. Outside the envelope it remains the only door.
- A plain override or a blank still never satisfies.
- The report shows the same non-blocking `cross_period_dependency_operator_attested` finding, and the result carries operator-attested provenance. The clean evidence kind becomes `operator_attested_absent_upstream`. Envelope status stays a separate fact, used only for wording.
- Scope widens from `previous_filing_binding` requirements to the scalar relation-prefill dependencies too, for example Modelo 100 casilla 0604 when the Modelo 130 quarters were filed outside the application, or Modelo 390 from Modelo 303. Row channels stay sourced from records, and an attestation on them is refused.
- No year literal is used. Envelope and presence come from the pinned catalogue and the stores.
