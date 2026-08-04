---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:cdd81d6f3433d249950b8dd23fbff2af9f1f2d0db61c29976959fd0cd2d6fa64'
step_id: 'S105'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Correct the five settings-field defaults that disagree with their taxonomy member's declared subpath, cadrumo_registry_parity_store_dir defaulting to var slash audit slash registry slash parity against a declared audit slash registry slash parity, and cadrumo_financial_txs_dir, cadrumo_invoices_dir, cadrumo_attachments_dir, cadrumo_usage_ratios_path each carrying a var-prefixed default against an unprefixed declaration, dead at runtime since the derived-output validator overrides them from the taxonomy but a live second declaration of an already-drifted name that no gate compares

## Scope

- `src/cadrumo/core/config.py`

## Description

## Outcome

Landed in `ab90ba77c1`, confirmed at HEAD. The Step text names `src/cadrumo/core/config.py`; the fields actually live in `src/cadrumo/core/_config_integration_fields.py` (file-citation swapped with S50, see that record). All five defaults dropped the stale `var/` prefix: `cadrumo_registry_parity_store_dir` -> `Path("audit")/"registry"/"parity"`, `cadrumo_financial_txs_dir` -> `Path("financial")/"transactions"`, `cadrumo_invoices_dir` -> `Path("financial")/"invoices"`, `cadrumo_attachments_dir` -> `Path("financial")/"attachments"`, `cadrumo_usage_ratios_path` -> `Path("financial")/"usage-ratios.json"` — each now agreeing with its `StorageCategory`'s declared subpath. Confirmed dead-at-runtime-but-now-consistent per the commit message: `Settings._resolve_output_dirs_under_storage_root` already overrode every unset field from the taxonomy before this fix; the correction removes a live second declaration of an already-drifted name, not a data relocation.

## Notes
