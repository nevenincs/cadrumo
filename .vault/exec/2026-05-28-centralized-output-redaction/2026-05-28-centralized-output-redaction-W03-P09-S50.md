---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S50'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---


# W03.P09.S50 command-output redaction canary matrix

Scope: add real command-output coverage for the centralized CLI rendering boundary across profile id, bucket id, tax id, URL, token, and object-key canaries.

## Description

- Add a `_emit` text and JSON canary matrix that captures production CLI transport output rather than asserting only helper internals.
- Extend CLI text assignment redaction so canonical profile and bucket assignment labels render as stable placeholders.
- Keep tax identifiers hashed, URL output host-only, bearer tokens fingerprinted, and secure object keys placeholdered in both text and JSON command output.
- Update core redaction coverage so text output distinguishes profile and bucket placeholders.

## Outcome

S50 is implemented. Focused ruff and pytest gates pass for the touched redaction, output rendering, and CLI output contract surfaces.

## Notes

No skipped work. No new pragma or noqa suppressions were added. The step keeps the existing centralized renderer contract and does not add command-local redaction.
