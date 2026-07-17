---
tags:
  - '#exec'
  - '#arch-remediation-engine-lifecycle'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S06'
related:
  - "[[2026-07-02-arch-remediation-engine-lifecycle-plan]]"
---

# Sweep the shared secure-SQL harness ephemeral and synthetic-session path onto the unified lifecycle so engine routing follows the session through the harness teardown

## Scope

- `src/aeat/tests/secure_sql.py`

## Description

- Sweep `secure_sql.py`: `isolated_runtime_profile` and `isolated_two_bucket_runtime` close their sessions in teardown so disposal follows the session.
- Remove the stranding mid-session `dispose_engine` in `isolated_cli_runtime_profile` (it would orphan the session's registered handle).
- Keep `dispose_engine` in the ephemeral/sessionless helpers as the sanctioned teardown seam.

## Outcome

The harness routes engine disposal through the session lifecycle; URL-keyed helpers keep the teardown seam.

Landed in commit `38e62c216`.

## Notes
