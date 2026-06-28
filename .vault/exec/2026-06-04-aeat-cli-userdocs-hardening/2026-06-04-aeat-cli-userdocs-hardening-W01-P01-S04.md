---
tags:
  - '#exec'
  - '#aeat-cli-userdocs-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S04'
related:
  - '[[2026-06-04-aeat-cli-userdocs-hardening-plan]]'
---

# `aeat-cli-userdocs-hardening` `W01.P01.S04` execution

Scope: Capture runtime help-language anomalies and distinguish runtime flags from import-time language pinning.

## Description

- Sample runtime help with `uv run aeat --language en`.
- Compare observed help-language behavior across config and app surfaces.
- Record the distinction between `--language en` and `AEAT_OUTPUT_LANGUAGE=en` before CLI module import.

## Outcome

Completed. The plan records that some help text still renders Spanish under runtime `--language en`, while generated-reference behavior depends on `AEAT_OUTPUT_LANGUAGE=en` before import. This is now a mitigation item for localization and documentation trust.

## Notes

No source files were changed for this step. The finding should be addressed before handbook pages promise that runtime help and generated English reference always match.
