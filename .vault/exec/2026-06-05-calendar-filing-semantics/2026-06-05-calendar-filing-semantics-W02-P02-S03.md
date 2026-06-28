---
tags:
  - '#exec'
  - '#calendar-filing-semantics'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S03'
related:
  - '[[2026-06-05-calendar-filing-semantics-plan]]'
---

# `calendar-filing-semantics` `W02.P02.S03`

Scope: add application and CLI regression tests for dual filing states.

## Description

- Add application tests proving local Modelo records do not imply AEAT submission.
- Add application tests proving expedientes rows mark AEAT submission observed but not justificante verified.
- Add application tests proving stored filed-declaration justificante artefacts promote AEAT verification while storageless or generic observations do not.
- Add application tests proving imported justificante evidence marks AEAT verificante state without implying a local calculation.
- Add application tests proving calendar filing event rows inherit verified justificante evidence when the filed-declaration store contains a matching artefact.
- Add CLI JSON assertion for AEAT submission state and justificante verification on persisted filing events.
- Add CLI secure-storage regression proving filed evidence is scoped to the current profile session.

## Outcome

Focused tests now guard the clarified filing vocabulary: local ready-to-file, AEAT observed submission, stored justificante verification, and cross-profile evidence isolation are separate states.

## Notes

The current shared profiles are incomplete, so local command verification exercised event evidence in persisted snapshots; entry-level evidence is covered by deterministic application tests using real domain records.
