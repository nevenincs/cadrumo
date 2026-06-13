---
tags:
  - '#adr'
  - '#dsl-conditional-predicate'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-04-21-calc-verification-adr]]"
  - "[[2026-05-26-modelo-130-relation-regression-adr]]"
  - '[[2026-06-04-dsl-conditional-predicate-research]]'
---


# `dsl-conditional-predicate` adr: implies-nonzero conditional Layer 2 verification predicate | (**status:** `accepted`)

## Problem Statement

The Layer 2 cross-casilla verification predicate DSL currently supports
four operators: `all_nonzero`, `any_nonzero`, `cap_le_when_positive`,
and `advisory_when_ratio_ge`. None of these expresses a conditional
implication of the form "if antecedent casilla is non-zero (or strictly
positive) then consequent casilla must also be non-zero", which is the
canonical shape of several AEAT cuota-mínima invariants — notably
Modelo 131 EO `if C01 > 0 then C07 > 0` (cuota mínima when there is
positive base) and analogous rules on M130/M303 régimen simplificado.

Authors today either approximate the rule with `all_nonzero(["C01",
"C07"])` (which fires when C01 is itself zero — a false positive that
contradicts the regulation), or omit the predicate entirely and rely on
manual review (silent-pass risk). The DSL needs a first-class
conditional operator.

The schema docstring at `src/aeat/domain/calculations/registry/_schema.py`
explicitly defers conditional DSL to "W09" (predates the L4 cross-domain
continuity epic) — this ADR is the formal landing decision for that
deferred work, scoped to the implies-nonzero shape only.

## Considerations

- The existing four operators all evaluate predicate-holds (BLOCKING_RULE
  fires finding when the function returns False) or condition-fires
  (ADVISORY fires finding when the function returns True). The
  conditional operator follows the BLOCKING_RULE semantics: predicate
  holds iff antecedent is zero OR consequent is non-zero — i.e. the
  classical material implication `antecedent → consequent`.
- The schema-side `KNOWN_VERIFICATION_PREDICATE_OPERATORS` frozenset and
  the runtime evaluator regex registry must stay in lock-step; the
  existing P10.S68 gate test asserts both sides recognise every name.
- The verification finding emission contract (legal_refs threading from
  predicate definition to ModeloVerificationFinding) is already
  established by S318; this ADR does not alter that contract.
- AEAT cuota-mínima rules typically have a strictly-positive antecedent
  ("cuando C01 sea positivo") rather than "non-zero" (which would also
  fire for negative values that cannot occur in the casilla space).
  Both shapes are useful; we name the operator after the consequent
  side (implies_nonzero) and pin the antecedent test as "strictly
  positive" since that matches the regulatory phrasing for cuota-mínima.
  A future `implies_positive` variant can be added with the same
  authoring shape if a regulation requires the consequent to be
  strictly positive rather than merely non-zero.

## Constraints

- **No breaking change to existing predicates**. The four operators
  must continue to parse and evaluate identically.
- **No silent unknown-operator pass**. Authoring-time validation must
  reject `implies_nonzero` until it is registered in
  `KNOWN_VERIFICATION_PREDICATE_OPERATORS`; runtime evaluator falling
  through to `return True` (the current default for unrecognised
  expressions) must not absorb a misspelled `implies_nonzero` call.
  This is enforced by the existing P10.S68 gate; this ADR inherits
  that guarantee without modification.
- **Legal refs and finding kind preserved**. `finding_kind` defaults
  to BLOCKING_RULE and is settable to ADVISORY identically to the
  other Layer-2 predicates; the conditional operator is not
  semantically tied to one finding kind.
- **Deterministic evaluation**. Like the other operators, evaluation
  is a pure function of `(expression, casilla_values)`; no engine
  context, no profile axis, no clock.

## Implementation

### 1. Schema-side registration

In `src/aeat/domain/calculations/registry/_schema.py`, extend
`KNOWN_VERIFICATION_PREDICATE_OPERATORS` to include `"implies_nonzero"`.
Extend the `VerificationPredicateDefinition` class docstring to
document the new operator with the same prose structure as the existing
four. The schema field types (predicate_id, legal_refs, expression,
finding_kind) are unchanged.

### 2. Authoring shape

```
implies_nonzero(["antecedent_casilla_id", "consequent_casilla_id"])
```

Semantics: predicate holds iff `casilla_values[antecedent] <= 0` OR
`casilla_values[consequent] != 0`. Violation (predicate does not hold)
occurs iff antecedent is strictly positive AND consequent is zero (or
missing, which evaluates to Decimal(0) via the `.get(id, Decimal(0))`
default — same convention as the existing operators).

The antecedent is "strictly positive" rather than "non-zero" to mirror
AEAT phrasing ("cuando C01 sea positivo"). A casilla with negative
value does not trigger the implication.

### 3. Runtime evaluator

In `src/aeat/application/modelo/_actions.py`, add a regex constant
`_PREDICATE_IMPLIES_NONZERO` matching the authoring shape, and a branch
in `_evaluate_predicate_expression` that:

1. Parses the two casilla ids via the existing
   `_parse_predicate_casilla_ids` helper.
2. Returns True when `len(ids) != 2` (defensive: same shape as the
   existing cap_le_when_positive branch).
3. Reads the antecedent value; returns True if it is `<= Decimal(0)`
   (predicate trivially holds — material implication with false
   antecedent).
4. Reads the consequent value; returns True iff it is not
   `Decimal(0)`.

The branch ordering inside `_evaluate_predicate_expression` is
inconsequential since the regexes are mutually exclusive; place the new
branch alongside `_PREDICATE_CAP_LE_WHEN_POSITIVE` to keep the
two-id-tuple operators grouped.

### 4. Verification finding

No changes required. The existing BLOCKING_RULE branch in
`_evaluate_verification_predicates` already wraps any
predicate-holds-False outcome in a ModeloVerificationFinding with
predicate_id, legal_refs threading, and the standard next_action
prose. The next_action message will read:

```
Ensure all casillas required by predicate '<predicate-id>' are
non-zero before verifying.
```

This phrasing is generic enough to cover the conditional shape; a
future enhancement could specialise the message per operator if user
testing surfaces confusion.

### 5. Tests

- `test_predicate_implies_nonzero_holds_when_antecedent_zero` —
  antecedent=0, consequent=0 → predicate holds (no finding).
- `test_predicate_implies_nonzero_holds_when_antecedent_negative` —
  antecedent=-100, consequent=0 → predicate holds.
- `test_predicate_implies_nonzero_holds_when_both_positive` —
  antecedent=500, consequent=200 → predicate holds.
- `test_predicate_implies_nonzero_violated_when_consequent_zero` —
  antecedent=500, consequent=0 → predicate violated, BLOCKING finding
  emitted with predicate_id + legal_refs.
- `test_predicate_implies_nonzero_unknown_consequent_treated_as_zero`
  — antecedent=500, consequent absent from casilla_values → violated.
- Schema-side: extend the existing P10.S68 gate test fixture list to
  cover `implies_nonzero` so authoring-time validation accepts it and
  the runtime/schema lock-step assertion remains green.

Tests live under
`src/aeat/application/modelo/test_verification_predicates.py` (or the
nearest existing predicate-test module — runtime evaluator coverage
is currently colocated with `_actions.py`).

### 6. Registry use site

The first authoring use is the Modelo 131 EO cuota-mínima rule under
`src/aeat/_data/registry/aeat/modelos/131/.../verification_expectations.toml`
(scope of task #168). That authoring lands in the same commit (or an
immediately-following commit) as the schema + runtime change so the
gate test stays green throughout.

### 7. Out of scope

- Arbitrary boolean composition (`AND`, `OR`, `NOT`) of predicates.
- Multi-antecedent or multi-consequent implication.
- Arithmetic thresholds (use the existing `advisory_when_ratio_ge`
  pattern as the template for that family).
- `implies_positive` (strictly-positive consequent) — defer until a
  regulation requires it; the implies_nonzero shape covers the M131
  use case.

## Consequences

- AEAT cuota-mínima invariants can be expressed declaratively in
  TOML without false-positive collateral.
- The Layer 2 DSL now has five operators; the lock-step gate test
  continues to enforce schema/runtime parity.
- Future conditional-shape operators (`implies_positive`,
  `implies_zero`, `implies_le`) follow the same authoring + runtime
  + finding pattern; this ADR is the canonical reference for that
  family.
- Authors writing a predicate that expresses "if A then B" no longer
  reach for `all_nonzero` and accept a false-positive contract.
