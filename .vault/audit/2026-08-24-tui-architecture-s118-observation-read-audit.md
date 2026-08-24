---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d6cee5bbb4c5e4e968166b5c32e15ae48e7a4dc17fb220bbe69357ef6f7a0937'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
---
# `tui-architecture` audit: `S118 observation read`

## Scope

Formal read-only review of `W02.P19.S118` against the accepted operation-observation decision. Reviewed the application port and public facade, the real filesystem adapter and shared journal substrate, and the focused real-filesystem tests for one locked record, typed error dispositions, replay/progress anchoring, helper ownership, and imports.

## Findings

### root-validation-before-lock | high | Observation creates a lock sidecar before refusing an unsafe journal root

`src/cadrumo/adapters/persistence/operations/_journal.py:124` acquires the journal lock before `super().load` validates the journal root at `src/cadrumo/application/_journal_repository.py:130`. The lock primitive creates its parent and sidecar at `src/cadrumo/core/locks.py:193`, so an unknown-operation read materializes an absent journal directory without the normal hardened-root setup. More seriously, if that root is a symlink or junction, lock creation follows it and creates `.repository.lock` in the link target before `load` refuses the unsafe root. Validate or establish the root through the hardened repository path before opening the sidecar, then retain the same lock for the record read.

### atomicity-page-witness | low | Interleaving witness does not distinguish a split replay read

`src/cadrumo/adapters/persistence/operations/tests/test_journal.py:425` requests `after_cursor=1` with `limit=2`. Both the pre-transition and successor records therefore yield the identical replay page `(2, 3)`. A future two-read implementation could take that older page, then take the successor snapshot and full progress history, and still satisfy the accepted successor shape at `src/cadrumo/adapters/persistence/operations/tests/test_journal.py:451`. The present adapter performs one locked load and has no such join, but this witness would not fail if that invariant regressed. Use a page limit that crosses the transition and assert the page plus `next_cursor` correlate with the same initial or successor anchor.

### atomicity-lock-barrier | low | Interleaving witness does not prove the observer reached lock acquisition

The subprocess signals readiness before invoking the observation read at `src/cadrumo/adapters/persistence/operations/tests/test_journal.py:235`, while the parent treats that signal and an empty queue as proof that the read is blocked at `src/cadrumo/adapters/persistence/operations/tests/test_journal.py:429`. A delayed subprocess can satisfy both checks without reaching the lock boundary; after release, either allowed result still passes. Instrument the actual lock-acquisition boundary or add deterministic coordination that proves both workers reached it before release.

No other findings. The current adapter derives snapshot, bounded replay, and full progress-fold input from one loaded record under the canonical journal lock; absent and ahead states use application-owned typed exceptions; corrupt records rethrow as repository errors; replay construction is canonicalized in one helper; the bounded-page/progress-suffix test covers a later progress event; and imports use the owning package facades.

## Recommendations

Resolve `root-validation-before-lock` before S118 closes. Strengthen both atomicity witnesses, then rerun the focused journal suite. No other production implementation change is indicated.
