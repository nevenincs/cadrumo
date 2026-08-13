---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d6ed72ebd9fdac93c1d03c059d6106a2fad27a3ac25ac098ab410c4bbc3d66d2'
step_id: 'S03'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
---

# expose the filed sweep dry-run flag and carry its state as primary result data on the envelope, never as a notice

## Scope

- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

FOUND DELIVERED. This record was authored retroactively; no execution record
existed at delivery time, so the step was carried by its commit alone until
now.

- Delivered by `a6792147dd`, "report a bulk filed pull that wrote nothing, and
  refuse it in single mode".

## Outcome

Verified present at HEAD by reading, not by running:

- `--dry-run` is threaded from the CLI into `capture_filed_data_bulk`.
- `FiledCaptureResult` carries a `dry_run: bool = False` field and the bulk
  branch sets it from `report.dry_run`; the field rides the envelope's
  `result` payload, never the `notices` channel.
- Single-modelo capture has no dry-run path, so the flag is refused there with
  `typer.BadParameter` rather than silently accepted and performing a real
  write.
- The text-mode line emits from the same field the JSON result carries, so the
  two transports cannot disagree about whether anything was written.

A dedicated regression test already exists at
`src/cadrumo/entrypoints/cli/tests/test_app_live_filed_dry_run_surface.py`,
covering: `dry_run` is addressable on the result schema, it defaults to
`False` so an omission never reads as an unstated preview, and text mode
agrees with the JSON field for both `True` and `False`.

## Notes

Nothing here was run beyond the pre-existing regression suite. Every
statement above is read off the source and the existing test file at HEAD.
