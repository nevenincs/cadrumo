---
step_id: S68
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
  - '[[2026-05-30-identity-primitives-reference]]'
---

# identity-primitives W05.P19.S68 — bare-str typed-id field detector and inventory discovery

## Scope

Land the fourth ADR Rule 9 detector: walk every pydantic
`BaseModel` subclass under `src/aeat/` with the standard-library
`ast` module and flag every `<owner>_id` field declared as bare
`str` (or `str | None`) when a typed alias for that owner exists
in the discovered alias inventory.

## Outcome

Extended `src/aeat/diagnostics/_identity_placement.py` with:

- `_is_basemodel_subclass(node)` — textual recognition of a
  pydantic-`BaseModel` subclass (covers bare `BaseModel`,
  attribute-form `pydantic.BaseModel`, and `BaseModel[T]` generic
  parameterisation).
- `_annotation_is_bare_str(annotation)` — recognises bare `str`
  and `str | None` while accepting any other shape (typed alias
  `WorkUnitId`, inline `Annotated[str, ...]`, or third-party
  type).
- `find_bare_str_typed_id_fields(root, inventory)` — the public
  detector. Skips alias-declaring modules so an `_ids.py`'s own
  `__all__` assignment never trips the field walker.

Extended `_module_dotted_path` to accept the `root` parameter so
test fixtures rooted at a synthetic `tmp_path` resolve cleanly.

Added two tests:

- `test_alias_inventory_discovers_known_owners` — pins the
  required owner-prefix mapping (bucket, profile, snapshot,
  transaction, work_unit, calculation_revision, filing_record,
  verification_report, invoice, attachment, bundle, evidence,
  casilla, formula, revision, modelo). The mapping is itself
  part of the test contract; renaming an alias without renaming
  this assertion fails the test.
- `test_bare_str_typed_id_detector_recognises_synthetic_violation` —
  exercises the detector against a synthesised
  `tmp_path/src/aeat/...` fixture with three shapes (bare `str`,
  `str | None`, typed `InvoiceId`) and asserts the detector
  flags the two bare shapes while accepting the typed shape.

## Deferred enforcement — adjudication required

The detector run against the post-W04 tree surfaces 54 bare-`str`
typed-id field sites across 30 files. Lifting these mechanically
introduces cross-domain Rule 2 violations the S65 detector would
then flag, exposing a structural tension between ADR Rule 9
clause 4 and ADR Rule 2:

- `domain.transactions._models` references `EvidenceId` (defined
  in `application.evidence._ids`) and `InvoiceId` (sibling
  domain). Lifting forces either a domain-from-application
  import (forbidden by hexagonal direction) or a sibling-domain
  identity import (forbidden by Rule 2).
- `domain.calculations.registry._bindings` references
  `InvoiceId` (sibling domain). Same tension.
- `domain.invoices._service` references `InvoiceId` from the
  invoice domain (same-domain — clean lift).

Reporting back per the dispatch brief: the adjudication options
are (a) extend ADR Rule 1 clause (a) to promote `InvoiceId`,
`EvidenceId`, `AttachmentId`, and other affected aliases to
`core/identity/` (consistent with the `TransactionId`
promotion landed in S65); or (b) extend the Rule 2 exception
list to name specific cross-domain identity edges; or (c)
extend W04 with a follow-up Wave that performs the 54-site
sweep alongside whichever adjudication path (a)/(b) lands.

The 54-site inventory is captured in the test failure output
when `find_bare_str_typed_id_fields` runs without the
synthetic-fixture restriction; see commit `19db0abcd` for the
first `git diff` showing the discovered inventory.

## Verification

`uv run --no-sync pytest
src/aeat/diagnostics/test_identity_primitive_placement.py`
runs five tests (5 passed, 5.08s).
