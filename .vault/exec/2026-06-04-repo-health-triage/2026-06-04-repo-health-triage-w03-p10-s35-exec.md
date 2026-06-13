---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S35'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# W03.P10.S35 remove unapproved diagnostics source package

Scope: `W03.P10` emergency source-boundary mitigation.

## Description

- Remove the unapproved `aeat.diagnostics` source package and its `python -m aeat.diagnostics` entrypoint.
- Remove generated API stubs for `aeat.diagnostics`.
- Remove the stale Ruff exception for the deleted diagnostics helper.
- Replace live source references that advertised `aeat.diagnostics` with approved operator repair wording or neutral internal descriptions.

## Outcome

The production source tree no longer contains an `aeat.diagnostics` package.
Current source and docs config no longer advertise the unapproved module, and
Python import discovery no longer resolves `aeat.diagnostics`.

## Verification

- `fd . src/aeat/diagnostics -t f` produced no source files; the empty namespace
  directory and generated `__pycache__` were removed as part of the correction.
- `fd "aeat\.diagnostics" docs/api -t f` produced no generated API pages.
- `rg "aeat\.diagnostics|python -m aeat\.diagnostics|docs/api/aeat\.diagnostics|src/aeat/diagnostics|src\\aeat\\diagnostics" src docs pyproject.toml` produced no matches.
- `uv run --no-sync python -c "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('aeat.diagnostics') is None else 1)"` passed.
- `uv run --no-sync ruff check ...` passed for the touched source, docs config,
  and affected tests.
- `uv run --no-sync ty check ... --output-format concise` passed for the touched
  typed source and ledger test setup file.
- `uv run --no-sync pytest ... -q` passed for the non-ledger affected test slice:
  60 passed, 46 warnings.
- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_ledger_validation_paths.py --collect-only -q`
  collected 9 tests successfully after the diagnostics import removal.

The full affected pytest slice still reports the existing ledger validation
storage-route failures in `test_ledger_validation_paths.py`:
`INTEGRITY_STORAGE_VALIDATION` / "The database route does not match the active
bucket session." That module remains a separate ledger-session repair item; it
is not caused by retaining or removing `aeat.diagnostics`.

## Notes

This supersedes the earlier S35 analyzer extraction, which was rejected because `aeat.diagnostics` is not an approved hexagonal module.
