---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P04.S03'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P04.S03`

Wired both `profile.active` (no-active-profile) and
`profile.required_keys` (missing-keys) warn branches to the
ADR-canonical literal
`aeat config init --tax-id <TAX_ID> --activity <ACTIVITY>` so every
profile-readiness fail row points at the same recovery command. The
`<TAX_ID>` / `<ACTIVITY>` brackets are operator-fill-in literals, not
Python f-string substitutions. Updated the dispatch test for the
missing-keys branch to assert the new canonical string instead of the
forwarded `report.next_action` field.

- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/application/test_diagnostics_dispatch.py`

## Tests

`test_profile_check_no_active_profile_returns_warn_with_setup_next_action`
and the renamed
`test_profile_check_missing_required_keys_returns_warn_with_canonical_next_action`
green under the P04 run.
