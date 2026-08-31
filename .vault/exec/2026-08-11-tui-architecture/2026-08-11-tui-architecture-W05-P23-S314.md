---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:8727932b06905be41f5c492c36dd1b304936d8d50b28d1e790d98bd09bb7c616'
step_id: 'S314'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Hard-move the transient financial operand contracts out of their private module into a public defining module, atomically: `OperationTransientFinancialOperandDeclaration`, `OperationFinancialOperandRefusalReason` and their siblings live in `_financial_operand.py`, but are imported cross-package by PRODUCTION code at `adapters/persistence/operations/financial_operand_custody.py` and `application/modelo/operation_definitions.py`, with the custody state machine in `_financial_operand_custody.py` reached the same way -- a contract required outside its package living in a private module, which `dev/tests/test_import_hygiene_gate.py` currently fails on across four assertions; move both modules to public defining names, update every production, test, fixture, annotation and docs-stub consumer, delete the old paths, land it in ONE explicit-path commit with `pytest --collect-only -q` clean immediately before, and prove the hygiene gate green rather than re-baselined

## Scope

- `src/cadrumo/application/operations/_financial_operand.py`
- `_financial_operand_custody.py`
- `their public destinations`
- `every consumer the gate names`
- `and the regenerated docs/api stubs`

## Changes

- `R` `src/cadrumo/application/operations/_financial_operand.py -> src/cadrumo/application/operations/financial_operand.py`
- `R` `src/cadrumo/application/operations/_financial_operand_custody.py -> src/cadrumo/application/operations/financial_operand_custody.py`
- `M` `src/cadrumo/adapters/persistence/operations/financial_operand_custody.py`
- `M` `src/cadrumo/adapters/persistence/operations/tests/test_financial_operand_custody.py`
- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/application/operations/financial_operand_submission.py`
- `M` `src/cadrumo/application/operations/persistence/financial_operand_custody.py`
- `M` `src/cadrumo/application/operations/registry.py`
- `M` `src/cadrumo/application/operations/supervisor.py`
- `M` `src/cadrumo/application/operations/tests/test_executor.py`
- `M` `src/cadrumo/application/operations/tests/test_financial_operand.py`
- `M` `src/cadrumo/application/operations/tests/test_financial_operand_custody.py`
- `M` `src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py`
- `M` `src/cadrumo/application/operations/tests/test_financial_operand_executor_custody.py`
- `M` `src/cadrumo/application/operations/tests/test_financial_operand_registration.py`
- `D` `docs/api/cadrumo.application.operations._financial_operand.rst`
- `D` `docs/api/cadrumo.application.operations._financial_operand_custody.rst`
- `A` `docs/api/cadrumo.application.operations.financial_operand.rst`
- `A` `docs/api/cadrumo.application.operations.financial_operand_custody.rst`
- `M` `docs/api/cadrumo.application.operations.rst`
- `verify:` `uv run --no-sync pytest --collect-only -q` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo` -> `pass`
- `verify:` `uv run --no-sync python -m dev.docs.apidocs scaffold --check` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests src/cadrumo/adapters/persistence/operations/tests -n0` -> `fail`

## Notes

### Adjudication, not underscore stripping

Both modules moved whole, and the decision was taken per module rather than
applied mechanically.

The operand contracts module is reached from production by the modelo operation
definitions, which need the declaration type. Its models and protocols are one
contract: a declaration cannot travel without the operand-kind, refusal-reason
and requirement types it is validated against.

The custody module is reached from production by the adapter repository, and
here a narrower option genuinely existed. Only the checkpoint model and the
state enum are reached from outside the package, so a split into a public model
module and a private state-machine module was available and was considered. It
was rejected: the transition table is keyed by the very enum that would become
public, and the repository's own test legitimately builds a legal successor
checkpoint with the advance function in order to exercise its compare-and-swap,
which is precisely that adapter's business. Splitting would leave the fixed
custody order private while the states it governs are public, a worse boundary
than the one being replaced.

No re-export, alias or bridge was introduced at either site, and both old paths
were deleted by the move rather than left forwarding.

### The gate is red, and this change neither caused nor cleared it

The move removes four named cross-package private reaches into the operand
modules. Measured by calling the gate's own site collectors before and after,
production reaches fall from 116 to 114 and test-only reaches from 129 to 127;
every removed site is an operand site and nothing else moved.

The gate nevertheless still fails, because the production baseline is hard-zero
and 114 unrelated production reaches remain, alongside a documented test-debt
set of 36 against 127 live reaches. The four sites this change owned were four
of roughly two hundred and forty-five. The honest claim is the narrow one, not
that the gate went green.

Neither the ratchet baseline nor the test-debt inventory was edited, in either
direction. That was deliberate. Raising a baseline to absorb a violation
converts a real defect into a permanently accepted one, and the count here could
only have been made to pass that way.

### The debt inventory needed no update, and the reason matters

A relocation must carry its inventories in the same commit as the move, and a
red gate standing beside a relocation is a fair reason to suspect it did not.
That inference was made here and checked rather than assumed, and it turned out
not to apply: the dead test-debt entries the gate reports name auth diagnostics,
wizard widgets, ledger actions, browser site health, the root conftest and the
vision classifier. There are none for the operand modules, because those reaches
were never recorded in the debt inventory to begin with. Nothing went dead, so
nothing needed deleting.

The gate reports nine such dead entries, not six, and separately three
forwarding wrappers in the ledger and retention packages. All are pre-existing
and all are out of scope here; they belong to their own Step.

### Verification, including a clean-baseline comparison

Collection is clean at 28638 tests, the type checker passes, and the stub tree
is conformant with no drift.

The operations and operand-adapter suites report two failures, both in the
projection-services module, on an assertion that a class name begins with an
underscore-prefixed token after an earlier relocation renamed that class to a
public name. To establish that these and a large number of modelo failures were
not caused by this move, a detached worktree was checked out at the unmodified
commit and the same tests were run there against the same interpreter. The
failure lists are identical on both sides - the same two in operations, and the
same twenty-five across the three heaviest modelo files. This change introduces
no failure.

### Provenance: landed non-atomically, by commits this author did not make

The relocation was prepared as a single change and was never committed by its
author. Two concurrent broad commits in the shared worktree captured it in
pieces. The first, `4cd0abf4c9`, carries the module moves and every code
consumer under a subject about decimal string uniqueness, together with an
unrelated test file. The second, `5ad0f86a75`, carries the documentation stubs
under a relocation subject, together with five further unrelated test files.

The consequence is worth stating plainly rather than filing as a curiosity: the
atomicity requirement was met in the working tree and lost in the history. The
move and its documentation-stub inventory are in different commits, so between
those two commits the tree carried orphan stubs for deleted modules. The final
state is correct and the stub check confirms it, but the history does not show a
single relocation commit, and no commit subject attributes the work to the
author who did it.
