---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-17'
body_hash: 'sha256:0be673a33dd575e90103db21876acb7bf4976c6024225f9d6efa876177eeee44'
step_id: 'S01'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

# Extend the state-root derivation so every output-dir Settings field default derives from cadrumo_local_storage_root under the category taxonomy, eliminating PROJECT_ROOT/var defaults

## Scope

- `src/cadrumo/core/config.py`

## Description

- Generalise the `_STATE_ROOT_DERIVED_DIRS` taxonomy table in `src/cadrumo/core/config.py` to map every generated-output directory field to a POSIX relative subpath under `cadrumo_local_storage_root`.
- Fold the auth-token and diagnostic-log derivations into the one table (previously two dedicated validators) and add every remaining `PROJECT_ROOT/var/...` output dir: the append-only telemetry logs (`llm-usage`, `llm-run-telemetry`), the regenerable caches (`cache/llm-cache`, `cache/status-cache`), and the durable outputs (`backups`, `submissions`, `browser-traces` pair, `inbox`, `inbox/pdfs`, `workflow-runs`, `drafts`, `runs`, `justificantes`, `filing-history`).
- Collapse the three per-family model validators (`_resolve_token_dir_...`, `_resolve_log_dir_...`, `_resolve_storage_substrate_dirs_...`) into one `_resolve_output_dirs_under_storage_root` that iterates the table and only computes a path when the field is not explicitly set.
- Simplify the `override_settings` re-derivation pop-loop to iterate the unified table, so overriding the root re-derives every dependent dir.
- Add `src/cadrumo/core/tests/test_output_dir_state_root.py` enumerating the whole table: each field roots under an overridden storage root, none escapes to `PROJECT_ROOT/var`, an explicit per-field override wins, and the two caches share the `cache/` namespace.
- Update the now-stale validator-name reference in the token/log derivation test comment.

## Outcome

Every output-dir Settings field default now derives from the one state root, so on an installed run nothing lands inside site-packages or a uv cache, while a checkout keeps everything under `PROJECT_ROOT/var/storage`. The `cache/` prefix is the sole on-disk category prefix; state, logs, and durable outputs keep bare leaf names matching the existing tokens/secrets/blobs/audit/logs layout, with the state/cache/logs/exports lifecycle grouping recorded conceptually per ADR ruling R1. Explicit per-field env overrides are preserved.

Gates: the targeted settings suite (config, override, state-root, token-dir, substrate, and the new derivation test) is 48 passed. The full `src/cadrumo/core` suite is 697 passed, 2 failed; both failures are outside this Step's surface and pre-existing/peer-owned in the shared worktree - `test_production_exception_classes_do_not_introduce_unregistered_builtin_roots` (a peer `FormerProduct*` exception class) and `test_repo_has_no_unallowlisted_combined_period_strings` (docs export-filename tokens owned by the in-flight S16 work). `pytest --collect-only` is clean repo-wide; ruff is clean on the touched files.

## Notes

The browser-trace field pair is derived here (both to `browser-traces`) so no config-owned effective default remains `PROJECT_ROOT/var`; the fields themselves are deleted with their table entries in S03. Each derived field keeps its historical `PROJECT_ROOT/var/...` value as an inert placeholder default (the same pattern the pre-existing secrets/blobs/audit fields use) - the effective value is always the validator-computed derived path unless the field is explicitly set.
