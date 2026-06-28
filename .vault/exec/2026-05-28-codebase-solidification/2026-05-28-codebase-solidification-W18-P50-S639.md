---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S639
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W18.P50.S639

Canonicalized the `cast()` rationale token in `_engine.py`.

- Modified: `src/aeat/application/workflow/_engine.py`

## Description

The existing token `CAST-RATIONALE-WORKFLOW-ENGINE-SITE-HEALTH-STATUS` was renamed to `CAST-RATIONALE-WORKFLOW-SITE-HEALTH-STATUS` (removing the redundant `-ENGINE-` segment) to match the canonical slug. The prose rationale (`SiteHealthError` types its payload through `SiteHealthStatusLike` protocol so `core.errors` need not import the browser adapter; every site-health failure carries the concrete `SiteHealthStatus`; narrowed at adapter boundary) was preserved verbatim.

## Tests

Grep-post confirmed token present on the comment line immediately preceding the `cast(` call. `test_cast_rationale_inventory.py` passes with 0 violations. `test_w18_p50_closure.py::test_s639_workflow_site_health_status_token_present` passes.
