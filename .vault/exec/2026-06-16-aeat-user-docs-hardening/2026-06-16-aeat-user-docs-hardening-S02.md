---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S02'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden censo-update.md

## Scope

- `docs/how-to/censo-update.md`

## Description

- Verify-close: read `censo-update.md` against its 2026-06-18-audit findings (the systemic S-AUTH / S-PASS / S-PREREQ patterns that touch every live-read page) and confirm resolution at HEAD.
- Confirm S-AUTH: the page requires configured read-only AEAT authentication and links the authenticate guide; the pull-vs-apply separation is explicit (pull saves a snapshot, apply writes reviewed facts locally, nothing is submitted to AEAT).
- Confirm S-PASS (master-key passphrase prerequisite) and the never-file-036 / never-submit boundary are stated.

## Outcome

- Page verified compliant at HEAD; the S-AUTH / S-PASS patterns are addressed. Delta: none required.

## Notes

- `aeat config profile censo pull` / compare / apply cited per the pull-and-file standard; local audit history documented. CLI conformance gate green.
