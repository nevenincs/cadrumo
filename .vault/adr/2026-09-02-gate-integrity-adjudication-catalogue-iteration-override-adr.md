---
tags:
  - '#adr'
  - '#gate-integrity-adjudication'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:e6db979da26bf3c78bd74d18e6cc3d0ee2befc6d91fc348d9938d0491059def7'
related:
  - "[[2026-09-02-gate-integrity-adjudication-research]]"
  - "[[2026-09-02-gate-integrity-adjudication-negative-test-typing-adr]]"
---

# `gate-integrity-adjudication` adr: `catalogue iteration overrides` | (**status:** `proposed`)

## Problem Statement

Nine pydantic catalogue models override `__iter__` to yield their contained
records instead of pydantic's declared field-name/value pairs. Every one carries
a triple suppression -- one comment per configured checker -- and the
twenty-seven suppressions together are the largest single block standing between
the `domain` and `application` trees and a clean type gate.

The suppressions cannot simply be deleted, because the diagnostic under them is
real: the override genuinely violates the base signature. Nor can they simply be
kept, because `aeat-quality-gates` refuses a suppression that stands in for a
fix, and `[tool.basedpyright]` already sets `reportUnnecessaryTypeIgnoreComment`
to error precisely so that escape hatches stay adversarial. The burn-down is
blocked until the project decides whether the override is a public API worth its
cost or an accident worth retiring, and that is an architecture question about
the catalogue contract rather than a typing patch.

## Considerations

- The overriding sites are `TransactionCatalogue` in
  `src/cadrumo/domain/transactions/models.py:1134`, `WorkUnitCatalogue` in
  `src/cadrumo/domain/modelos/work_unit.py:280`, `VerificationReportCatalogue`
  in `src/cadrumo/domain/modelos/verification_report.py:341`,
  `ModeloRecordCatalogue` in `src/cadrumo/domain/modelos/filing_record.py:453`,
  `CalculationRevisionCatalogue` in
  `src/cadrumo/domain/modelos/calculation_revision.py:1124`, `IvaCatalogue` in
  `src/cadrumo/domain/iva/schema.py:837`, `InvoiceCatalogue` in
  `src/cadrumo/domain/invoices/models.py:1084`, `AttachmentCatalogue` in
  `src/cadrumo/domain/attachments/models.py:348`, and
  `BucketEventHistoryCatalogue` in `src/cadrumo/domain/buckets/event.py:519`.
  All nine sit inside the `domain` tree, which is in scope for all three
  configured checkers.

- The diagnostic is a Liskov violation, not an undeclared override. `BaseModel`
  in pydantic 2.13.5 declares `__iter__` returning `TupleGenerator`, aliased to
  a generator of string/value pairs, with the docstring noting that this is what
  makes `dict(model)` work. Both checkers reject the narrowing on the return
  type alone: basedpyright reports `reportIncompatibleMethodOverride` because
  the narrowed iterator is incompatible with the base generator protocol, and
  `ty` reports `invalid-method-override`, naming the Liskov Substitution
  Principle explicitly. Eight of the nine sites already carry `@override`, so
  the decorator is not the missing piece and adding it changes nothing.

- The premise that the suppression protects `dict(model)` does not hold on this
  tree. No call site anywhere in `src`, `dev`, or `tests` passes one of the nine
  catalogues to `dict()`. Every `dict(...)` call in the neighbourhood takes the
  inner mapping field -- the `transactions`, `records`, `revisions`,
  `work_units`, `events`, `reports`, or `invoices` attribute -- which is a plain
  `dict` and needs no `__iter__` on the model at all. The override therefore
  breaks `dict(model)` today rather than enabling it.

- The behaviour actually consumed is value iteration, and its production
  footprint is small and enumerable:
  `src/cadrumo/application/user_profile/bundle.py` at lines 227, 230, 233, and
  236, `src/cadrumo/domain/iva/verify.py:69`, and
  `src/cadrumo/application/modelo/calculation_actions.py:1927`. The remainder is
  test code, concentrated in
  `src/cadrumo/domain/transactions/tests/test_catalogue.py` with scattered
  single uses under the buckets, invoices, and IVA test packages.

- A suppression-free equivalent already exists on all nine models: each defines
  `values()` returning exactly what `__iter__` returns, alongside `__len__` and,
  on six of them, `__contains__`. The catalogues are already collection facades
  with a redundant iteration entry point. Three of the nine `values()` methods --
  in `verification_report.py`, `filing_record.py`, and
  `calculation_revision.py` -- are unannotated and would need return types
  before they can carry the contract under a strict gate.

- The ninth site is inconsistent with the other eight and is the specific hazard
  the checker configuration warns about. `src/cadrumo/domain/buckets/event.py`
  uses a mypy-shaped `type: ignore[override]` where the others use a
  `pyright: ignore` comment; the note beside `reportUnnecessaryTypeIgnoreComment`
  in `pyproject.toml` records that such a comment can hide a diagnostic from that
  checker while looking inert. Its rationale text also declares the deferral
  permanent, citing a pydantic-v2 metaclass-aware base class that does not exist.

- Two sibling models prove the checkers object to the return type and nothing
  else. `EvidenceInput` in `src/cadrumo/application/ledger/evidence_input.py:129`
  and `DocumentTranscription` in
  `src/cadrumo/application/ledger/document_transcription.py:227` both override
  `__iter__` on a pydantic model and carry no checker suppression at all, because
  they return `Never`, which is assignable to the base return type. The override
  itself is permitted; only the incompatible narrowing is not.

## Considered options

- **Retire `__iter__` and route consumers through `values()`.** Deletes all
  twenty-seven suppressions with no residue, leaves one canonical way to read a
  catalogue's records, and touches roughly six production sites plus a bounded
  test set. Costs the terser iteration spelling and requires annotating three
  `values()` methods. Kept.

- **Make the override type-correct so no suppression is needed.** Rejected as
  unreachable rather than undesirable. Compatibility requires yielding the
  field-name/value pairs the override exists to replace, so conforming to the
  signature deletes the feature. `@override` alone satisfies neither checker, and
  eight sites already carry it.

- **Introduce an explicit `as_mapping()` method and delete `__iter__`.**
  Rejected: it solves a problem this tree does not have. The consumers found are
  value iterators, not `dict(model)` callers, and `values()` already serves them.
  A second accessor beside `values()` would create the duplicate surface
  `aeat-architecture-boundaries` forbids.

- **Stop deriving the catalogues from a pydantic model.** Rejected: the
  catalogues are validated and persisted through pydantic -- several are
  constructed by `model_validate` -- so the base class is load-bearing, and the
  change would be far wider than the diagnostic that motivates it.

- **Keep the suppressions with an owned rationale and a removal condition.**
  Rejected as the recommendation, though it is the honest fallback if the
  consumer migration is judged too costly. It leaves twenty-seven permanent blind
  spots on a Liskov violation in the domain tree, and its stated removal
  condition on the ninth site is already known to be unreachable.

## Constraints

The decision depends on pydantic's declared base `__iter__` signature, which is
stable across pydantic 2.x and unlikely to widen; there is no upstream change to
wait for. No frontier technology is involved and no parent feature is in flight
that would move these models.

The one sequencing constraint is the gate itself: basedpyright treats a
suppression that no longer suppresses anything as an error, so the override
deletion and the suppression deletion must land in the same change per file.
`no-legacy-compatibility` forbids leaving `__iter__` in place as a deprecated
shim while consumers migrate, so the migration is atomic per model rather than
staged. The mypy-shaped comment in the buckets module must be resolved in the
same pass; leaving it would preserve exactly the hiding behaviour the
configuration warns about.

## Implementation

We will delete `__iter__` from all nine catalogue models together with their
twenty-seven suppressions, and move every consumer to the `values()` accessor
those models already expose.

The work layers in three parts. First, `values()` is made a complete contract:
the three unannotated definitions gain explicit return types, and the accessor is
confirmed to return the same records the override yielded on all nine. Second,
each consumer is rewritten against `values()` -- the four tuple constructions in
the profile bundle, the two loop sites in IVA verification and calculation
actions, and the test sites, whose first-element reads become explicit. Third,
`__iter__` and its suppression comment are removed from each model in the same
change as that model's consumers.

Deleting an iteration entry point is a behavioural change that must be proven,
not asserted. Because the models remain pydantic models, removing the override
restores the inherited `__iter__`, so iterating a catalogue will silently start
yielding field-name pairs instead of raising. `aeat-quality-gates` requires the
gate to exercise real behaviour, so each model needs a test that pins the
post-change contract: `values()` yields records, and iterating the model directly
does not. A gate that only asserts the suppressions are gone would pass on a tree
where a missed consumer now silently reads field pairs.

## Rationale

The knockout is that the premise justifying the suppression is false on this
tree. The suppression's own rationale text says the override preserves an
established public API against pydantic's field-pair semantics, and the
`dict(model)` compatibility it is presumed to protect is exactly what pydantic's
base `__iter__` exists for. But no caller passes any of the nine catalogues to
`dict()`, and the override makes that call fail rather than work. What is being
protected is value iteration, which `values()` already provides on every one of
the nine, without a suppression. The project is paying twenty-seven permanent
blind spots to keep a spelling.

The scale settles the cost objection. The consumer set is six production sites
across three files plus a bounded test set, small enough that
`no-legacy-compatibility`'s same-change replacement requirement is comfortable
rather than punishing. Weighed against that, the retained-suppression option asks
the domain tree to carry a documented Liskov violation indefinitely, and the
buckets site shows how such a deferral ages: its stated unblocking condition
names a pydantic base class that does not exist, so the rationale can never be
revisited on its own terms.

The tension with `aeat-architecture-boundaries` is worth stating plainly rather
than glossing. Consolidating on `values()` is the rule's canonical-definition
direction -- one way to read a catalogue's records, not two -- but `values()` was
not designed as that canonical accessor, and three of the nine leave it
unannotated. This decision promotes an incidental accessor to the contract. That
is the right direction, and it is honest that the promotion is a decision this
record makes rather than a state it inherits.

## Consequences

The type gate loses twenty-seven suppressions from the domain tree and gains
nothing in their place, which is the outcome `aeat-quality-gates` asks for: the
diagnostic is resolved rather than silenced. Each catalogue ends with one
documented way to read its records, and the mypy-shaped comment in the buckets
module -- which could hide unrelated future diagnostics on that line while
appearing inert -- is removed as a side effect.

The cost is real and falls on readability. Direct iteration over a catalogue
becomes an explicit `values()` call, and the terser spelling is genuinely more
pleasant; the project is trading it for gate reach. Reviewers should expect the
diff to be wider than the nine model files.

The principal pitfall is silent breakage. Removing the override does not make
iteration raise -- it restores pydantic's field-pair iteration -- so a consumer
missed in the migration keeps type-checking and keeps running while reading the
wrong values. The per-model contract tests described under Implementation are
what make that failure mode loud, and they should land before or with the
deletions rather than after.

Beyond this feature, the decision establishes a reusable precedent for the
remainder of the burn-down: a suppression whose stated rationale cannot be
reproduced against live consumers is evidence that the suppressed construct is
unused, not evidence that it is load-bearing. That test is cheap to apply and
generalises past `__iter__`.
