---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-27-secure-storage-production-hardening-w12-p21-s83-workflow-runtime-default-slice-exec]]'
---



# `secure-storage-production-hardening` Code Review

S83-WORKFLOW-RUNTIME-001 | FIXED | Explicit SQL URL could bypass runtime-default refusal in the no-pointer bootstrap branch

The first review found that `workflow_state_repository()` allowed the no-active-pointer bootstrap branch to open a bare repository even when an explicit `aeat_database_url` was configured. That would have let deprecated explicit SQL routing bypass the runtime-default guard. The slice now classifies the route before taking the bootstrap exception and refuses explicit SQL routing through the runtime factory. A regression test asserts the structured storage-runtime refusal and confirms the explicit database file is not created.

S83-WORKFLOW-RUNTIME-002 | FIXED | Workflow run injection semantics used truthiness rather than explicit `None`

The first review found that `WorkflowRunRepository` used truthiness for `objects=` injection while `WorkflowStateRepository` used an explicit `is not None` check. The implementation now preserves explicit injection by checking `objects is not None`.

S83-WORKFLOW-RUNTIME-003 | INFO | Re-review found no remaining findings

After the two fixes and the added explicit-route regression test, the `vaultspec-code-reviewer` re-reviewed the workflow runtime-default slice and reported no findings.
