---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:986c0e9405cdafe0498191e6854b5433be2428632f7482891cf43cc1e83cf324'
step_id: 'S358'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# PREMISE OVERTAKEN BY LIVE WORK, READ THIS FIRST: when recorded, this row stated that application/modelo contained exactly four edit modules, all private, and no public edit surface of any kind. That was verified true at the time and IS NO LONGER TRUE. A public edit_contract.py now exists in the working tree -- untracked, absent from HEAD -- and ModeloEditCompatibilityTupleV1 has already moved into it. The other three types this row names remain in _edit_models.py. The promotion this row asks for is being executed by another lane as this is read, so re-measure the private/public split before acting rather than trusting any inventory below. Adjudicate and promote the Modelo edit contract to a public defining module, which is C3's UNDECLARED FIFTH PREREQUISITE and gates the remainder of the interface plan. CORRECTION ALREADY RECORDED IN THIS ROW: an earlier form claimed the promotion was UNLANDABLE BY ANY AGENT because an atomic relocation needs one commit. That claim is WITHDRAWN. Measured with an AST pass: 17 import statements across 16 files naming the private models module, of which 15 statements in 14 files are SAME-PACKAGE and only two are cross-package -- adapters/persistence/profile/modelos_edit_receipts.py and its sibling test. The atomicity the architecture rule demands is that the move and every consumer update share ONE CHANGE, not that the change be a commit; collect-only either side is the proof. The work is executable by an agent and only the LANDING needs the operator, which was already true of everything else in this tree. THE REMAINING FACTS: three interface C3 rows require the TUI to construct ModeloEditParseRequestV1, ModeloEditCompatibilityTupleV1 and ModeloEditSubmissionV1, with ModeloEditPermittedSurfaceEntryV1 needed for the admitted permitted surface; that last is a PEP-695 type ALIAS rather than a class, so a class-shaped grep will not find it and will wrongly report it absent. The production Family-1 gate prints the pattern as a live violation naming adapters/persistence/profile/modelos_edit_receipts.py importing from the private models module, under an assertion whose baseline sites list is empty. IT IS AN ADJUDICATION, NOT A RENAME: the work-lifecycle precedent split 8 shared from 4 internal, so some edit types belong public and others stay internal. DELIBERATELY NOT PRE-CHECKED: an inventory keyed to the private module would be stale the instant the promotion lands while still LOOKING current -- a prediction this row has now confirmed against itself within a day. WHY C2 NEVER HIT THIS: everything the read cohort consumed was already public. The read cohort was buildable because someone had already done the promotion for the read side; nobody had done it for the edit side, and the C3 rows were written as though they had

## Scope

- `src/cadrumo/application/modelo/_edit_models.py and its sibling private edit modules`
- `the in-flight public edit_contract.py`
- `every consumer including adapters/persistence/profile/modelos_edit_receipts.py`
- `and dev/quality/import_hygiene_baseline.json`

## Changes

- `A` `src/cadrumo/application/modelo/edit_contract.py`
- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `M` `src/cadrumo/application/modelo/_edit_services.py`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/adapters/persistence/profile/modelos_edit_receipts.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_contract.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_services.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_execution.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_detail_row_end_to_end.py`
- `verify:` `pytest --collect-only -q application/modelo adapters/persistence/profile` -> `2330/2631 before and after, 0 errors`
- `verify:` `definition census, HEAD 78 = 73 private + 6 public - 1` -> `pass, none lost`

## Notes

ADJUDICATION: 2 symbols shared by real consumers out of 57
(`ModeloEditMutationResultReceiptV1` at 2 cross-package files,
`ModeloEditMutationFamily` at 1). The other 55 have zero. A whole-module
promotion would have published 55 internal types.

THE PUBLIC MODULE'S CONTENTS ARE THE SHARED SET PLUS ITS TRANSITIVE
CLOSURE, NOT THE SHARED SET. `ModeloEditExecutionEffect` has zero consumers
anywhere and had to move because the receipt's `effect` field types on it;
`_EditModel` moved as the shared base. Deriving contents from consumer
counts alone builds a module that does not import.

`ModeloEditCompatibilityTupleV1` was promoted in the same shape afterwards
(closure of 1), closing a public-API leak: `operation_definitions.py`
embedded a private type in the public `ModeloEditApplyBaselineV1`, so an
outside caller could not construct it without reaching a private module.

CONTRAST WITH `work_lifecycle` (see the S351 record): 8 shared of 12 there
warranted promoting the module whole; 2 of 57 here warranted a narrow one.
THE SAME RULE PRODUCES OPPOSITE ANSWERS AND THE DECIDING FACT IS THE RATIO.

HELD, not delivered: the parse service (`parse_modelo_edit_value`,
`ModeloEditParseRequestV1`, `ModeloEditParseResultV1`). Transitive closure
is 35 of 63 types plus 4 symbols from `_edit_services.py`, because
`ModeloEditParseRequestV1` carries the complete admitted baseline by design
-- its own docstring states the contract mints no server-side baseline
store. RELEASING CONDITION: a real caller exists, then promote what that
call site needs rather than what the row names.

`edit_contract.py` has NO API stub: `dev.docs.apidocs scaffold` is
tree-wide with no scoping flag and six peer packages were mid-relocation.
The module drops out of the docs build until scaffolded. RELEASING
CONDITION: a quiet tree.
