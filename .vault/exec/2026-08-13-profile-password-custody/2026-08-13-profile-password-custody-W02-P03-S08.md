---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:00582519f3ed331ceaa309ff1c88fc6aa701d8f55a796afeca9944a302ab5102'
step_id: 'S08'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Terra XHigh consolidate committed-marker discovery and the existence-only retired-path detector/refusal without legacy reads or keyring probes

## Scope

- `src/cadrumo/application/workflow/_profile_bucket_scan.py`

## Description

- Consolidate profile-bucket reads on anchored committed-capsule discovery and remove independent manifest and bucket scans.
- Add the exact existence-only retired-member detector, typed refusal guidance, and current-marker integrity refusal before projection.
- Keep active-profile health observation-only: use an already authenticated record or custody session and return the typed unreadable-record precondition for a cold capsule.
- Move the MCP identity projection and its integration fixture to current registration plus explicit committed-envelope authentication.
- Prove real ready, absent, malformed, and cold cases without opening configured secret-store or custody-recovery paths.

## Outcome

Committed UUID capsules are the sole profile-health and workflow discovery source. Retired paths are only statted against the exact allowlist and are never parsed. Health assessment no longer constructs a provider or unlocks a cold capsule.

Focused custody, workflow, and state projection coverage passed 39 tests. The direct MCP current-identity integration passed. Scoped Ruff, formatting, Ty, and basedpyright checks passed; the production type check reported zero errors, warnings, and notes. Independent Sol review passed.

## Notes

No data was deleted and no compatibility path was added. Two shared-tree checks remain outside this step: the deferred cross-layer registry has peer-owned stale declarations, and full MCP server construction stops at obsolete CLI command-schema references before the identity route executes.
