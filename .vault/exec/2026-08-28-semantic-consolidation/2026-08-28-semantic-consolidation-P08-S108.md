---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:ceb899659bb532abd2c5b3207a90a7bd9a283d7cd5a14d3ca71706ed49effbd6'
step_id: 'S108'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Detect a name imported from a genuinely inert namespace, distinguishing it from one reached through a live lazy export map

## Scope

- `src/cadrumo/tests/`

## Changes

- `verify:` `src/cadrumo/tests/test_inert_namespace_imports_resolve.py` exists and is green

## Notes

The gate refuses a name imported from a namespace that exports nothing, which is
the distinction the step asks for: a genuinely inert namespace against one still
served by a live lazy export map.

Worth recording how it was narrowed. The first version read `core`'s lazy map as
empty and produced 6,803 false positives -- it could not tell "exports nothing"
from "exports lazily", which is precisely the distinction it exists to draw. It
was narrowed to namespaces that are genuinely inert.
