---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S06'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W01.P02.S06`

Scope: `src/aeat/application/user_profile/test_bundle_reexports.py`.

## Description

- Replaced absolute package imports with relative package imports.
- Preserved real package-surface assertions for user-profile re-exports.
- Verified focused user-profile re-export tests.

## Outcome

The test module no longer contributes to the absolute self-import baseline and
continues to validate the package public surface.

## Notes

No test double or monkeypatch was introduced.
