---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:48bdce4ec8d9511a33d3188f1d5d85a2e06ac297ee731abb09e6344147286228'
step_id: 'S03'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
---

# emit a truncation notice when a sweep is limited, so a partial run cannot read as complete coverage

## Scope

- `src/cadrumo/entrypoints/cli/_app_live.py`

## Description

FOUND DELIVERED. This record was authored retroactively; no execution record
existed at delivery time, so the step was carried by its commit alone until
now.

- Delivered by `03e1b8b9d9`, "say when a filed sweep stopped on its limit".

## Outcome

Verified present at HEAD by reading, not by running:

- Both `--limit`-bearing filed-read lanes (single and bulk) build a
  truncation notice through one shared builder rather than two independent
  ones, so the two lanes cannot disagree about when a sweep was cut short.
- The predicate is `reached_count >= limit`, never `captured_count`. The
  commit's own rationale: `captured_count` is `len(observation_paths)`,
  appended only on the write path, so a preview (`dry_run=True`) would leave
  it at zero and `captured_count >= limit` would read `False` exactly when a
  dry run WAS truncated — the one surface with no other signal, since
  `--dry-run` and `--limit` compose on the bulk lane.
- `reached_count` reaches the envelope as a REQUIRED field rather than a
  defaultable one, so a dropped key cannot silently assert a complete sweep.

Scoped only to the filed sweep, matching the row's own scope clause: the
Sheets export has no `--limit` concept to truncate against — it materialises
one modelo/period/year workbook in a single write, not a sweep over many
items — so no analogous notice applies there.

## Notes

Nothing here was run. Every statement above is read off the source and the
commit's own message at HEAD; verification belongs to the gate owner.
