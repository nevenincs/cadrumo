---
step_id: S143
tags:
  - "#exec"
  - "#codebase-solidification"
date: '2026-05-28'
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P05.S143 — shared storage_path helper

## Outcome

Created `src/aeat/application/_storage_paths.py` with a single public
function `storage_path(root, bucket_id, *, extension=".jsonl")` that
does `root.mkdir(parents=True, exist_ok=True)` and returns
`root / f"{bucket_id}{extension}"`.

Deleted the seven local `_storage_path` definitions and migrated all
call-sites to the canonical helper:

| Caller | Root expression | Extension |
|---|---|---|
| `evidence/_service.py` | `settings.aeat_audit_dir / "evidence-bundles"` | `.jsonl` |
| `inventory/_service.py` | `settings.aeat_ledgers_dir / "inventory"` | `.json` |
| `ledger/_business_operation_invoice.py` | `settings.aeat_invoices_dir / kind.value` | `.jsonl` |
| `ledger/_evidence.py` | `settings.aeat_purchase_invoice_evidence_dir` | `.jsonl` |
| `live/_expedientes.py` | `settings.aeat_audit_dir / "live" / "expedientes"` | `.jsonl` |
| `live/_notifications.py` | `settings.aeat_audit_dir / "live" / "notifications"` | `.jsonl` |
| `live/_verify.py` | `settings.aeat_audit_dir / "live" / "verify"` | `.jsonl` |

The `inventory` caller uses `extension=".json"` (variant detected during
inspection). The `ledger/_business_operation_invoice.py` caller takes an
extra `kind: BusinessOperationInvoiceSourceKind` argument — the root is
computed inline as `settings.aeat_invoices_dir / kind.value` before the
call, so the canonical helper signature is unchanged.

The `ledger/_evidence.py` former implementation had no `mkdir` call (mkdir
was deferred to `_save`). Post-migration the helper does mkdir on both read
and load paths, which is idempotent and safe. The `_save` function's
redundant `path.parent.mkdir` was removed.

Also updated `test_business_operation_invoice.py` which was importing the
now-deleted `_storage_path` directly — migrated to import `storage_path`
from the new module.

## Collision signal

`git diff` over all seven target files returned no output — clean workspace.

## Verification

`ruff check` — all checks passed after auto-fixing import ordering.
`def _storage_path` — no matches remaining in `src/aeat/application`.
