---
tags:
  - '#exec'
  - '#live-pull-verification-sweep'
date: '2026-06-12'
modified: '2026-06-12'
plan: '[[2026-06-12-live-pull-verification-sweep-plan]]'
step_id: W03.P05.S19
related_steps:
  - W02.P04.S10
  - W03.P06.S27
---

# W03.P05.S19 censo CLI auth preflight and live retry

## Scope

Hardened the `config profile censo pull` surface so it emits the same redacted
live-auth preflight as the other authenticated pull surfaces before the
live-read access gate or backend censo fetch is reached.

This keeps censo/Modelo 036 pull aligned with the pull-only CLI contract while
leaving `show`, `compare`, and `apply` as local projection verbs over persisted
censo snapshots.

## Code changes

- `src/aeat/entrypoints/cli/_config/_profile_censo.py`
  - imports `_emit_live_auth_preflight`;
  - calls `_emit_live_auth_preflight()` immediately after resolving the active
    profile pointer and before `AeatAccessGate.require_live_read()`.
- `src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
  - extends the live-gate refusal regression to require
    `auth_preflight=redacted` and `auth_provider` output before the live-read
    refusal.

No `pull-all` censo or filed-history verb was introduced.

## Verification

Required semantic discovery was attempted first:

- `vaultspec-rag search --timeout 180 "live pull verification censo modelo 036 calendar obligations justificante filed history CLI pull"`
  - result: `http_search_timeout`.

Focused local gates:

- `.venv\Scripts\python.exe -m ruff check src/aeat/entrypoints/cli/_config/_profile_censo.py src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py`
  - result: passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py::test_refresh_refuses_without_live_gate -q -rs --tb=short`
  - result: 1 passed.
- `.venv\Scripts\python.exe -m pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_censo_verbs.py -q -rs --tb=short`
  - result: 11 passed.

An initial focused pytest invocation using the global `python` binary failed
before collection because that interpreter lacked project dependencies. The
same check was rerun with the repo `.venv` and passed.

## Live run

A fresh isolated live root was created under:

- `.tmp/live-censo-cli-20260612-204622`

Setup used a fresh profile whose profile tax id matched the configured Cl@ve
identity, file-backed secret storage, `AEAT_LIVE_TESTS_ENABLED=1`, visible
browser mode, and the canonical command:

- `aeat config profile censo pull`

The setup commands succeeded:

- `aeat config profile create ...`
  - result: exit 0, profile created and active.
- `aeat config auth configure --provider clave_movil`
  - result: exit 0, provider configured, profile tax id present, Cl@ve identity
    present, identity alignment `matches`.
- `aeat config auth status --provider clave_movil`
  - result: exit 0, provider configured and available, not yet authenticated.

Live censo pull outcomes:

- QR-mode retry:
  - command: `aeat config profile censo pull`
  - result: exit 3
  - preflight emitted before failure: `auth_preflight=redacted`,
    `auth_provider=clave_movil`, `auth_identity_alignment=matches`,
    `auth_mode=qr`, `auth_probe_result=ok`.
  - AEAT route reached: `clave_movil_qr_request`.
  - failure: `auth_completion_timeout`.
  - diagnostic: `20260612T184841Z`.
  - verification code present: true.
- non-QR retry:
  - command: `aeat config profile censo pull`
  - result: exit 3
  - preflight emitted before failure: `auth_preflight=redacted`,
    `auth_provider=clave_movil`, `auth_identity_alignment=matches`,
    `auth_mode=non_qr`, `auth_probe_result=ok`.
  - AEAT route reached: `clave_movil_non_qr_request`.
  - failure: `auth_completion_timeout`.
  - diagnostic: `20260612T185117Z`.
  - verification code present: true.

Because Cl@ve completion did not finish, no live censo snapshot was captured in
this run and the follow-on `show`, `compare`, and `apply` commands were not run
against live censo facts.

## Plan status

`W02.P04.S10`, `W03.P05.S19`, and `W03.P06.S27` remain open. This record proves
the CLI preflight hardening and captures authenticated-live attempt evidence,
but it does not prove positive Modelo 036/censo retrieval or calendar
projection from live censo facts.
