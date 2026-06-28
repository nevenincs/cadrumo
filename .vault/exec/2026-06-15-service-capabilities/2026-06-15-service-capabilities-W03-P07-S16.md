---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S16'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Gate every Google-write verb (verify, push, probe --no-read-only) on google_export with a no-allowlist conformance test (honesty review H1)

## Scope

- `src/aeat/entrypoints/cli/_config/_google.py`
- `src/aeat/entrypoints/cli/_config/_google_sync_calc.py`

## Description

- Route `calc verify` (creates + writes a Drive spreadsheet via `apply_export_plan`), `sync push` (mirrors secure-object ciphertext to Drive), and `sync probe --no-read-only` (sentinel Drive write) through the same `resolve_active_capability(GOOGLE_EXPORT)` refusal that `calc export` uses.
- Gate `probe` only on its write arm — the read-only connectivity probe stays open.
- Add a parametrized conformance test asserting every Google-write CLI leaf refuses with the capability message when `google_export` is off; the gate fires before any Google call, so it is deterministic without credentials.
- Absorb a broken-import regression: the two CLI config files imported `resolve_active_profile` from the deleted `_profile_binding` module — corrected to the renamed `_active_profile`.

## Outcome

Closes honesty-review finding H1 (and H2 by extension): the ADR claim that "the Google export entry points check `google_export`" is now true for every entry point. 9 capability CLI tests pass (4 new H1 cases) and the CLI builds. Committed as `fe474ff1d`.

## Notes

The commit was made with a bare `git commit` (no pathspec) and, due to the shared index, swept peer-staged work (a `filing/reconciliation` package removal + regenerated api stubs) into it. The resulting tree was verified consistent: clean `pytest --collect-only` (15960 collected, no import errors), conformant `apidocs scaffold --check`, no dangling imports of the removed package. The lesson (always `git commit -- <pathspec>`) is recorded in the close audit; the bundled peer work is committed, not lost.
