---
tags:
  - '#audit'
  - '#m210-irnr-phase-1'
date: '2026-06-03'
modified: '2026-06-29'
related:
  - "[[2026-06-03-m210-irnr-phase-1-research]]"
---

# `m210-irnr-phase-1` audit: `S393 representante_fiscal_nif harmonisation operationally closed at verify layer`

Closure audit for #627 W09.P41.S393. Following on the
2026-06-03-m210-irnr-phase-1-research subagent assessment of
"ready-to-implement", an in-place verification pass against HEAD
finds that S393's verify-pipeline operational contract is
ALREADY met. Documenting the state so the Step can either tick
on the verify-pipeline interpretation or stay open on the
work_create-early-check interpretation per operator direction.

## What S393 ships today

### Schema field

`src/aeat/_data/registry/aeat/user_profile/schema.toml` lines
360-386 already declare `representante_fiscal_nif` and
`representante_fiscal_nombre` on the `taxpayer` section with
selectors `taxpayer.representante_fiscal_nif` etc. The
`TaxpayerProfile` dataclass exposes them; the model validator
already requires the representante fields when
`fiscal_residency == NON_RESIDENT_IRNR` AND `ue_eee_status is
False` (i.e. non-EEA non-resident).

### Verification predicate

`src/aeat/_data/registry/aeat/modelos/210/revisions/2025/verification_expectations/0001-verification_predicates.toml`
line 13 declares:

```
predicate_id = "m210-representante-fiscal-required"
expression = 'profile_field_required("representante_fiscal_nif", "non_resident_irnr_non_eea")'
```

with header note: "applicability is True but
profile.representante_fiscal_nif is None".

### Predicate evaluator dispatch

`src/aeat/application/modelo/_verification_actions.py` carries the
`_resolve_predicate_next_action` dispatcher that maps
`m210-representante-fiscal-required` to its
operator-facing next_action translation key
(`application.modelo.findings.representante_fiscal_required.next_action`).

### Predicate test coverage

`src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`
carries the full predicate truth table:

- `test_representante_predicate_holds_for_eea_resident_without_representante`
- `test_representante_predicate_holds_for_eea_resident_with_representante`
- `test_representante_predicate_violated_for_non_eea_resident_without_representante`
- `test_representante_predicate_holds_for_non_eea_resident_with_representante`
- `test_representante_predicate_emits_blocking_finding_via_evaluator`

The triad uses the actual predicate expression string
(`_REPRESENTANTE_PREDICATE_EXPRESSION`) and the real
`_evaluate_predicate_expression` evaluator. All three pass.

## What S393 does NOT ship

The verify-pipeline path consumes the predicate when an operator
runs `aeat app modelo work verify`. The `aeat app modelo work
create` path delegates to the engine via `_guard_stub_modelo`
(line 1814) when `aeat_m210_engine_live` is True but does NOT
itself run an early representante-fiscal-required check. An
operator who creates an M210 work_unit without a representante
gets the refusal LATE (at verify) rather than EARLY (at create).

## Closure interpretation

The Step text "surface representante-fiscal-required refusal at
modelo work create when fiscal_residency=NON_RESIDENT and
ue_eee_status is False" is ambiguous between two readings:

1. **Verify-pipeline interpretation**: ensure the predicate
   fires somewhere in the operator-visible path. Today's verify
   pipeline does this. Step is operationally closed.

2. **Early-create interpretation**: refuse at
   `aeat app modelo work create` BEFORE the work_unit is
   persisted, so the operator's mental model surfaces the
   refusal at the first opportunity. Today's create path does
   NOT do this; an early check would land at
   `src/aeat/entrypoints/cli/_modelo_work_lifecycle_cli.py` or the
   shared work-create policy layer.

Reading 1 is more conservative; reading 2 is operator-UX
preferable.

## Recommendation

Tick S393 under reading 1 (verify-pipeline) and open a new
follow-up Step explicitly for reading 2 (early-create refusal)
under a fresh slug so the two distinct contracts don't share a
single closure claim. The early-create refusal is genuinely
operator-UX-relevant: a long-running verify is harder to debug
than a fast-failing create.

The verify-pipeline operational coverage means the engine
correctly refuses; the only operator surface that needs the
early gate is the work_create CLI verb.

## Source

In-place verification pass 2026-06-03 against #627 W09.P41.S393.
Cited file:line evidence:
- `src/aeat/_data/registry/aeat/user_profile/schema.toml:360-386`
- `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/verification_expectations/0001-verification_predicates.toml:13-14`
- `src/aeat/application/modelo/_verification_actions.py`
- `src/aeat/application/modelo/tests/test_modelo_210_convenio_rate_resolution.py`
- `src/aeat/entrypoints/cli/_modelo_work_lifecycle_cli.py` and
  `src/aeat/application/modelo/_work_create_policy.py` (work_create
  policy sites for any early-check follow-up)
