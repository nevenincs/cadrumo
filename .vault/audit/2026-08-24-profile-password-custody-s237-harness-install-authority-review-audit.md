---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:73f167901ae5b0dce5c2a51afc93d2131b3d5c0e0ad94a15c358b2d9908029c7'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `s237 harness install authority review`

## Scope

Reviewed the S237 production and test delta against the harness project metadata, root distribution boundary, current MCP entry point, stale-phrase inventory, focused refusal behavior, and path-scoped quality results.

## Findings

### sibling-install-authority | resolved | Live MCP guidance names the distribution that owns the runtime

The `cadrumo-harness` project declares the MCP SDK dependency and owns the `cadrumo-mcp` console script. Updated docstrings and refusal text consistently describe that sibling distribution, and the focused real tests assert both the complete missing-runtime hint and exact-version cohort guidance. No parallel installation helper or second authority was introduced.

### unrelated-harness-gates | low | Existing recovery and typing debt prevents a wholly green package-wide report

Two warm-runtime integration tests fail during profile creation because their existing non-interactive provisioning omits the now-required recovery secret channel. Path-scoped ty also reports two existing fallback-import diagnostics in `_harness_tools.py`. Neither failure is caused by or concealed by the S237 prose and hint correction; both remain honestly recorded for their owning work.

### cohort-command-punctuation | high | Sentence punctuation corrupted the final exact version token

Formal review found that the first exact-cohort refinement appended a period directly to the final `cadrumo-data-official` version requirement. The initial substring assertion stopped before that punctuation and therefore did not prove the complete copyable command.

### cohort-command-punctuation-resolved | resolved | The complete exact command is emitted and asserted

The period was removed from the command line, and the refusal test now asserts the complete four-package pinned suffix through its newline. Re-review and the repeated focused integration module pass with no remaining finding.

## Recommendations

- Close S237 if independent review confirms the emitted guidance and production inventory are truthful.
- Repair the warm-runtime provisioning witnesses under their recovery-enrollment owner rather than expanding this packaging-language Step.
- Keep copyable command assertions anchored through the final token and newline so presentation punctuation cannot enter a package requirement unnoticed.
