---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:c49f6726c7c8a09129c36916f9f2d36a4ed5bf7fc1ba2c374950ce2fb1ceeb3b'
step_id: 'S07'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
---
# Define immutable operation request, identity, snapshot, revision, and terminal receipt models

## Scope

- `src/cadrumo/application/operations/_models.py`
- `src/cadrumo/application/operations/tests/test_models.py`
- `src/cadrumo/core/__init__.py`

## Description

- Ground the generic request, invocation identity, optimistic revision, snapshot, and receipt boundary in the accepted operation-envelope decision and its existing immutable Pydantic precedents.
- Reuse the canonical hex-64 identity primitive and strict frozen model configuration instead of declaring equivalent validators or mutable transport records.
- Keep domain operands typed through generic request payloads while retaining domain-specific request, proposal, baseline, and result ownership outside the generic platform.
- Enforce request-to-invocation identity correlation, terminal lifecycle and condition correlation, and exact receipt identity, revision, condition, effect, and settlement-time correlation.
- Promote the nine already-canonical S06 operation axes through the public `cadrumo.core` facade so the application layer consumes them without a private-module import.

## Outcome

The application operation platform now has immutable, strict contracts for `OperationIdentity`, typed `OperationRequest`, revisioned `OperationSnapshot`, and `OperationTerminalReceipt`, together with constrained aliases for operation ID, definition ID, revision, and safe record references. A cryptographically random hex-64 invocation ID generator reuses the repository's established operation-identity shape.

Snapshots preserve lifecycle, terminal-condition, and effect independence while refusing incoherent terminal states. A terminal snapshot requires exactly one correlated receipt; a non-terminal snapshot cannot carry a terminal condition or receipt. Successful and refused receipts bind their result or refusal references explicitly, and all timestamps must be timezone-aware UTC values.

## Notes

S06-to-S07 facade precondition: S06 established the canonical axes in `cadrumo.core.operations` while deliberately avoiding the then-dirty core facade. At S07 start, the facade was clean but did not export those types. The mandatory cross-package facade rule prohibited importing `cadrumo.core.operations` directly from the application package. Narrow authorization was obtained to add only the nine existing `Operation*` exports to `cadrumo.core`; no other facade symbol or behavior changed.

Canonical-home and duplication decisions:

- `Hex64Str` remains the sole physical validator for 256-bit operation identities; `OperationId` is a semantic alias, not a copied regex or wrapper.
- Configuration-reset operation records retain their specific journal identity and state contracts. The generic request and snapshot models do not absorb or replace them.
- Domain request/result payloads remain typed Pydantic models owned by their operation definition; the generic layer neither accepts `dict[str, Any]` nor invents a second payload schema.
- Interaction tokens, event records, capability declarations, journal metadata, and transition behavior remain owned by their later dedicated plan steps.

Focused verification:

- `uv run --no-sync ruff check src/cadrumo/core/__init__.py src/cadrumo/application/operations/_models.py src/cadrumo/application/operations/tests/__init__.py src/cadrumo/application/operations/tests/test_models.py` - all checks passed.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/application/operations/tests/test_models.py` - 10 passed in 0.97 seconds.
- `uv run --no-sync basedpyright src/cadrumo/application/operations/_models.py src/cadrumo/application/operations/tests/test_models.py` - 0 errors, 0 warnings, 0 notes.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/tests/test_import_hygiene_gate.py -k "private"` - 3 passed and 32 deselected in 1.02 seconds; the new operation test import creates no private cross-package regression.

Standing status: all focused S07 gates are green. The Step remains open and uncommitted pending independent review.

Review remediation:

- Pydantic v2 documentation confirms `frozen=True` prevents field reassignment but does not freeze nested dictionaries or other mutable objects. The request boundary therefore does not treat a shallow frozen wrapper as exact operand identity.
- `OperationRequest` now admits a payload only when its model and every nested Pydantic model explicitly declare `strict=True`, `frozen=True`, and `extra='forbid'`, with no private state.
- Stored payload values are recursively checked. Immutable scalars, nested strict-frozen models, tuples, frozensets, and read-only mapping proxies are admitted; lists, dictionaries, sets, cyclic references, and unsupported object types fail closed with an exact field path.
- Real tests prove refusal of non-strict payloads, non-frozen payloads, a mutable list inside a frozen model, and a mutable dictionary nested inside an otherwise immutable tuple.

Post-remediation focused verification:

- `uv run --no-sync ruff check src/cadrumo/core/__init__.py src/cadrumo/application/operations/_models.py src/cadrumo/application/operations/tests/__init__.py src/cadrumo/application/operations/tests/test_models.py` - all checks passed.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/application/operations/tests/test_models.py` - 14 passed in 0.89 seconds.
- `uv run --no-sync basedpyright src/cadrumo/application/operations/_models.py src/cadrumo/application/operations/tests/test_models.py` - 0 errors, 0 warnings, 0 notes.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/tests/test_import_hygiene_gate.py -k "private"` - 3 passed and 32 deselected in 0.94 seconds.

Standing remediation status: the request operand is now fail-closed against shallow or nested mutability. S07 remains open and uncommitted pending independent re-review.

Second review remediation:

- Removed read-only mapping-view admission. `MappingProxyType` does not own or copy its backing dictionary, so the dictionary can mutate after request validation; the request boundary now refuses it as unsupported rather than mistaking a view for immutable custody.
- Moved cycle tracking to the common traversal entry before descending into any model, tuple, or frozenset. A repeated object in the active recursion path now produces one controlled validation error with its exact path.
- Added real tests proving a mapping proxy observes backing-dictionary mutation and is refused, a deliberately self-referential strict-frozen model is refused without recursion failure, private model state is refused, and a nested strict-frozen model with tuple values is admitted.

Final focused verification:

- `uv run --no-sync ruff check src/cadrumo/core/__init__.py src/cadrumo/application/operations/_models.py src/cadrumo/application/operations/tests/__init__.py src/cadrumo/application/operations/tests/test_models.py` - all checks passed.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/application/operations/tests/test_models.py` - 18 passed in 1.04 seconds.
- `uv run --no-sync basedpyright src/cadrumo/application/operations/_models.py src/cadrumo/application/operations/tests/test_models.py` - 0 errors, 0 warnings, 0 notes.
- `uv run --no-sync pytest -q -n 0 src/cadrumo/tests/test_import_hygiene_gate.py -k "private"` - 3 passed and 32 deselected in 0.92 seconds.

Standing final status: request payload custody is fail-closed for borrowed read-only views, mutable/private state, and cycles while admitting a fully strict-frozen nested operand. S07 remains open and uncommitted pending final independent re-review.

Mechanical closeout verification:

- `uvx vaultspec-core vault check all` - exit 0 in 28.4 seconds with 1,318 warnings and no errors. The warning inventory was one S07 audit-template annotation warning, five Markdown warnings, eight feature warnings, 54 execution-mapping warnings, 1,220 body-section warnings, 29 schema warnings, and one unrelated modified-stamp warning. The two generated comment blocks identified in the S07 audit were stripped afterward through the sanctioned vault edit path; all remaining warnings are outside this Step.

