---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:52c1d136a920183afde06c64b72847b01dc4752714f272b8e9960531ffb40f2e'
step_id: 'S117'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rehome the Drive object-label derivation beside the hmac half of the same naming scheme, keeping it distinct from the manifest label whose policy differs

## Scope

- `src/cadrumo/adapters/outbound/storage/`
- `src/cadrumo/entrypoints/cli/_config/`

## Changes

- `M` `src/cadrumo/adapters/outbound/storage/_mirror_manifest.py`
- `M` `src/cadrumo/adapters/outbound/storage/__init__.py`
- `M` `src/cadrumo/entrypoints/cli/_config/_google.py`
- `M` `src/cadrumo/entrypoints/cli/_config/tests/test_google_sync_push.py`
- `verify:` `pytest src/cadrumo/adapters/outbound/storage -n 0 -m ""` -> `pass` (271; 4 live tests refuse without their env flag)
- `verify:` `pytest src/cadrumo/entrypoints/cli/_config/tests/test_google_sync_push.py -n 0 -m ""` -> `pass` (13)

## Notes

A mirrored row is named `<object-key-hmac>--<label>.bin`. The hmac half already
lived in the outbound adapter and the CLI delegated to it; the label half was
computed in the CLI. Both are facts about the wire, not about whichever surface
pushes.

Deliberately NOT merged with the adapter's `_manifest_label`, which names the
manifest file rather than a row: that one keeps the whole namespace, admits no
dots or underscores, and allows sixty-four characters. Neither policy is a
superset of the other.
