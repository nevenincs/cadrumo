---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:bbeca3526546f6ac8c26eb43a5c51f3d41631d26d707c8251dc8e624e789c51f'
step_id: 'S16'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# BLOCKED on the same specimen: wire aeat app live deudas pull calling the walker and DeudasService capture, named pull never capture or refresh or fetch or sync per the CLI contract

## Scope

- `src/cadrumo/entrypoints/cli/_app_live_deudas_cli.py`

## Description

- Not implemented. Blocked on S14's walker, which is itself blocked on a
  populated listing.

## Outcome

**DEFERRED CARRY-FORWARD. No `pull` verb was added.**

The verb's whole body is a call to the walker from S14 and
`DeudasService.capture`. The walker does not exist, so the verb would be a CLI
leaf that cannot do the thing its name promises.

Shipping it would also cost real surface for nothing: a new `tr` help key must
exist in all four locale catalogues the moment it appears in source, and the
leaf would need classifying in the write-guard census. That is a live operator
verb, a locale obligation and a guard entry, all to expose a call to a function
that is not there.

The naming decision the row exists to protect is recorded and unspent: the verb
is `pull`, never `capture`, `refresh`, `fetch` or `sync`.

## Notes

Mirror `expedientes_pull` when it is written: auth preflight, active-bucket
resolution, then the shared envelope. Its four locale values must land in the
same commit as the key, because the codebase-to-locale parity gate is tree-wide
and immediate.
