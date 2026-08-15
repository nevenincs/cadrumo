---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f4e8e8cfe897fa581f96707235ed45d508ffe310301612c58682197632d6af2a'
step_id: 'S166'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh compose the full-corpus collectability proof into a lane that is actually run, since the harness that would have caught two test packages being uncollectable is real and mutation-tested but is enrolled only in a standalone recipe every other lane ignores and in a single separately-named continuous-integration job, so every routine local and integration run stayed green throughout the window those packages could not import, and a green lane structurally unable to see a collection error is what makes one read as infrastructure noise and get scrolled past

## Scope

- `justfile and .github/workflows/ci.yml`

## Description

## Outcome

## Notes
