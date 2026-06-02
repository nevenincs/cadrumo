---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
step_id: 'S51'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# W03.P09.S51 workflow output redaction expectations

Scope: update the live workflow-verification test surface after centralized output redaction, replacing the removed apex test target with the current accepted CLI workflow verification file.

## Description

- Preserve operator-facing `active_profile` display labels in workflow status output while keeping machine identifiers redacted.
- Make the central `active_profile` redaction rule value-aware so UUID-shaped raw profile references are placeholdered and display labels are not.
- Replace the repair diagnostic literal active-profile sentinel with the shared CLI profile placeholder constant.
- Update workflow tests to assert centralized profile and bucket placeholders via shared constants.

## Outcome

S51 is implemented against the current worktree surface. The old apex workflow test path no longer exists; the live equivalent is `test_cli_workflow_verification.py`.

## Notes

Focused ruff passed. Focused pytest passed for core redaction, workflow verification, and the S49 repair privacy regressions. No new suppressions were added.
