---
tags: ['#exec', '#modelo-export-evidence-parity']
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S05'
related:
  - '[[2026-06-03-modelo-export-evidence-parity-plan]]'
---

# `modelo-export-evidence-parity` `W01.P01.S05` step record

Scope: `W01.P01.S05` - Capture guard for evidence contributor coverage.

## Description

- Add `assert_evidence_covers_snapshot` to reject evidence bundles whose row ids differ from the fingerprint snapshot row ids.
- Cover the missing-contributor failure path and complete-bundle success path.
- Stage verify-time guard wiring so verified revisions cannot persist an evidence bundle that omits a fingerprinted contributor.

## Outcome

The capture layer now has an explicit no-silent-omission guard for bundled evidence coverage.

## Notes

The working-tree copy of `_actions.py` contains unrelated shared WIP; the S05 commit stages only the guard import/call from a synthetic `HEAD`-based index blob.
