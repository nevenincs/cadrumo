---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:23845bad508daf227157014451c03790d8e8ff71931afcd23ce37de587cc6c41'
step_id: 'S112'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rehome the ledger folder-import aggregation and the Drive remote-object label derivation, both of which the CLI computes with no application or adapter counterpart

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `verify:` `aggregate_ledger_import_results` at `application/ledger/actions_import.py:615`
- `verify:` `remote_mirror_object_label` at `adapters/outbound/storage/_mirror_manifest.py:415`

## Notes

Both rehomings landed earlier in the campaign: the folder-import aggregation now
has an application counterpart and the Drive remote-object label derivation an
adapter one, so neither is computed in the CLI without a home.

Its sibling S115 stays open and is a different thing -- widening that fold so a
directory import reports every file's report rather than only the first.
