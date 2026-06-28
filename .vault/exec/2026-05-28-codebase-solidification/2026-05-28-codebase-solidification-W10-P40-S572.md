---
step_id: S572
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W10.P40.S572 — file_permissions.py os.environ allowlist doc

## Outcome

Added inline allowlist rationale comment in `src/aeat/core/file_permissions.py`
at the `os.environ.get` callsites for `SYSTEMROOT` and `USERDOMAIN` (lines 70, 72).

The comment explains: these are Windows OS-integration variables, not AEAT-prefixed
application configuration. The `test_settings_single_surface_invariant.py` scanner
only flags `AEAT_*` keys — these pass the scanner cleanly by design, so no
allowlist entry is added. Adding them would cause the `test_allowlisted_paths_still_contain_aeat_env_reads`
bitrot test to fail immediately.

The allowlist in `test_settings_single_surface_invariant.py` is not modified
because the scanner correctly clears these non-AEAT-prefixed reads.

## Grep post-condition

No bare string literal counts change (non-AEAT env vars, not in scope of scanner).
Inline rationale comment added at the allowlist-adjacent pattern.

## Commit

`5cc2fffd6`
