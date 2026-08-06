---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
body_hash: 'sha256:ce60b599be4ae843dae463255525f46cc98b82f0ab5a8ecafdda3589efe7a4a8'
step_id: 'S28'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Emit CENSO_APPLIED at cotejo artefact-apply and pin the emission site in the event contract test

## Scope

- `src/cadrumo/application/user_profile/`

## Description

- Re-enrol the dormant `CENSO_APPLIED` bucket event: `ProfileLifecycleService.record_censo_applied` is the single live emission site, called exactly once per apply-commit by `apply_cotejo` regardless of fact count, read back from the real event history repository in every apply-shaped test.
- Close the second-write-route hole the review adjudicated: `config profile censo file --apply` routes through the same apply authority instead of a bare fact write, so a censal artefact-apply can never persist silently without its audit event; the door's docstring now names the authority and the emission.

## Outcome

Landed as `8f004fcc51` with the routing fix in `c253a117c2` and the documentation-and-pin follow-up `4e51620cf8`. The emission is pinned fact-count-independent, the adopt-all door shape emits exactly one event, and the lifecycle docstring's claim about the file door is true at HEAD.

## Notes

- The event is live-dormant with the rest of the cotejo family until a G313 specimen pins the parser; the emission contract is fully tested against synthetically constructed certificates through the real encrypted write path.
