---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:fe722da1f92ce6f798c0b8402841a3f93633d495810f2e89a1b744c2e4a52502'
step_id: 'S33'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---

# Bind the two corpus distributions to project-level Trusted Publishers

## Scope

- `RELEASING.md`

## Changes

- `M` `RELEASING.md`

## Notes

The two corpus distributions carry project-level Trusted Publishers, and the primary name
its pending one. Confirmed by the operator, which is the only evidence that exists: a
publisher registration lives inside the account and no probe from this repository or
request to the index can observe one.

The runbook previously stated the two corpus bindings as outstanding. That was inferred
from the distributions existing on the index and never measured, so it was an assertion
about a surface this repository cannot see. It now states the rule that decides the
binding form and says plainly that the first publish run is what demonstrates all three.
