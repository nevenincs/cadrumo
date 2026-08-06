---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:04da6f0ccc918ad11824a413d711d551850b10b95569b5ae8f16295bbb166f0d'
step_id: 'S138'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Update root fallback write classification without accepting removed command paths

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_root_fallback_write_guard.py`

## Description

- Read the root fallback write guard module and enumerate its assertions.
- Confirm the guard classifies write paths without accepting any removed command path.
- Run the module and confirm it passes with no marker filter and no parallel deselection.

## Outcome

The named surface already classifies root fallback writes without accepting a removed command path, and does so structurally rather than by listing forbidden strings: it asserts that every guarded write path names a live command, which makes accepting a removed path impossible without failing.

That assertion carries its own anti-tautology proof, which confirms a stale catalogue entry is rejected, so the guard is not vacuous. The module also proves the guard leaves read and recovery paths open and that the CLI root delegates route classification to the backend policy rather than duplicating it. The module runs green under an explicit empty marker expression and without parallelism, so no lane was silently deselected.

## Notes

No code change was required by this Step. The implementing change had already landed under the successor plans this document was rescoped into, so the row was stale rather than unexecuted. The Step is closed as verified-satisfied against its named surface, per the Wave W06 instruction that each open W05 Step be verified against that surface before being checked and never inferred from the live command tree alone.
