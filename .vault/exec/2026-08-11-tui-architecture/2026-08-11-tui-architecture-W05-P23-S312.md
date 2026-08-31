---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:c64b90fa6621979ff471ebfaa1e222a2243f5255123f0c3dde0a48e3d0c91523'
step_id: 'S312'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Build the payload-safe wire mirror for ModeloDetailRow so modelo.edit.apply can carry a detail-row edit: detail_row_intents is structurally absent from the operation's request type today because all six per-modelo row types (M184/M232/M349 operador/rectificacion/M347/M210) embed coercive BeforeValidator code-hydration built for CLI --row key=value parsing, which the operations payload-graph gate refuses outright; build one mirror per row type carrying only payload-safe primitive fields, and a total translation back to the real row type that DELEGATES to the existing hydration helpers (_hydrate_m232_codigo and its siblings, the four BeforeValidator sites in _row_models.py) rather than re-implementing them, so the wire path and the CLI path share one hydration and cannot drift; extend modelo.edit.apply's wire submission and executor to carry and translate detail_row_intents; prove a real row of EACH of the six kinds round-trips through admission, mirroring and translation with byte-identical field values, and that the wire path and the CLI path refuse the SAME malformed raw code

## Scope

- `src/cadrumo/application/modelo/operation_definitions.py (the wire mirror types and executor)`
- `src/cadrumo/domain/modelos/_row_models.py (the shared hydration helpers the translation delegates to`
- `read-mostly)`
- `and a six-kind round-trip conformance test proving wire/CLI hydration parity`

## Changes

- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `A` `src/cadrumo/application/modelo/tests/test_edit_detail_row_wire_mirror.py`
- `M` `pyproject.toml`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_detail_row_wire_mirror.py -m unit -n0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_detail_row_wire_mirror.py src/cadrumo/application/operations/tests/test_financial_operand_conformance.py src/cadrumo/entrypoints/tests/test_operation_composition.py src/cadrumo/application/modelo/tests/test_edit_detail_row_end_to_end.py -n0` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo` -> `pass`

## Notes

### What this delivered, and what it did not

Six wire mirrors, one per per-modelo detail-row kind, each confirmed admitted
by the operations payload-graph gate individually rather than inferred from the
whole. Every one translates back to a byte-identical domain row.

`detail_row_intents` is still NOT carried on the wire submission. The mirrors
exist and are proven; a detail-row edit is still not submittable. Those are
different claims and this change delivered only the first. The blocker is
recorded below and is owned elsewhere.

### The blocking cause was none of the three the work expected

The Step was written against the premise that all six row types embed coercive
code hydration built for CLI parsing. Measured against the real gate functions,
that is not what blocks them.

The universal blocker is the `Decimal` validation/serialization schema-identity
mismatch - a `Decimal` field validates from a number or a string but always
serializes to a string - which is the same reason the scalar value channel was
already mirrored in this module. Only two of the six row types carry a coercive
validator at all, and one of those is a whitespace-and-uppercase normaliser
rather than code hydration. The remaining four are additionally refused for a
missing validated-defaults declaration on their shared model configuration,
which is a configuration gap owned by a separate open Step, not a property of
the rows.

The single hydration helper the Step named has no siblings, and there are three
validator sites rather than four. Recording this because the next reader of the
Step row would otherwise go looking for a hydration family that does not exist.

### One hydration, not two that agree

The instruction given was that translation must call the existing hydration
helper rather than re-implement it. What was built does something stronger: the
mirrors carry each registry code as the raw characters submitted and never
hydrate at all, so translation hands those characters to the real row type's
constructor and that type's own validator runs.

The difference matters. Calling a shared helper from two places leaves two call
sites that agree today and can be changed independently tomorrow. Carrying the
value unhydrated leaves exactly one hydration in the system, because the wire
path has no hydration to drift. The same reasoning applies to amounts: the
characters cross verbatim and the domain row parses them, so an amount the
direct path would refuse is refused here too rather than being normalised into
acceptability on the way across.

Anyone building the next wire mirror should carry values unhydrated rather than
mirror a hydrated result and delegate.

### Coverage beyond the round trip

A round-trip assertion alone passes while a field is dropped on both sides of
the comparison, because both sides are built by the same fixture. A second
check therefore asserts that every field of each domain row type is present on
its mirror, which fails on exactly that omission. The decimal test asserts on
the digit tuple rather than numeric equality, because a renormalised amount
still compares equal.

### Mutation proof

Three deliberate breakages, each confirmed to turn the suite red, all applied
by runtime monkeypatch from a plugin outside the repository so no tracked file
was modified:

- a mirror that normalises an amount in passing - caught by the decimal test;
- a translation that silently omits one optional field - caught by the M347
  round trip;
- the wire growing its own code hydration that accepts a code the direct path
  refuses - caught by the refusal-parity test.

The third is the one the design exists to prevent, and it is now detected
rather than merely argued.

### The field name that blocks the wiring, and why it was not routed around

Wiring `detail_row_intents` onto the submission was attempted, observed to
break the production registry, and withdrawn within minutes so no concurrent
commit could capture a red tree.

The refusal is on the detail-row address, not on any row: its `natural_key`
field is rejected by the credential-free field-name check, which splits a field
name on underscores and refuses any part in the forbidden set. The value is a
row's own business identity - a fiscal identifier, or a compound of identifier
and operation code - and carries nothing secret. The check has no knowledge of
the field's type, which is the same defect an earlier change already fixed for
one specific token by admitting it when its shape matches.

Mirroring the address under a different field name would have cleared the gate
immediately. It was deliberately not done. Nothing crossing the wire would have
changed; only the matcher would have stopped seeing it, which is hiding a
construct from a gate rather than resolving it. The reason is written into the
wire type's own docstring so the next reader finds an explanation rather than
an unexplained absence.

### Production cannot reach this, with or without the mirrors

The wire submission type and its request wrapper have no consumers outside the
module that defines them, and no caller anywhere submits this operation. Adding
a detail-row family to it would not make a detail-row edit reachable. What was
delivered is capability, not reach, and the distinction is stated here so a
later reader does not infer otherwise from a green Step.

### Provenance: the tree was already broken by a split capture

Part of this work was committed by a concurrent broad commit that the author of
the change did not make, under a subject about an unrelated import-flow test
helper. That commit took the mirror classes but not the imports they depend on,
leaving three undefined names and four naming violations on the main line. The
module still imported, because the affected annotations are deferred, so the
breakage was invisible to an import check and would have surfaced only when a
translation was first called.

That is the same failure mode a previous relocation hit, and it is worth stating
generally: a capture does not merely misattribute authorship, it can split one
change and land the half that does not work. The completion of those imports is
part of this commit.
