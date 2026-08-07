---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e8037795c4c5530347977e2309653c180bc76e158d5da321e915990dfb4166f2'
step_id: 'S27'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---
## Description

The register row carries AEAT's own request-type field, the capture path read it
into the raw observation's metadata, and the persistence boundary then built its
source metadata from a fixed key set that dropped it. So the one signal that
could distinguish an original filing from an amendment was gone before any
selection logic could read it.

This Step pinned that loss rather than repairing it, because a separate row
already owned carrying the field through and a half-fix landed here would have
been worse than a visible gap.

## Outcome

Added `test_persisted_source_metadata_drops_the_register_request_type_signal` to
`src/cadrumo/application/live/tests/test_filed_capture_calculation_history.py`,
with the reversal condition stated in its own docstring.

The observation was Modelo 130, not Modelo 303. A 303 observation additionally
drives the IVA compensation wallet on the way to persistence, so a failure there
would have been indistinguishable from the metadata behaviour under test; Modelo
130 reached the boundary with nothing else attached. It reused the shared Modelo
130 observation builder rather than duplicating one.

Assertion order was chosen so absence could not pass vacuously: the raw
observation carries the signal, the metadata was built at all, the key is absent,
and the VALUE is absent from every other key so a rename could not satisfy it.

## Verification

The test passed, and the gate was proven to bite by a runtime mutation making the
metadata builder carry the request type through -- the pending change itself. Red
observed: `assert 'tipo_solicitud' not in {...}` with the added key visible.
Re-run explicitly serialised with `-n0` after the project default was found to
inject `-n auto --dist=loadfile`: verdict unchanged, still red. Unmutated control
green.

## Notes

THIS TEST NO LONGER EXISTS, and its removal is the correct outcome rather than a
lost gate. The carry-through landed while this Step was closing: the persistence
boundary now writes `aeat_tipo_solicitud`, and the pinning test was replaced by
three tests asserting the opposite -- the signal is carried, an absent request
type is omitted rather than written empty, and the carried key survives a strict
encrypted roundtrip. The reversal condition this Step's docstring stated was
executed exactly as written.

So this record describes a gate that was live and has since been retired by the
change it was pinning. It is not evidence of a currently-enforced property. The
carry-through's own row was still unchecked when this was written even though its
code was in the tree, which is worth an owner: done-but-unmarked reads to the next
person as outstanding work.

An earlier draft could not run at all. The Modelo 303 path raised `AttributeError`
because `_iva_compensation_history.py` read a field the derivation dataclass does
not declare -- pre-existing at HEAD, in files this Step did not touch, already
reding thirteen long-standing tests in the same module. It was not patched here.
