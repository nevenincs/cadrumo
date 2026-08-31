---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c7ab83a8fa0b1d572b59372aea65ca7d073776e943d859569758f47f1b9b0378'
step_id: 'S80'
related:
  - "[[2026-08-11-tui-interface-plan]]"
  - "[[2026-08-11-tui-interface-W06-P12b-S79]]"
---

# Define callback-free ModeloActionView rows and one closed controller dispatch map over public query, capability, edit, and operation ports with exact result destinations and no direct executor or writer calls; `src/cadrumo/entrypoints/tui/modelo/actions.py`. GROUNDING MEASURED 2026-08-31, so the next attempt starts from facts rather than rediscovering them. THE C4 DENOMINATOR IS 31 ACTIONS, not the six this phase enrols. An AST walk of the classification table in dev/quality/modelo_workspace_action_denominator.py gives the exact set by disposition: C4_MUTATION_PENDING 31, C1_OR_C2_READ_PENDING 43, C1_BOUNDED_REVIEW 2, FLOW_OWNED 2, DEFERRED 1. The 31 are modelo.aggregate, audit.export, export, filing_record.import, filing_record.observe_local, iva_wallet.{correct,override,seed}, m036.{alta,baja,modificacion}, m145.{create,export,mark_delivered_to_payer,mark_locally_completed}, reconcile.{import,pull}, review_package.{build,counter_sign,decrypt,import_feedback,sign}, spreadsheet.{calculate,pull,push}, and work.{amend,calculate,discard,file,rename,verify}. Rows S82-S87 enrol only rename, discard, verify, file, export and amend, so TWENTY-FIVE of the 31 stay pending after this phase; a dispatch map covering six while the denominator holds 31 must make the other 25 VISIBLY pending rather than silently absent, or it under-declares its own scope. Note the table's rows pass action_id and disposition POSITIONALLY -- a keyword-based extraction returns an empty set and reads like a clean answer. BLOCKED ON THE SAME BOUNDARY QUESTION AS W06.P12b.S72, WITH A PRECEDENT RULING AVAILABLE. This row must not hand-list actions; the canonical catalogue already exists at application/operator_actions/_catalogue.py (OPERATOR_ACTION_CATALOGUE, ActionCatalogue, ActionCatalogueEntry, lookup_action, next_action). But that package has NO LEGAL PUBLIC ROUTE for a TUI consumer: every defining module is underscore-private, and application/operator_actions/__init__.py is a RE-EXPORT NAMESPACE binding 15 symbols from three private modules -- which aeat-architecture-boundaries forbids outright ('package __init__.py namespaces are inert and may not import, bind, alias, lazily resolve, or re-export project symbols'). So the TUI cannot import the namespace (prohibited re-export) and cannot import _catalogue (cross-package private import, hard-zero baseline). THIS IS A LIVE ARCHITECTURE VIOLATION IN ITS OWN RIGHT, independent of this row, and is presumably one the relocation campaign has not yet reached. THE PRECEDENT: the operator ruled on exactly this shape for S72 -- NARROW FACADE IN THE APPLICATION LAYER, keeping the records private and exposing operator-level calls, so the TUI holds a handle rather than the contract types. Applying that here means an application-owned action facade, not a TUI module reaching into the catalogue. DO NOT start this row by importing the private module or the re-exporting namespace to get moving; that trades a blocked row for a hard-zero gate violation, which is the same trap S72's original blocked-note fell into.

## Scope

- `src/cadrumo/entrypoints/tui/modelo/actions.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/actions.py`
- `A` `src/cadrumo/entrypoints/tui/modelo/tests/test_actions.py`
- `verify:` `pytest test_actions.py` -> `10 passed`

## Notes

CALLBACK-FREE BY TYPE, NOT BY CONVENTION. `ModeloActionView` is a frozen,
slotted dataclass, and a proof walks every field of every row asserting none
holds a callable, module, method or function. Checked at RUNTIME rather than
against the annotations, because a field declared `str` can still hold a bound
method and the annotation would not object. A view row carrying a callback is a
hidden edge from a rendering surface into whatever the callback closed over --
invisible to the import graph and to any reader of the row -- which is the
shape the previous cohort removed.

THE DISPATCH MAP IS KEYED BY THE REGISTERED DEFINITION ID, never by a parallel
enum, so a row cannot name an operation the platform does not register. A proof
resolves every key against the ids the application layer publicly declares, and
fails if one is absent -- a row pointing at an unregistered id would submit into
nothing, and the failure would otherwise surface at the operator.

THE UNDISPATCHABLE ACTIONS ARE DECLARED. The denominator classifies 31 modelo
candidates as pending C4 mutations; only SIX have registered definitions, so 25
are listed in `MODELO_ACTIONS_WITHOUT_REGISTERED_OPERATIONS` rather than
omitted. Two proofs keep that list honest in both directions: it must not
overlap the dispatch table, and none of its members may have acquired a
registered operation -- if one does, it belongs in the table and the test fails.
A pending list that goes stale silently would understate the surface
indefinitely. Note `modelo.work.calculate` is among the 25: it looks like a
sibling of the six and is not dispatchable.

ARITHMETIC STATED BECAUSE IT LOOKS WRONG: seven dispatchable plus twenty-five
pending does not sum to thirty-one. The sets overlap in six members and each
holds one the other does not -- `modelo.edit.apply` is registered but is not
among the denominator's 31, having arrived with the C3 editor. Caught before it
became a cited figure; the module now says so rather than leaving an apparent
slip.

THIS ROW WAS WRONGLY DECLARED BLOCKED EARLIER IN THE SAME SESSION, and the
correction is the more useful record. The reasoning was: the row must not
hand-list actions, the canonical catalogue lives in `application/operator_actions/`,
and that package has no legal public route -- every defining module is private
and its `__init__.py` re-exports 15 symbols, which the architecture rule
forbids. All of that is TRUE of that package and IRRELEVANT here: the C4
actions ARE registered operations, and all seven definition ids are public and
in `operation_definitions.__all__`. A dependency was inferred that the row never
had, and a buildable row was parked awaiting an operator ruling it did not need.
The `operator_actions` namespace violation is real and stands on its own,
unrelated to this row.

A TEST THAT WAS WRONG ABOUT ITS ENVIRONMENT RATHER THAN ITS SUBJECT. The
immutability proof originally asserted `FrozenInstanceError`. It failed with
`TypeError: super(type, obj): obj is not an instance or subtype of type` --
which reads like the frozen guarantee is broken. It is not: run directly, the
module raises `FrozenInstanceError` correctly; under pytest the module is
reachable under two identities, so the generated `__setattr__` resolves
`super()` against a different class object. The assertion now pins the PROPERTY
-- the write is refused AND the value is unchanged -- rather than the exception
class, which would have made the test assert a fact about the import context.
