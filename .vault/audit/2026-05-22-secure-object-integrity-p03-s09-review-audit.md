---
tags:
  - '#audit'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---



# `secure-object-integrity` Code Review


S09-001 | HIGH | Root-fallback guard blocked bootstrap-safe help and read-only surfaces

The first guard shape refused every real, non-bootstrap-exempt invocation when storage classified as root fallback. Review found that this blocked nested help and read-only registry surfaces before their callbacks could render. The implementation was remediated by returning no verb path for help/version surfaces, restricting the guard to named profile-bound mutation verbs, and moving storage classification inside the guarded-verb branch.

Status: resolved. Fresh-root real CLI smokes confirmed `config --help`, `app ledger --help`, and `app registry legal view` exit cleanly while guarded mutation paths still refuse.

S09-002 | HIGH | Guarded mutation registry missed profile-bound write surfaces

Review found that the manual guarded-verb registry did not cover several mutation paths, including modelo verification/file/amend/import/reconcile/export, live verification persistence, profile census refresh/apply, inventory valuation preview, and ledger link/export. Those paths can persist bucket events, secure observations, links, or exported-state events and must not write through root fallback.

Status: resolved. The guarded registry now includes the surfaced mutation paths, and a direct predicate check asserts those paths are guarded while sampled read-only paths remain unguarded.

S09-003 | HIGH | `config profile switch` was incorrectly guarded

Review found that guarding `config profile switch` blocked a recovery/on-ramp path from no-active-profile state because the root callback refused before the switch command could resolve and activate the target profile bucket.

Status: resolved. `config profile switch` was removed from the guarded mutation registry. A fresh-root real CLI smoke now reaches the command's own unknown-profile refusal instead of the root-fallback no-active-profile guard.

S09-004 | INFO | Final review

Final scoped review found no remaining critical or high blockers in `src/aeat/entrypoints/cli/__init__.py`. Reviewer checked guard ordering, guarded verb list, predicate matching, argv extraction, and the profile-switch recovery path.
