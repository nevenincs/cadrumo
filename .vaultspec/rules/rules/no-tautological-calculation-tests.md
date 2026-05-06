---
name: no-tautological-calculation-tests
trigger: always_on
---

# No tautological calculation tests

This rule is a HARD MANDATE. It exists because a previous test sweep
landed dozens of calculation tests that produced false confidence —
they passed green while the registry's correctness was never actually
verified.

## The defect

A tautological calculation test:

1. Feeds synthetic input casillas / observations / relation values
   to a registry runtime function such as
   `calculate_registry_snapshot`, `resolve_relation_values_from_observations`,
   `resolve_previous_filing_binding_values`, or any other formula
   evaluator entry point.
2. Asserts the runtime's output equals a hardcoded `Decimal` value
   that the test author HAND-COMPUTED by applying the same formula
   declared in the registry TOML being tested.
3. Therefore only verifies "the formula declared on disk computes
   what the formula declared on disk says it computes". No external
   authority. No real verification. The test passes green even when
   the formula is wrong against AEAT's own truth.

## Forbidden pattern

```python
result = calculate_registry_snapshot(snapshot, inputs={"01": Decimal("10000"), "02": Decimal("4000")}, ...)
assert result.values["03"] == Decimal("6000.00")  # author hand-computed 10000 - 4000
```

The test author and the registry both compute `10000 - 4000`. They
agree because they share the same defect, not because the registry
matches AEAT's authoritative calculation.

Same defect in chain resolution:

```python
result = resolve_relation_values_from_observations(revision, four_quarterly_observations, ...)
assert result["modelo-X-rel-Y-anual"] == Decimal("50000.00")  # author hand-summed 4 quarters
```

The author summed the four quarter observations in their head. The
resolver does the same sum. The Decimal assertion verifies nothing.

## What is allowed

Tests SHALL ground their expected values against external authority,
or test only structural / graph-wiring / error-path properties:

- **Workbook parity** — feed identical inputs to the AEAT-published
  `dr.xls` workbook (declared via `workbook_parity_refs`) and to the
  registry. Assert outputs match. The workbook is AEAT's own tool;
  agreement with it is real verification.
- **AEAT-published worked examples** — extract input/output pairs
  from BOE / AEAT instructional PDFs. The numbers came from AEAT,
  not from the test author.
- **Live AEAT oracle replay** — feed inputs to AEAT's open simulator
  / TGVI / NIF-IVA checker / pre-filing validator surfaces. Compare
  the registry's output to AEAT's response.
- **Structural / graph-wiring assertions** — `operand_refs`,
  `formula_targets`, `relation_ids`, `revision.id`, casilla counts,
  binding presence. These verify schema shape, not formula
  arithmetic.
- **Error-path assertions** — the runtime rejects unknown casilla
  ids, missing observations, malformed inputs. These verify
  validation contracts.
- **Identity round-trips** — for `op = "copy"` formulas, asserting
  that `output == input_relation_value` verifies the runtime threads
  the value through. Borderline; prefer graph-wiring assertions.
- **Python primitive contracts** — tests of `_evaluate_expression`'s
  raw `op = "add"`, `op = "subtract"`, `op = "percent"` handlers
  that exercise the Python implementation's contract. NOT a
  registry formula re-implementation.

## Forbidden in CI

A test landing under any of the following patterns is a violation
of this rule and MUST be removed or rewritten:

- Hardcoded `Decimal` literal in an assertion against
  `result.values[...]`, `relation_values[...]`,
  `binding_values[...]`, or any equivalent runtime output, where
  the literal can be reproduced by the test author applying the
  same formula declared in the registry TOML.
- Programmatic re-implementation of the formula's logic in the
  test (e.g., the test sums the observations itself, then asserts
  the resolver sums to the same value). This is even worse than
  hand-computed because the parallel logic is harder to detect.
- "Round-trip" tests where the inputs are arbitrary synthetic
  values and the outputs are the test author's arithmetic result.

## Mandatory checks before writing a calculation test

Before writing any test that asserts a runtime output `Decimal`:

1. Identify the EXTERNAL source the expected value comes from.
   "I computed it from the formula" is not an acceptable answer.
2. If no external source exists, do not write the assertion. Test
   the structural / wiring / error-path contract instead, or
   defer the test until an external source (workbook, AEAT
   example, live oracle) is wired.
3. If the expected value is a copy or identity passthrough, ensure
   the assertion verifies the runtime threading rather than the
   formula's arithmetic.

## Continuous pruning

The defect is pernicious — every cycle it tries to creep back. When
reviewing a calculation test or PR that touches calculation tests,
ask:

> "If I changed the formula's declaration to be wrong against AEAT,
> would this test fail?"

If the answer is no — the assertion duplicates the formula — the
test is tautological and must be removed.

## Reference incident

A previous sweep landed 38 tautological calculation test functions
across 15 files. The teardown commit removed them; the workbook-
parity tests, formula-runtime primitive tests, parity-tape tests,
and structural / graph-wiring tests survived. Future agents shall
not reintroduce the defect.
