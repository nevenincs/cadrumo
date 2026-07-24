---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S29'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Run the docs build and documented-command conformance gates green, with owner triage recorded for any unrelated peer failures

## Scope

- `docs/`

## Description

- Regenerate apidocs stubs in the retirement commit (two stale stubs removed, wizard and tui toctrees refreshed); `scaffold --check` clean.
- Run the documented-command and JSON-schema conformance gates: green (independently re-verified at pushed HEAD, 501 passed at integration scope).
- Run the full docs build gate (`dev/docs/tests/test_docs_build.py`) with complete on-disk log capture: 8 failed, 15 passed.

## Outcome

Every substrate-owned docs surface is green: the apidocs tree matches the module tree, no orphan stubs, conformance gates pass, and the wizard/flows/tui reference pages build. The docs build gate is red only on peer-owned in-flight work (see Notes); no failing surface belongs to this campaign.

## Notes

- Owner triage: all 8 docs-build failures reduce to ONE signature — `CadrumoError subclass cadrumo.application.auth._apoderado.ApoderadoRepresentedNifInvalidError is missing a declared ErrorCode registry entry`, raised by the `cli-sequence` directive on every build variant (nitpicky, user-scope, es/ca/hu localized, site-identity, sequence-widget). The class exists only in a peer campaign's uncommitted working-tree edits to the auth/apoderado files; the registry row lands with their commit. The gate's own message anticipates exactly this concurrent-process state.
- The step stays open until the docs build is re-run green after the peer lands; the substrate side is complete.
