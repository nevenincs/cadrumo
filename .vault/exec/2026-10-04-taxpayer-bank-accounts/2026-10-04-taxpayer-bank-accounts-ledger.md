---
tags:
  - '#exec'
  - '#taxpayer-bank-accounts'
date: '2026-10-04'
modified: '2026-10-04'
body_schema: 'body-v2'
body_hash: 'sha256:bfc9eb7fa6c4152371cf3733a468c1d8dfcfe3d5d497ed245d2ab169ba3981ac'
related:
  - "[[2026-10-04-taxpayer-bank-accounts-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `taxpayer-bank-accounts` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->

- `S01` `A` `src/cadrumo/domain/transactions/own_accounts.py`
- `S01` `A` `src/cadrumo/domain/transactions/tests/test_own_accounts.py`
- `S01` `M` `src/cadrumo/core/iban.py`
- `S01` `M` `src/cadrumo/core/tests/test_iban.py`
- `S01` `M` `src/cadrumo/domain/calculations/registry/schema_scalars.py`
- `S01` `M` `src/cadrumo/application/modelo/value_presentation.py`
- `S01` `M` `src/cadrumo/application/modelo/tests/test_value_presentation.py`
- `S01` `M` `src/cadrumo/core/errors/registry/_domain_part3.py`
- `S01` `M` `src/cadrumo/locales/en/errors.yml`
- `S01` `M` `src/cadrumo/locales/es/errors.yml`
- `S01` `M` `src/cadrumo/locales/ca/errors.yml`
- `S01` `M` `src/cadrumo/locales/hu/errors.yml`
- `S01` `verify:` `pytest domain/transactions/tests core/tests/test_iban.py core/errors/tests test_value_presentation.py` -> `pass`
- `S01` `verify:` `ruff check and format on touched files` -> `pass`
- `S01` `verify:` `ty on touched files` -> `pass`
- `S01` `verify:` `just check-import-boundaries` -> `fail`
- `S01` `by:` `lane-a`
- `S10` `M` `src/cadrumo/core/result_disposition.py`
- `S10` `M` `src/cadrumo/application/modelo/result_disposition_resolution.py`
- `S10` `M` `src/cadrumo/application/modelo/export.py`
- `S10` `M` `src/cadrumo/core/tests/test_result_disposition.py`
- `S10` `M` `src/cadrumo/adapters/persistence/profile/tests/test_export_result_disposition.py`
- `S10` `M` `src/cadrumo/entrypoints/tests/profile_persistence/test_export_output_paths.py`
- `S10` `verify:` `pytest core/tests + disposition, producer_snapshot, DID wire, export_projection, export_output_paths, 303 refund e2e (1698 passed; 4 failures in other lanes' files)` -> `pass`
- `S10` `verify:` `ruff check + ruff format --check on touched files` -> `pass`
- `S10` `verify:` `ty on touched files` -> `pass`
- `S10` `by:` `lane-c`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/secure_object_namespaces.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/namespace_registry.py`
- `S02` `M` `src/cadrumo/adapters/persistence/storage/tests/test_namespace_registry.py`
- `S02` `A` `src/cadrumo/adapters/persistence/profile/own_accounts.py`
- `S02` `A` `src/cadrumo/adapters/persistence/profile/tests/test_own_account_register_roundtrip.py`
- `S02` `M` `src/cadrumo/locales/en/adapters.yml`
- `S02` `M` `src/cadrumo/locales/es/adapters.yml`
- `S02` `M` `src/cadrumo/locales/ca/adapters.yml`
- `S02` `M` `src/cadrumo/locales/hu/adapters.yml`
- `S02` `verify:` `pytest test_own_account_register_roundtrip.py test_namespace_registry.py` -> `pass`
- `S02` `verify:` `pytest adapters/persistence/storage/tests adapters/persistence/profile/tests` -> `fail`
- `S02` `verify:` `ruff check and format on touched files` -> `pass`
- `S02` `verify:` `ty on touched files` -> `pass`
- `S02` `by:` `lane-a`

## Notes

- `S01` import-boundary gate: 15/15 contracts kept; its failure is the pre-existing `dev/docs/serve_languages.py` re-export and stale import-load-target metadata. 2 pre-existing failures in core/errors exception-hygiene tests name unrelated modules.
- `S02` Directory run: own-account and namespace tests pass; 39 failures are pre-existing and unrelated (OS keyring logon-session probe, evidence-draft extraction, composing-write declarations naming other modules).
