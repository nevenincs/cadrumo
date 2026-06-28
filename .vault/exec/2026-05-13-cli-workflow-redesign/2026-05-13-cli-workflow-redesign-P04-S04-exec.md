---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P04.S04'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P04.S04`

Wired both `auth.provider` (no-provider) and `auth.session`
(provider-without-session) warn branches to the ADR-canonical literal
`aeat config auth setup`. Updated the two failing dispatch tests
(`test_auth_check_no_provider_returns_warn_with_auth_setup_next_action`
and `test_auth_check_provider_configured_but_no_session_returns_warn`)
to assert the new exact string.

- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/application/test_diagnostics_dispatch.py`

## Tests

Both previously failing auth tests now pass; full dispatch suite
green.
