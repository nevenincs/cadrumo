---
step_id: S65
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

# identity-primitives W05.P19.S65 — sibling-domain _ids import detector and TransactionId core promotion

## Scope

Land the first of four ADR Rule 9 structural enforcement
detectors: a real-behavior test that walks every Python
module under `src/aeat/` with the standard-library `ast`
module and asserts no `domain.<a>` module imports from
`domain.<b>._ids` for `a != b` other than the registry-aliases
exception. Surface and remediate every sibling-domain
identity import the detector finds in the post-W04 tree.

## Outcome

Created `src/aeat/diagnostics/_identity_placement.py` with the
shared AST-walking helpers (`Finding`, `AliasInventory`,
`iter_aeat_modules`, `build_alias_inventory`,
`find_sibling_domain_id_imports`). The helper does not import
any application, domain, adapter, or entrypoint module — it
inspects them as AST text only.

Created `src/aeat/diagnostics/test_identity_primitive_placement.py`
with `test_no_sibling_domain_id_imports`. The test fails loudly
with a precise `path:line` location if any sibling-domain
identity import appears.

First detector run against the post-W04 tree surfaced three
violations:

- `domain/invoices/_service.py:20` importing `TransactionId`
  from `domain.modelos._ids` (W04-residual sibling import)
- `domain/transactions/_models.py:37` importing `TransactionId`
  from `domain.modelos._ids` (the owner-domain itself never
  used the alias outside `_ids.py`)
- (After moving `TransactionId` to `domain/transactions/_ids.py`)
  `domain/invoices/_service.py` still imported from a sibling
  domain `_ids.py`, demonstrating that owner-domain placement
  alone does not satisfy Rule 2 when a true sibling consumer
  exists.

Per ADR Rule 1 clause (a) — *the lowest layer that owns the
constraint and is imported by code outside the declaring
layer* — `TransactionId` qualifies for `core/identity`
promotion the same way `BucketId`, `ProfileId`, and `SnapshotId`
do. Created `src/aeat/core/identity/_transaction.py` with the
canonical hex-64 alias and re-exported through
`aeat.core.identity.__all__`. The owner domain re-exports
through `aeat/domain/transactions/_ids.py` for ergonomic local
imports.

Updated importers:

- `domain/transactions/_models.py` → `from ._ids import TransactionId`
- `domain/invoices/_service.py` → `from ...core.identity import TransactionId`
- `application/ledger/_models.py` → `from ...core.identity import BucketId, TransactionId`
- `domain/invoices/test_service.py` docstring path corrected.

Removed the `TransactionId` declaration and `__all__` entry from
`domain/modelos/_ids.py`. The `modelos._ids` docstring updated
to reflect the relocation rationale.

## Verification

`uv run --no-sync pytest
src/aeat/diagnostics/test_identity_primitive_placement.py
::test_no_sibling_domain_id_imports`
passes against the post-fix tree (1 passed, 0.97s).

`uv run --no-sync pytest src/aeat/domain/transactions/
src/aeat/domain/invoices/ src/aeat/application/ledger/`
runs the migrated importers; the only failure is a pre-existing
`ExportFieldError: row contains unknown fields:
['source_jurisdiction']` in `application/ledger/test_actions.py`
unrelated to the identity migration (git log on that test
shows the regression was landed previously by the ledger
campaign).
