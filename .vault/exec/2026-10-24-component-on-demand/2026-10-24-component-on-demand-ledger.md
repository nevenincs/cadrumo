---
tags:
  - '#exec'
  - '#component-on-demand'
date: '2026-10-24'
modified: '2026-10-24'
body_schema: 'body-v2'
body_hash: 'sha256:f1553176d1fb8674a84d85c75298c93b52b879ed9171fe9fff55d0b9603eeadf'
related:
  - "[[2026-10-24-component-on-demand-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `component-on-demand` ledger

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

- `S01` `M` `src/cadrumo/application/provisioning_contracts.py`
- `S01` `M` `src/cadrumo/application/local_reader.py`
- `S01` `M` `src/cadrumo/application/tests/test_local_reader.py`
- `S01` `verify:` `pytest local_reader, provisioning, llm reader, batch ingest and evidence CLI suites (144)` -> `pass`
- `S01` `verify:` `ruff check/format, ty, lint-imports` -> `pass`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/factory.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/session.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_browser_provisioning_refusal.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_terminal_preconditions.py`
- `S04` `M` `src/cadrumo/adapters/outbound/aeat/browser/tests/test_working_data.py`
- `S04` `M` `src/cadrumo/adapters/persistence/operations/tests/test_auth_operation_definitions.py`
- `S04` `M` `src/cadrumo/application/auth/operation_definitions.py`
- `S04` `M` `src/cadrumo/application/auth/protocols.py`
- `S04` `M` `src/cadrumo/application/auth/tests/test_operation_definitions.py`
- `S04` `M` `src/cadrumo/application/auth/tests/test_passphrase_operation_access.py`
- `S04` `M` `src/cadrumo/application/auth/tests/test_provider_configure_operation_access.py`
- `S04` `M` `src/cadrumo/application/auth/tests/test_session_acquire_operation_access.py`
- `S04` `M` `src/cadrumo/entrypoints/live_state_composition.py`
- `S04` `M` `src/cadrumo/entrypoints/operation_composition.py`
- `S04` `A` `src/cadrumo/entrypoints/tests/test_live_browser_readiness_refusal.py`
- `S04` `verify:` `focused browser readiness pytest (10)` -> `pass`
- `S04` `verify:` `browser, auth, preflight, runtime auth, provisioning_browser pytest (151 passed; 2 live-only test_live_evasion need CADRUMO_LIVE_TESTS_ENABLED)` -> `pass`
- `S04` `verify:` `live operation caller pytest (128)` -> `pass`
- `S04` `verify:` `ruff check/format, ty` -> `pass`

## Notes

- `S04` Start checks sit in entrypoint preflight bindings and an auth port, not under application/live, because application may not import the adapter's BrowserError; the refusal settles FAILED `(FAIL_BROWSER_SESSION_BROWSER)` until S05 adds a REFUSED code
