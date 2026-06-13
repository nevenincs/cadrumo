---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

S88-SELF | INFO | Review opened for `W12.P22.S88`.
Scope: runtime write-policy query for CLI guarded profile-bound writes, bootstrap exemption preservation, deprecated `cli.config.init` locale cleanup, and focused real-behavior tests.

S88-001 | MEDIUM | Bootstrap-exempt root callback still attempts active-session open under broad suppression.
Reviewer found that `_activate_active_bucket_session` still called `ctx.with_resource(get_master_key_provider())` for bootstrap-exempt invocations when an active profile resolved and wrapped the activation in `contextlib.suppress(Exception)`. That violated the sessionless bootstrap exemption and hid custody/session activation defects instead of surfacing them.

S88-001-RESOLVED | PASS | Bootstrap-exempt root callback no longer opens or suppresses active-session activation.
The root callback now returns immediately for bootstrap-exempt verbs after write-policy inspection and active-profile resolution, so profile create/import/repair stay sessionless at the root boundary. Focused validation passed with `ruff check` over the changed S88 files and `pytest` over `test_storage_write_policy.py`, `test_root_fallback_write_guard.py`, and `test_repair_bootstrap_exempt.py` with 59 passing tests. A wider profile-create custody gate still fails because the wizard/profile lifecycle storage span opens the master-key provider before provisioning custody; that remaining issue is owned by `W12.P22.S89`, not the S88 route-policy delegation.

S88-001 | MEDIUM | Bootstrap-exempt verbs still attempt a bucket session and swallow all activation failures.
`src/aeat/entrypoints/cli/__init__.py` lines 220-230 route bootstrap-exempt invocations with an active profile through `ctx.with_resource(get_master_key_provider())` inside `contextlib.suppress(Exception)`. That means exempt verbs are no longer strictly sessionless when a profile resolves, and any custody/session activation defect is hidden rather than surfaced or logged. This violates the S88 bootstrap exemption requirement and the audit criterion forbidding broad swallowing from hiding real defects.

S88-REVIEW-REMEDIATION | PASS | Narrow re-review after remediation passes.
Bootstrap-exempt invocations now return before root callback session activation; no broad `contextlib.suppress(Exception)` path remains in the scoped root callback, and `ctx.with_resource(get_master_key_provider())` is reachable only after the non-exempt gate. The known wider profile-create custody failure remains scoped to `W12.P22.S89` and is not an S88 route-policy blocker.
