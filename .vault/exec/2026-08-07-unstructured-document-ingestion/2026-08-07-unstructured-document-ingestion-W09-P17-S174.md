---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:824ea32e0ed133333d7970cf7ae2c6137880e8d64682cd6f3feda16dc0fe3a2b'
step_id: 'S174'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Gate the consumes declaration against what each predicate reads

## Scope

- `src/cadrumo`

## Description

- Re-measure the row's stated precondition before writing the gate: an honest structurally-derived comparison over all nineteen rows finds zero mismatches in either direction, so the intra-community migration has in fact cleared it.
- Extract each row's actual fact set from its predicate's own AST, including a branch following module-local helpers a predicate hands the criteria to. That branch turned out to be inert on every live row and the rationale recorded for it here was wrong; see the correction below.
- Map criteria attribute to party fact through one table keyed by the criteria model's field names, and assert that mapping exhaustive against the model, so a field added to the model forces a decision instead of defaulting to carrying no fact.
- Assert declared equals actual per row, reporting the two directions as separate diagnostics because they are different defects: a fact read but not declared stops the producer demanding evidence the branch decides on, and a fact declared but not read asks an operator for evidence that changes no outcome.
- Carry the non-vacuity trio: the table floored as a bound rather than pinned as a count, a per-row assertion that some attribute was extracted, and a refusal rather than an empty set when a predicate cannot be read.
- Anchor the extractor itself with an assertion that some row is found to read the identifying State, since every other assertion would pass identically if the extractor found no identification read anywhere.

**Correction, measured afterwards.** That anchor was originally recorded, and named,
as pinning the helper-following branch. It does not and cannot: following changes the
extracted set on 0 of the 19 live rows, because every predicate spells the attribute
out in the call it makes and the argument is an attribute OF the subject, which the
plain walk records before any helper is considered. Removing the branch left all five
tests green, this anchor included. What the anchor really pins is that the equality
gate is comparing something rather than establishment against establishment, which is
worth having and is a narrower claim than the one recorded here. The branch's own
guard, and the reason it was kept rather than deleted, are recorded under the row that
closed the gap.

## Outcome

The gate lands green over nineteen rows with no allowlist and no exemptions. Its value is that no existing gate grounded the declaration in the code: the neighbouring party-fact tests compare the declaration against another declaration or against a pinned set of rule identifiers, which establishes that the declarations agree and nothing about what the predicates do. One of those neighbours carries a docstring asserting that every predicate reads the residencies; that sentence is now verified rather than asserted.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/iva/tests -n0 -q -m unit
    688 passed in 18.36s

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_consumes_declaration_honesty.py -n0 -q
    5 passed in 0.81s

    uv run --no-sync ruff check src/cadrumo/domain/iva/tests/test_consumes_declaration_honesty.py
    All checks passed!

Proved to bite from outside the repository, in both directions and on the unreadable case, with the number of rows the gate examined reported on every arm so a rebinding that did not take could not read as a pass:

    baseline rows: 19
    [MUT declared-but-unread ]: gate examined 20 rows -> REDS (names the injected row: True)
    [MUT read-but-undeclared ]: gate examined 20 rows -> REDS (names the injected row: True)
    [MUT unreadable predicate]: gate examined 20 rows -> REDS (names the injected row: True)
    [CONTROL unmutated       ]: gate examined 19 rows -> PASSED

The first probe run showed the unreadable arm reddening without naming the offending row, because the extraction refusal carried only the predicate function name. The diagnostic now carries the rule identifier on every arm.

## Notes

The four type-checker diagnostics under this package are in peer test modules and none is in the gate.
