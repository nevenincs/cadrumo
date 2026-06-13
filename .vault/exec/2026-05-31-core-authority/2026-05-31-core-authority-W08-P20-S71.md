---
tags:
  - '#exec'
  - '#core-authority'
step_id: S71
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P20.S71 - remaining bi-directional auth adapter import edges

## Outcome

The module-scope import-time cycle between application/auth/_sessions.py and
adapters/outbound/aeat/auth was broken in S70. S71 documents the remaining
local_scope edges and their structural classification.

Remaining application->adapters edges in application/auth/ (local_scope context):
- `_sessions.py` lines 65, 236, 354, 491, 571: browser factory, AeatLoginAssertionError,
  storage imports — all inside function bodies (local_scope). These are NOT import-time
  cycle edges; they are runtime-deferred adapter calls.
- `_operator.py` lines 229, 670, 807, 905, 932: certificate and clave_movil adapter imports
  (local_scope inside operator functions).
- `_apoderado.py` lines 28-33: persistence storage imports (normal-scope, addressed in S79).
- `_diagnostics.py` lines 12-14: persistence storage imports (normal-scope, addressed in S79).

Remaining adapters->application edges (protect-list classified):
- `adapters/outbound/aeat/auth/_providers.py:15`: imports `AuthProvider, AuthProviderKind,
  describe_provider_operator_impact` from `application.auth`. This is on the protect list
  as `aeat.application.auth` hybrid LEGITIMATE canonical site. NOT a violation.
- `adapters/outbound/aeat/auth/_authenticator.py:1146`: local_scope import of
  `application.workflow._models` for `require_active_bucket_id`. Structurally entangled.
- `adapters/outbound/aeat/auth/_clave_movil.py:746-749,860`: local_scope imports of
  `application.user_profile._orchestration`, `application.user_profile._projections`,
  `application.workflow._models`, `application.workflow._profile_bucket_scan`.
  These represent adapter->application upward dependencies for profile/workflow context.

STRUCTURAL BLOCK NOTE: The _clave_movil.py and _authenticator.py local_scope imports of
application.workflow and application.user_profile cannot be removed without extracting
the profile-bucket-scan and workflow-model query logic to a shared domain Protocol. This
is a larger refactor not in W08 scope. The import-TIME cycle is broken; the remaining
edges are structural violations tracked under RELOC-032.

MIGRATE-001, Rule 2.

## Commit

S69+S70 commit: `c1ab6234d`.
S71 is a documentation-only step; the import-time cycle was broken in S70.

## Files touched

No additional code changes for S71.

## Verification

Auth application suite: 59 passed (test_operator.py excluded — pre-existing
AttachmentStoreProtocol import failure unrelated to auth).
Auth adapter suite: 129 passed, 9 pre-existing failures in test_clave_movil.py
(settings-defaults regression predating this Wave; not caused by W08 changes).

P20 close gate: `rg "from ...adapters" src/aeat/application/auth/_sessions.py`
shows zero module-scope application->adapters edges (the import-time cycle is severed).
