---
tags:
  - '#exec'
  - '#cli-testimonial'
date: '2026-05-21'
modified: '2026-05-21'
related:
  - '[[2026-05-21-fresh-cli-persona-repair-plan]]'
  - '[[2026-05-21-fresh-cli-persona-findings-inventory-audit]]'
---

# Fresh CLI persona repair P03 execution

## Closed Steps

- `P03.S09` - reproduced the persona-reported paths in an isolated smoke
  root and retired the `SecureObjectUnreadable` import error as not
  reproducible in the current worktree.
- `P03.S10` - added a focused public-surface regression guard for the
  confirmed import boundary.

## Finding Outcome

`SecureObjectUnreadable` is exported from `aeat.adapters.persistence.storage.sql`.
The current isolated CLI smoke did not reproduce the import error across
the reported list/create/calculate/verify workflow.

The `work verify` command refused because the draft calculation was not
ready, which is an expected domain refusal and not an import crash.

## Verification

- `uv run python -c "from aeat.adapters.persistence.storage.sql import SecureObjectUnreadable; print(SecureObjectUnreadable.__name__)"`
- `uv run aeat app modelo filing-record list`
- `uv run aeat app modelo verification-report list`
- `uv run aeat config profile create p03-seq --quiet --accept-defaults --tax-id 12345678Z --name P03 --surnames Secure --activity consultoria --iva-regime GENERAL --irpf-estimation-regime directa_simplificada --tax-residence-ccaa madrid`
- `uv run aeat config profile switch p03-seq`
- `uv run aeat app modelo work create --modelo 303 --year 2026 --period 1T --revision 2009-y-siguientes --name "P03 303" --by p03-seq`
- `uv run aeat app modelo work calculate a895bfc1c4ac1f80518b7d2ac16961be9a0979193167ab224c15ad0312d8d0d2 --by p03-seq`
- `uv run aeat app modelo work verify dde8c8a8eeec1d76b09803781e6b010ba4a85eef1f8e359ceb58a667f26910c8 --by p03-seq`
- `uv run aeat app modelo work list`
- `uv run ruff check src/aeat/adapters/persistence/storage/sql/__init__.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py`
- `uv run pytest src/aeat/adapters/persistence/storage/sql/test_secure_objects.py::test_secure_object_unreadable_is_public_sql_surface -q`
