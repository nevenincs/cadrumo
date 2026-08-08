---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:f4706c2778dbb602a2a62b4a33a50ef38193bce97cea6f9c0fa08c860c653278'
step_id: 'S11'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Wire aeat app live deudas list, view and latest into the app live command group, matching the expedientes latest, list, view verb shape exactly

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Verify rather than author: the wiring for this row was already on disk.
- Confirm the command family is mounted on the live app group and that its verb
  shape matches the sibling expedientes family exactly, which is the row's
  stated acceptance criterion.

## Outcome

`register_deudas_commands` is imported in
`src/cadrumo/entrypoints/cli/_app_live.py` and invoked there with the
active-bucket resolver, mounting the family under `deudas`.

The verb shape matches the expedientes family on the three read verbs, and
diverges from it deliberately in one respect: expedientes carries a `pull`
verb and deudas does not. That is not an incomplete match. Fetching the debts
consulta needs an operator-authorised specimen of that AEAT page, and the
adapter's read-landing guard refuses every landing until one exists, so a
`pull` verb here would be a surface that cannot legally execute. The row asks
for the list, view and latest shapes to match, and they do.

The registration takes no auth preflight, which is correct rather than an
omission: every verb in the family reads persisted bucket storage and none
crosses a wire, so there is no live session to preflight.

## Verification

    rg -n "deudas" src/cadrumo/entrypoints/cli/_app_live.py
    61:from ._app_live_deudas_cli import register_deudas_commands
    1631:register_deudas_commands(app, active_bucket_id=active_bucket_id_or_refuse)

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_live_deudas_verbs.py -m integration -n0 -q
    8 passed in 6.97s

One of those eight, asserting the family exposes exactly list, view and latest,
is the direct gate on this row's verb shape.

## Notes

The content predates this record and landed in commit `ed09a6dd4b`
("feat(cadrumo): land the in-flight source work"), a bare whole-index commit
whose subject names neither deudas nor this row.
