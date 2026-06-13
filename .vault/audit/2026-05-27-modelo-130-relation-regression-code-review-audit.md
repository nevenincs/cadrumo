---
tags:
  - '#audit'
  - '#modelo-130-relation-regression'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-26-modelo-130-relation-regression-plan]]"
  - "[[2026-05-26-modelo-130-relation-regression-adr]]"
  - "[[2026-05-26-modelo-130-relation-regression-audit]]"
  - "[[2026-05-27-modelo-130-relation-regression-audit]]"
---

# `modelo-130-relation-regression` audit: code review (P08.S56)

Independent review performed by `vaultspec-code-reviewer` agent
dispatched against the campaign's ~40 commits, ADR (with 3
amendments A/B/C), 8 Phases / 59 Steps L2 plan, and 3 supporting
audit documents.

## Verdict

The campaign's structural objective — foreclosure of the silent-
`Decimal("0")` hazard for previous-filing bound casillas — is
achieved cleanly. Architecture, code quality, and test surface
are sound. Three LOW + two MEDIUM follow-ups remain; none are
production hazards but each closes a gate-completeness gap.

| Severity | Count | Items |
| -------- | ----- | ----- |
| CRITICAL | 0     | —     |
| HIGH     | 0     | —     |
| MEDIUM   | 2     | M1 cap-predicate integration test; M2 SecureObjectRepository roundtrip for `absent_by_design` |
| LOW      | 3     | L1 C17 tautology; L2 silent unknown-predicate fallthrough; L3 `abs()` cap symmetry |

## MEDIUM findings

### M1 — cap-predicate integration test missing

`cap_le_when_positive` is verified at the DSL evaluator unit
level (`src/aeat/application/modelo/test_verification_substance.py:91-119`)
but not at the integration level. There is no test that:

  1. Loads M130/M131 via the real `RegistryValidator` snapshot path.
  2. Computes a real calculation where C11 > C10 (or C15 > C14).
  3. Asserts a `BLOCKING_RULE` finding is emitted with the
     correct `predicate_id`.

The predicate declarations at
`src/aeat/_data/registry/aeat/modelos/130/revisions/2019-y-siguientes/verification_expectations/0002-verification_predicates.toml:16-20`
and equivalent on M131 are wired into the schema but the
end-to-end gate from registry-load → calculation →
verification-finding emission is not under test. A future
`verify_modelo_revision` regression could break the predicate
loading without surfacing.

**Recommendation**: add a real-behaviour test that constructs an
M130 2T scenario where the prior-quarter seed exceeds the current
quarter's C14, runs the full verification pipeline, and asserts
the `modelo-130-c15-cap-by-c14` predicate fires as
`BLOCKING_RULE`. Parametrise to cover M131 C11.

### M2 — `CasillaObservation.absent_by_design` SecureObjectRepository roundtrip not tested

The P08.S51 roundtrip test (`test_casilla_observation.py:89-127`)
exercises pydantic `model_dump_json` / `model_validate_json`. The
production persistence path goes through
`SecureObjectRepository.save`/`load` over encrypted SQLite, which
adds a serialization-layer + envelope-decrypt step. A future
encryption-envelope refactor could drop the field silently
because the pydantic gate would pass even if the storage layer
truncates the JSON.

**Recommendation**: add a real-behaviour roundtrip test using
`isolated_runtime_profile` that persists a `RegistryCalculationResult`
containing an `absent_by_design=True` observation to a real
secure-storage backend, reloads, and asserts the flag survives.
Parallel to the existing AEAT roundtrip discipline.

## LOW findings

### L1 — C17 subtraction tautology

`test_modelo_130_second_period_carry_forward_picks_up_first_period_saldo`
at `test_modelo_130_registry.py:159` asserts:

```python
assert casilla_17.value == casilla_14.value - saldo_seed - casilla_16.value
```

This re-derives the formula under test (`modelo-130-diferencia`
expression: `(C14 - C15) - C16`). The C15 assertion above it
(against the binding-contract seed) is non-tautological; this C17
assertion isn't. Per `.claude/rules/no-tautological-calculation-tests.md`
this is a stricter standard than typical. Cite shape: structural
invariant rather than re-derivation would be C17 < C14 (when C15
> 0), C17 sign-preserving, or operand-trace assertion.

**Recommendation**: replace the equality assertion with a
structural one (sign + bounded relation). Low priority — the test
is correct, just close to the tautology line.

### L2 — Unknown predicate expression silently passes

`_evaluate_predicate_expression` at
`src/aeat/application/modelo/_actions.py:2287-2296` returns `True`
for any unrecognised expression. The behaviour is documented
("unknown predicates do not block the operator") and tested
(`test_unknown_expression_does_not_block`). The hazard: a typo in
a future predicate `expression` field (e.g., `cap_lt_when_positive`
instead of `cap_le_when_positive`) silently passes the gate and
the predicate's intent is lost without diagnostic.

**Recommendation**: extend `RegistryValidator` to validate
`VerificationPredicateDefinition.expression` against the known DSL
operator set at registry load time. Reject unknown operators
during validation rather than silent-pass at runtime. This is
authoring-time hardening parallel to the tautology gate's design.

### L3 — `abs()` cap symmetry vs strict-greater documentation

`_PreviousModeloSelector.required_period_anchors_for_target` at
`src/aeat/domain/calculations/registry/_bindings.py:340-373`
filters anchors with `abs(anchor[0]) <= self.max_year_delta`.
The field docstring (S01) says "anchors whose absolute year-delta
is strictly greater than `max_year_delta` are dropped". The
ADR Decision 1 text says "strictly exceeds `max_year_delta`".

The implementation correctly uses `<=` (keep) which equates to
"strictly greater is dropped" — semantics match. But the symbol
choice (`<=` vs `>`) is subtle for the next reader. A passing
unit test (`test_previous_modelo_selector_max_year_delta_zero_drops_cross_ejercicio_offset_anchor`)
pins the behaviour.

**Recommendation**: docstring/code comment alignment — quote the
boundary semantics in the implementation comment ("kept when
`abs(year_delta) <= cap`; dropped when `abs(year_delta) > cap`")
so future readers don't need to re-derive.

## Confirmation of honestly-deferred items

The dispatch brief listed P08.S53 (specimen authenticity), S54
(corpus provenance), S56 (this review), and S59 (closing
verification) as out-of-session-scope. The reviewer confirms
these are honestly deferred in the audit document
(`2026-05-27-modelo-130-relation-regression-audit.md`); no
finding flagged.

## Summary

Recommendation: land **M1** and **M2** as additional Steps
(P08.S60, P08.S61) before P08.S59 closing verification. **L1-L3**
are nits that can be folded into the same Phase or a follow-up
cleanup; they are not regressions and do not block the campaign
close. The structural objective is achieved; the remaining work
is gate-completeness, not architecture.
