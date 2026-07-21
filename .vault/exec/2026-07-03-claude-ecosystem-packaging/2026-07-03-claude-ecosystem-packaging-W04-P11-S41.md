---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S41'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

# Document the aeat-data file-size grant request template and the publish-when-granted flow so the plugin delivery is not hard-blocked on the grant

## Scope

- `RELEASING.md`

## Description

- Document the `aeat-data` file-size grant flow: `github.com/pypi/support` `limit-request-file.yml`, 200 MB request, the reviewed/license-clean/integrity-hashed justification wording, `torch` precedent, and the no-SLA warning (file early, schedule nothing against it).
- Commit `3ebe536354`.

## Outcome

- The grant request is a documented, repeatable step rather than tribal knowledge.

## Notes

Executed inline by the coordinator during the account rate-limit window.
