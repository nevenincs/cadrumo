---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S10'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W01.P03.S10`

Scope: `src/aeat/adapters/outbound/google/test_document_link_resolver.py`.

## Description

- Removed the undocumented module-level monkeypatch service swaps from the
  resolver tests.
- Kept `resolve_document_link` credential-owned by removing the public Drive
  service injection keyword after code review.
- Verified Google document-link resolver tests and monkeypatch inventory.

## Outcome

The Google resolver tests no longer use undocumented `monkeypatch.setattr` sites,
and the public resolver no longer exposes a Drive service bypass.

## Notes

Focused download behavior is covered through a private service-bound helper; the
production resolver still builds the Google Drive service from credentials.
