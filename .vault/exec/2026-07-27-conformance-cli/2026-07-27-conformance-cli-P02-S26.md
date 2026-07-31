---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:438ca57f5e2b8c2f4a4f91627420f7a7e7746f630607a5c2dfe2a6428bfd3631'
step_id: 'S26'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# restore an independent registry-grounded oracle for the fichero-BOE required-applicable set so a relaxation of the predicate in either direction flips an assertion, remediating the review finding required-set-oracle-collapse

## Scope

- `src/cadrumo/application/filing/tests`

## Description

- Read the confirmed review finding `required-set-oracle-collapse` and reproduced its
  premise against the live registry with a throwaway probe.
- Add `_RequiredSetPartition` and `_required_set_partition` to
  `src/cadrumo/application/filing/tests/_export_support.py`: a registry-derived
  classification of every manifest-and-representable casilla into calculation results
  (declares a formula), schema-required inputs (no formula, `required` flag), and
  optional inputs (neither). The partition reads `formula` and `required` off the
  `CasillaCollection` directly and never calls `required_applicable_casilla_ids`.
- Add `test_required_applicable_set_mirrors_the_registry_predicate` to
  `src/cadrumo/application/filing/tests/test_fichero_boe_completeness_parity.py`,
  asserting each predicate clause separately (results present, schema-required present,
  optional inputs excluded) before an exhaustive set equality against the partition.
- Add `test_required_applicable_set_pins_both_predicate_clauses_at_named_anchors` with
  per-clause anchors for the two revisions that exercise both clauses, re-reading the
  registry to confirm why each anchor qualifies before asserting membership.
- Re-point `test_export_completeness_gate.py` off the subject: replace the
  `_required_applicable` helper (which called the function under test) with the
  partition, and empty one witness from each required class rather than the first
  member of the production set.
- Add `test_schema_required_formula_less_casilla_panics_when_emptied` reproducing the
  finding's concrete harm end-to-end on the schema-required, formula-less casilla.
- Correct the `required_applicable_casilla_ids` docstring, whose claim that the parity
  tests "call this function instead of re-deriving the set locally" was the sentence
  that invited the collapse.

## Outcome

The subject and its oracle are separate again. The required-set semantics are unchanged:
casillas declaring a formula (calculation RESULT) or schema-required, intersected with
representable, fixed-width scope only, rendered set keyed on value presence.

Representability is deliberately not mirrored. The partition consumes the production
`boe_representable_casilla_ids` derivation, because only the required-set predicate is
the subject under pin and disposition suppression carries its own dedicated coverage.
That boundary is stated in the partition's docstring so the scope is explicit rather
than accidental.

### Mutation proof

The acceptance criterion was that assertions flip under a relaxation in BOTH directions,
not merely when the function returns empty. Each mutation was applied to the live
predicate, run, and reverted. All three runs below are real output.

Mutation A, dropping the `or schema.required` clause so the predicate reads
`schema.formula is not None`:

```
..F.F.FF.......                                                          [100%]
E   Failed: DID NOT RAISE FilingExportError      (test_thin_fixed_width_draft_panics_before_writing[modelo-130])
E   Failed: DID NOT RAISE FilingExportError      (test_schema_required_formula_less_casilla_panics_when_emptied)
E   AssertionError: modelo 130: casillas the registry marks required (and declares no
    formula for) are missing from the required-applicable set, so a fichero-BOE could be
    written with those slots blank: ['02']
E   AssertionError: modelo 130: casilla 02 is registry-required and declares no formula...
E   assert '02' in frozenset({'03', '04', '07', '09', '11', '12', ...})
4 failed, 11 passed in 23.93s
```

Mutation B, dropping the `formula is not None` clause so the predicate reads
`schema.required`:

```
..FF.FFF.......                                                          [100%]
E   Failed: DID NOT RAISE FilingExportError      (test_thin_fixed_width_draft_panics_before_writing[modelo-130])
E   Failed: DID NOT RAISE FilingExportError      (test_thin_fixed_width_draft_panics_before_writing[modelo-390])
E   AssertionError: modelo 111 has an empty required-applicable set; the gate would pass trivially
E   AssertionError: modelo 130: casillas the registry declares a formula for are missing from
    the required-applicable set, so they would render as blank slots behind a valid digest:
    ['03', '04', '07', '09', '11', '12', '13', '14', '15', '17', '19']
E   AssertionError: modelo 130: casilla 03 declares a formula (calculation RESULT)...
E   assert '03' in frozenset({'02'})
5 failed, 10 passed in 26.43s
```

Clean control, predicate restored:

```
collected 15 items
src\cadrumo\application\filing\tests\test_export_completeness_gate.py .. [ 13%]
...                                                                      [ 33%]
src\cadrumo\application\filing\tests\test_fichero_boe_completeness_parity.py . [ 40%]
.........                                                                [100%]
============================= 15 passed in 23.23s =============================
```

Both mutations flip real assertions rather than killing a fixture floor: mutation A
produces `assert '02' in frozenset({'03', ...})` and a gate that DID NOT RAISE on the
exact casilla the finding named, and mutation B produces `assert '03' in
frozenset({'02'})`. The previous mutation proof (returning an empty frozenset) only
killed the non-vacuity floors and therefore proved the function was called, not that its
semantics were pinned.

### Verification

Both affected modules under the repository default marker selector: `15 passed in
28.01s`, collected 15 items, no deselection (both modules carry the `unit` marker). The
count rose from 12 to 15: the gate module from 4 to 5, the parity module from 8 to 10.
Full filing test package: `258 passed in 214.63s`. `ruff check` clean, `ty check` reports
`All checks passed!`, `pyright` reports `0 errors, 38 warnings` where every warning is
the pre-existing `reportPrivateUsage` convention for the underscore-named shared test
support helpers.

## Notes

Two facts worth carrying forward.

The mutation-A run is the direct reproduction of the finding's harm, and it is worth
recording precisely what it looked like before the fix: the relaxed predicate shrank the
Modelo 130 required-applicable set from 12 to 11, and the pre-existing thin-draft test
selected its victim with `sorted(required_applicable & valued)[0]` where
`required_applicable` came from the relaxed function itself. It therefore picked a
formula casilla the relaxed gate still caught, panicked as expected, and passed. The
schema-required casilla left the gate silently. A test that sources its expectation from
the subject can only detect that the subject was called.

Pre-existing `ruff format` drift in `src/cadrumo/application/filing/_export.py` was
absorbed rather than deferred. The file was confirmed already format-dirty at the
previous commit by formatting a copy of that revision, so the reflow of the return
expression in this commit corrects landed drift and does not introduce churn; the
predicate line itself is byte-identical to the previous revision.

Nothing was skipped, weakened, or stubbed. No mocks, skips, or xfail were introduced,
and the required-set semantics were not changed. The four peer-contended files named as
off-limits were not touched.
