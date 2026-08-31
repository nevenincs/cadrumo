---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:bffb23a4d21dbeeb5d506a9ee7e1070b9c9887063c296f0fdef059aa986ea62a'
step_id: 'S03'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Reconcile the modelo payload modules onto canonical aliases and move the imported-evidence match invariant to the filing-record model

## Scope

- `src/cadrumo/entrypoints/cli/_modelo_payloads.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_modelo_payloads.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_filing_record.py`
- `verify:` serialization schema still carries both fields; a real payload emits `aeat_csv_register` / `CSV-1`
- `verify:` `pytest test_modelo_filing_record.py -n 0 -m ""` -> 3 pass, 1 unrelated
- `verify:` `pytest payload gate -n 0 -m ""` -> pass (7)

## Notes

The alias half of this step landed earlier; this is the invariant half, and the
step's phrasing turned out to point one step short of the answer.

It asks to MOVE the imported-evidence match invariant to the filing-record
model. It cannot move: the invariant compares `evidence_kind` and
`evidence_reference_id` against `external_evidence`, and those two flat fields
exist only on the payload. `ModeloRecord` has no such fields -- it has the
evidence row that already carries both, and it already enforces the presence
invariants (accepted implies evidence, evidence implies accepted).

So the invariant was guarding a duplication rather than a rule. The two flat
fields restated what `external_evidence` carries and were accepted as separate
INPUT, which is what made disagreement possible in the first place.

They are derived now. `computed_field` keeps them on the wire -- verified against
the serialization schema and a real dump, because the validation schema does not
show computed fields and checking only that would have made the "wire unchanged"
claim wrong. What is gone is the ability to supply them.

That is a stronger guarantee than relocating the check would have been, and the
test says so: a check that two inputs agree only fires when someone runs it,
while a value with ONE source has nothing to disagree with. The divergence test
now asserts the payload is refused for supplying them at all, and separately
that the derived values are right.

What remains of the validator is the one thing still worth asserting: an
imported filing record carries evidence, because an import without evidence is
not an import.

The remaining failure in that module is a peer's: `WorkAmendResult` gained a
required `m303_rectificativa_motive` that the test does not supply. Zero
occurrences in this session's diff.
