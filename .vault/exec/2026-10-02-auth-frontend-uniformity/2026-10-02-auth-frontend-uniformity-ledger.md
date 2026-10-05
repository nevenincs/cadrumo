---
tags:
  - '#exec'
  - '#auth-frontend-uniformity'
date: '2026-10-02'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:a5be34bf373ac561542ec0464662cd9e36613ad649c9031b14c53111d54ba4c3'
related:
  - "[[2026-10-02-auth-frontend-uniformity-plan]]"
---

# `auth-frontend-uniformity` ledger

## Changes

- `S01` `A` `src/cadrumo/application/auth/preferences.py`
- `S01` `M` `src/cadrumo/application/auth/operator.py`
- `S01` `M` `src/cadrumo/application/auth/credentials.py`
- `S01` `M` `src/cadrumo/application/auth/operator_results.py`
- `S01` `M` `src/cadrumo/application/auth/operator_result_projections.py`
- `S01` `M` `src/cadrumo/application/user_profile/fact_write.py`
- `S01` `M` `src/cadrumo/application/user_profile/tests/test_fact_write_door_contract.py`
- `S01` `verify:` `auth application and CLI contracts pytest -m unit or integration (188 tests)` -> `pass`
- `S01` `verify:` `scoped Ruff lint and format` -> `pass`
- `S01` `verify:` `scoped ty` -> `pass`
- `S01` `by:` `Codex`
- `S02` `A` `src/cadrumo/entrypoints/tui/tests/test_auth_frontend_uniformity.py`
- `S02` `M` `src/cadrumo/application/auth/operation_definitions.py`
- `S02` `M` `src/cadrumo/application/auth/operator_result_projections.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/_auth.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config/_auth_command_specs.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/config_payloads.py`
- `S02` `M` `src/cadrumo/entrypoints/cli/tests/test_auth_configure_identity_projection.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/installed_session.py`
- `S02` `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `S02` `M` `src/cadrumo/locales/en/cli.yml`
- `S02` `M` `src/cadrumo/locales/es/cli.yml`
- `S02` `M` `src/cadrumo/locales/ca/cli.yml`
- `S02` `M` `src/cadrumo/locales/hu/cli.yml`
- `S02` `verify:` `owning auth and actual CLI/TUI integration plus CLI architecture and profile admission tests (unit or integration; 219 passed)` -> `pass`
- `S02` `verify:` `scoped Ruff lint and format (12 paths)` -> `pass`
- `S02` `verify:` `scoped ty (12 paths)` -> `pass`
- `S02` `by:` `Codex`
- `S02` `M` `src/cadrumo/entrypoints/tui/tests/test_auth_frontend_uniformity.py`
- `S02` `M` `src/cadrumo/core/errors/hierarchy.py`
- `S02` `M` `src/cadrumo/core/errors/error_codes.py`
- `S02` `M` `src/cadrumo/core/errors/registry/_core.py`
- `S02` `A` `.vault/audit/2026-10-02-auth-frontend-uniformity-audit.md`
- `S02` `verify:` `core error contracts and frontend auth integration (61 passing; one profile-switch verification fixture corrected)` -> `pass`
- `S02` `verify:` `corrected profile-switch refusal test (20261002T082549.846008Z-pytest-90368-1642040d; 1 passed)` -> `pass`
- `S02` `verify:` `scoped Ruff lint and format (9 paths)` -> `pass`
- `S02` `verify:` `scoped ty (9 paths)` -> `pass`
- `S03` `M` `.vault/audit/2026-10-02-auth-frontend-uniformity-audit.md`
- `S03` `verify:` `auth/profile/admission/CLI architecture targeted suite (219 tests)` -> `pass`
- `S03` `verify:` `profile fixture and editor integration suite (64 tests)` -> `pass`
- `S03` `verify:` `public operation contracts and registry suite (119 tests)` -> `pass`
- `S03` `verify:` `combined core errors / auth frontend suite (61 passed, 1 failed due to original-profile read after switching)` -> `fail`
- `S03` `verify:` `corrected original-profile verification after reauthentication (1 focused test)` -> `pass`
- `S03` `verify:` `scoped Ruff lint and format plus ty (16 paths)` -> `pass`
- `S03` `verify:` `canonical dev.docs CLI reference generation (20 pages)` -> `pass`
- `S03` `by:` `Codex`
- `S03` `M` `.vault/index/auth-frontend-uniformity.index.md`
- `S03` `verify:` `auth verification captures (16) and localized wizard/profile captures (130)` -> `pass`
- `S03` `verify:` `all 146 capture source fingerprints, geometry, glyph and artifact checks` -> `pass`
- `S03` `verify:` `existing webserver API discovery and HTTP byte/hash equality for every PNG` -> `pass`
- `S03` `verify:` `integrated review (both high findings resolved)` -> `pass`
- `S03` `verify:` `scoped vault check (0 errors and 0 warnings)` -> `pass`
- `S03` `verify:` `installed TUI worker over changed shared composition (1 focused real integration test)` -> `pass`
- `S03` `verify:` `live-source capture refresh while unrelated files changed (source guard rejection)` -> `fail`
- `S03` `verify:` `frozen-copy coherence and auth/profile source parity (12 implementation files)` -> `pass`
- `S03` `verify:` `146 final snapshot captures and all HTTP PNG hashes` -> `pass`

## Notes

- `S02` CLI and installed TUI auth selection use the same registered request, public observation, result projector and failure metadata. TUI reuses its running graph. Repeated configuration reports NONE effect. Safe public result omits paths, identities and localized prose. New CLI route option uses the same closed schema. Sensitive typed inputs are masked. Test log 20261002T080150.404448Z-pytest-79772-2965d6ec.
- `S02` Integrated review reopened S02 for exact displayed-profile subject binding and preserving the public failure taxonomy. Both corrected. The preceding 62-test run had 61 passing and one failure only in reading the original profile after a switch; that test now reauthenticates before checking unchanged facts and passed separately. Core error registry/envelope/inventory checks remain applicable and passed. Public failure code/category/retryability/runbook are retained, with only validated opaque diagnostic references.
- `S03` Required core error checks were the passing 49 cases in the combined run; 12 frontend cases also passed. The only failing test was corrected to reauthenticate before inspecting the original encrypted record, then passed separately. Production code did not change after those 61 passing cases. Preserve this failed invocation as history rather than reporting the entire command as passing. Final visual and HTTP evidence will be appended once every locale finishes.
- `S03` Gallery runs: profile-auth-uniformity-2026-10-02-en and profile-setup-auth-uniformity-2026-10-02-es/en/ca/hu. ES 52 frames, other setup locales 26 each; auth 16. Both appearances; 80x24 and added 120x40 for Spanish/setup and auth. Review server http://100.84.254.21:8740 remained active. No live AEAT login.
- `S03` Final captures use the frozen current-source copy recorded in .tmp-tui-visual-inventory/capture-snapshot.json, because unrelated shared TUI files continued changing during live-tree render batches. Those batches were rejected rather than mislabeled coherent. Final auth/profile code matches the live tree; full-TUI source-current badges may reflect later unrelated edits. The user was informed. No live worktree edits were reverted or paused.
