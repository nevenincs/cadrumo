---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:10db1d4fe11986f1d2af3a5cc9f92c4632fe567978e3b945a5dfe0e7a88be945'
step_id: 'S76'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Converge the remaining tier-two isolation fixture-internal sites onto storage_overrides beyond the four already migrated

## Scope

- `src/cadrumo/tests/secure_sql.py`
- `src/cadrumo/tests/env_scope.py`

## Description

- Read `secure_sql.py` and `env_scope.py` in full (682 and 274 lines respectively; line counts cross-checked against `wc -l` to confirm neither read was truncated).
- Grepped both files for `override_settings(` and for every `cadrumo_*` field name used, filtered against the fields already known to be non-category (root, active-profile, secret-passphrase/backend, output-language, database-url, dev-test password, auth-provider, clave-movil field) to isolate any category-specific literal not already routed through `storage_overrides`.
- Read `StorageCategory` in `_storage_taxonomy.py` to confirm the storage root itself (`cadrumo_local_storage_root`) is not a declared category and so is structurally out of `storage_overrides`' scope (it relocates a declared category under an anchor; it does not relocate the root).
- Ran a `vaultspec-rag` semantic search ("fixture internal literal storage override tier two isolation", `--type code`) as a second, independent instrument to catch anything the grep-by-name pass could have missed; it returned only the four `S75`-converged fixtures and unrelated call sites, no new fixture-internal literal.
- Read the ADR (`R15`) and the research finding (`F16`) that named the six tier-two fixtures, to confirm the two named in `env_scope.py` — `isolated_aeat_env` and `settings_without_env_file` — are the intended remaining subject.

## Outcome

No remaining fixture-internal literal found in either file. `secure_sql.py`'s four convertible fixtures (`isolated_profile_storage_root`, `isolated_runtime_profile`, `isolated_two_bucket_runtime`, `isolated_cli_runtime_profile`) were already converged onto `storage_overrides` in `S75`; every other `override_settings` call in that file sets only the root, the active-profile pointer, or a non-path field, none of which `storage_overrides` covers by design. In `env_scope.py`, `isolated_aeat_env` manipulates `os.environ` generically from caller-supplied env-var names with no internal literal to convert, and `settings_without_env_file`'s only path-valued write is `cadrumo_local_storage_root` sourced from a fresh `TemporaryDirectory` — the root itself, which is out of `storage_overrides`' declared scope (root-scoped categories only, never the container). Neither function hand-rolls a category-specific directory literal.

This closes the Step by evidence rather than by manufacturing an edit: the research finding's "roughly 10 fixture-internal sites" figure was measured before `S75` landed and the actual per-field count in the four migrated fixtures (five in `isolated_cli_runtime_profile` plus one each in the other three) already accounts for essentially all of it. No code change lands with this Step.

## Notes

None. No incident, no data loss, no skipped work — a genuine null result, backed by a full-file read of both named files (line counts verified against `wc -l`), a targeted grep sweep, an independent semantic-search pass, and cross-reference against the taxonomy's own category set.
