---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:07b8baf989724a67b979c1f372aeeced9bebddef9546e3476a0ff750e3975493'
step_id: 'S311'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Build the OperationTransientFinancialOperandBroker composing three pieces that already exist rather than a new persistence-backed component: the S142 pure state-machine functions (open_custody, advance_custody, classify_interrupted_custody, reconcile_on_restart in _financial_operand_custody.py), the existing persistence layer (OperationFinancialOperandCustodyRepository protocol at persistence/financial_operand_custody.py:30, its filesystem implementation at adapters/persistence/operations/financial_operand_custody.py:41, already 8 tests deep against real tmp_path storage), and the S141 protocol surface (OperationTransientFinancialOperandProtocolV1) - mirroring EphemeralSecretBroker (secret_submission.py:85) exactly. Then add a financial_operand property to OperationExecutorContext (owner.py:175), thread one broker instance through the supervisor the same way self._ephemeral_secrets is threaded (supervisor.py:135, constructed per-operation into _SupervisorExecutorContext at supervisor.py:1251, mirroring BoundEphemeralSecretAccess at secret_submission.py:194), and prove one real executor calls declare_requirement and receives a granted access for an in-bounds amount and a refusal for one outside the declared bounds - a real executor exercising the broker, not a synthetic protocol-level test

## Scope

- `src/cadrumo/application/operations/_financial_operand.py (protocol surface`
- `S141)`
- `_financial_operand_custody.py (state-machine functions`
- `S142)`
- `persistence/financial_operand_custody.py and adapters/persistence/operations/financial_operand_custody.py (existing repository`
- `read-mostly)`
- `secret_submission.py (EphemeralSecretBroker as the pattern to mirror)`
- `owner.py (OperationExecutorContext)`
- `supervisor.py (broker construction and threading)`
- `and a real executor-exercised broker test`

## Changes

- `A` `src/cadrumo/application/operations/financial_operand_submission.py`
- `M` `src/cadrumo/application/operations/owner.py`
- `M` `src/cadrumo/application/operations/supervisor.py`
- `M` `src/cadrumo/application/operations/tests/test_executor.py`
- `A` `src/cadrumo/application/operations/tests/test_financial_operand_executor_custody.py`
- `A` `docs/api/cadrumo.application.operations.financial_operand_submission.rst`
- `M` `docs/api/cadrumo.application.operations.rst`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_financial_operand_executor_custody.py -m integration -n0` -> `pass`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/operations/tests/test_financial_operand_executor_custody.py src/cadrumo/application/operations/tests/test_executor.py src/cadrumo/adapters/persistence/operations/tests/test_financial_operand_custody.py -n0` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo` -> `pass`

## Notes

### Durable checkpoint ordering

The broker writes the custody checkpoints - open, bound, delivery-started - all
before the submitted amount becomes readable, and writes acknowledged and
released only after the executor has finished. The ordering is the design
judgement of this change, not an implementation detail.

Writing the checkpoints after the read would leave a process that died while
the executor held the amount reconciling as not-delivered. That is a
manufactured negative claim: the record would assert the executor never saw a
figure it may well have acted on, and the evidence does not support it. With
the checkpoints written first, the same crash reconciles as delivery-uncertain,
which is exactly what the record can support. In a system whose purpose is
filing-grade custody of financial figures, an honest uncertainty is worth more
than a confident falsehood, and that trade generalises past this change.

### Mutation proof

Three separate deliberate breakages, each confirmed to turn the new test red,
each applied by runtime monkeypatch from a plugin outside the repository so no
tracked file was ever modified: suppressing the out-of-declared-range refusal,
substituting the delivered amount, and skipping custody settlement. The clean
run is green before and after.

### Commit provenance

The work landed in commit `9b59f81c68`, which the implementing author did not
make. A concurrent broad commit in the shared worktree captured all seven files
of this change together with roughly 218 lines of an unrelated year-only
selection refusal test belonging to another author. Content at HEAD is correct
and history was deliberately not rewritten. Recorded here because the commit
message no longer identifies who did the work.

### Deferred: restart reconciliation has no production caller

`expire_lapsed` settles lapsed waits in memory only. The V1 protocol declares it
synchronous while the custody repository is asynchronous, so there is no honest
way to journal a durable expiry from it; a lapsed durable wait is instead
settled by `reconcile_owner_restart`. That function is implemented and covered
by the custody tests but has no supervisor caller, so restart reconciliation is
not reachable from production today. Wiring it is outside this change's scope
and is named here so the path does not go dormant unnoticed.

### Pre-existing failures, not introduced here

Two failing surfaces were confirmed present independently of this change; no
file either one names is touched by it, and neither was absorbed.

`test_projection_services.py` asserts a class name beginning `_Unavailable`
while the class is `UnavailableOperationSecureResponseAuthority` in
`projection_services.py`; the relocation that renamed the symbol left the
assertion behind, so that relocation was not atomic.

`dev/tests/test_import_hygiene_gate.py` reports cross-package underscore reaches
into the private financial-operand modules from the operand adapters,
definitions and their tests, against a baseline of 116 that no longer matches.
