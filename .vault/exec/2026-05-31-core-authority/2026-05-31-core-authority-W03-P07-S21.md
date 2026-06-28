---
tags:
  - '#exec'
  - '#core-authority'
step_id: S21
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P07.S21 — DELETE-001/002 ripgrep gate: BLOCKED

## Blocking Condition

The plan's own execution gate "after ripgrep confirms zero callers" was not
satisfied. `SYSTEM_BUCKET_ID` and `WORKFLOW_STATE_OBJECT_ID` in
`src/aeat/application/workflow/_events.py` have active callers at lines 103,
112, and 120 of the same file. They are used directly in the
`_load_and_update_workflow_state` function body and appear in `__all__`.

## Ripgrep Evidence

```
src/aeat/application/workflow/_events.py:103: bucket_id = fingerprint.recovered_bucket_id or SYSTEM_BUCKET_ID
src/aeat/application/workflow/_events.py:112: object_id=WORKFLOW_STATE_OBJECT_ID,
src/aeat/application/workflow/_events.py:120: object_id=WORKFLOW_STATE_OBJECT_ID,
src/aeat/application/workflow/_events.py:130: "SYSTEM_BUCKET_ID",
src/aeat/application/workflow/_events.py:131: "WORKFLOW_STATE_OBJECT_ID",
```

## Resolution

Step left unchecked. No code changes made. Requires a subsequent step to
first move callers to direct string literals or to a named config location
before deletion can proceed. Deferred to a future campaign.
