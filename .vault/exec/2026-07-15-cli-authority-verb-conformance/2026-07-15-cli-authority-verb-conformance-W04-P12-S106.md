---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:341101737af29239128b9d2014aaf6671485ea0654de4cecdf632f2402276296'
step_id: 'S106'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Replace recovery display and rotation spellings with recovery status, create, and rotate

## Scope

- `src/cadrumo/entrypoints/cli/_config/_custody_secret.py`

## Description

The old recovery display and rotation spellings (`show-recovery`, and any bespoke rotate
door) had to be replaced by a `config recovery` subgroup exposing exactly `status`,
`create`, and `rotate` as its inspection/enrollment leaves (`verify` is covered separately
by S107).

## Outcome

`_register_recovery_commands` in `src/cadrumo/entrypoints/cli/_config/_custody_secret.py:292-401`
registers a `recovery` Typer subgroup with `status` (line 300, read-only, reports
`recovery_enrolled`/`recovery_fingerprint` via `inspect_recovery_status`, never a secret),
`create` (line 332, delegates to `_run_recovery_enrollment(..., rotate=False)`), and
`rotate` (line 345, `rotate=True`). `_run_recovery_enrollment` (lines 404-456) refuses a
first `create` when already enrolled and requires existing enrollment for `rotate` via the
underlying `create_recovery_code`/`rotate_recovery_code` application calls. No
`show-recovery` command, string, or alias exists in `src/cadrumo/entrypoints/cli`
(confirmed by `rg` returning zero production hits for that spelling).

## Notes

Verified by direct file read of `_custody_secret.py` and `rg` sweep for the retired
`show-recovery` spelling across `src/cadrumo/entrypoints/cli`. Cited the coordinator's gate
run (parallel 154/1 failed, serial 27/1 failed, the one failure being the unrelated S112
gap) rather than re-executing the suite. RAG code index is degraded/truncated; this
verification used `rg` and direct reads only.
