---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S376'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S376 bootstrap-exempt registry

## Scope

- `src/aeat/entrypoints/cli/_bootstrap_exempt.py`

## Description

- Audited `entrypoints.cli._bootstrap_exempt` against the target `runtime-default` for `master-key` signal ownership.
- Confirmed bootstrap-exempt command paths are classification data only; the module does not construct storage repositories, open master-key providers, read environment variables, or call settings directly.
- Confirmed the CLI root callback evaluates `is_bootstrap_exempt` and `inspect_storage_write_policy` before acquiring `get_master_key_provider`, so exempt recovery/on-ramp verbs remain sessionless and non-exempt profile-bound writes stay fail-closed.
- Confirmed the storage write-policy backend short-circuits bootstrap exemptions before route classification and refuses profile-bound writes on root-fallback or explicit database routes.
- Fixed the reviewer-identified write-policy gap by adding `app ledger rule add` and `app ledger rule apply` to the centralized profile-bound write catalogue.
- Validated the behavior with the existing real CLI repair tests and write-policy backend tests.

## Outcome

- AFR-274 closed: `_bootstrap_exempt.py` remains a safe bootstrap registry and does not require production code changes for runtime-default rollout.
- Adjacent root-gate enforcement now covers ledger classification-rule mutations before this slice is committed.
- The plan checkbox was closed through `vaultspec-core vault plan step check` for `S376`; the AFR-274 register row was reconciled to `closed`.
- Validation passed: focused ruff, repair bootstrap-exempt CLI tests, storage write-policy tests, locale audit via `python -m aeat.locales audit`, and vaultspec RAG search for bootstrap-exempt runtime routing.

## Notes

- `src/aeat/entrypoints/cli/_app_live.py` was already dirty from concurrent live IVA watchdog/auth work, so S375 was intentionally left for that parallel slice.
- `src/aeat/domain/transactions/_models.py` was dirty from concurrent model-split work and was intentionally left untouched.
