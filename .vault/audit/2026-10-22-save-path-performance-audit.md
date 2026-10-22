---
tags:
  - '#audit'
  - '#save-path-performance'
date: '2026-10-22'
modified: '2026-10-22'
body_schema: 'body-v2'
body_hash: 'sha256:97552226fbe3d9b5c3ff7f330babdd4a2047ae888cd71f196366ecd977fcd443'
related:
  - "[[2026-10-22-save-path-performance-plan]]"
---

# `save-path-performance` audit: `Save path measurement`

## Scope

S07 of `2026-10-22-save-path-performance-plan`: the before and after measurement of the TUI profile save path. An external harness outside the repository ran a caller-owned runtime (`cadrumo-runtime --configured-root`) on a scratch storage root holding an encrypted clone of a real-sized operator profile. It drove `ProfileManagerClientComposition._field` (the TUI's field-save door, mutation then overview re-read) and the installed TUI headless through `launcher.main(headless=True, auto_pilot=...)`. The pre-plan tree (`d25e26839d`) and HEAD (`c9c4ee9e8b`), each exported with `git archive`, ran alternately in one time window with near-pristine probes (audit-hook file events, SQL, frames, per-process CPU; no per-function spans), then once each with full per-function counts. The range also contains other sessions' startup-performance commits, so wall time is the combined effect and the counts attribute it. The host was shared and loaded; medians over 8 saves per run.

## Findings

### save-path-wall | low | A TUI profile save takes about half the wall time of the pre-plan tree

Warm save median: pre-plan 4.04 s and 3.27 s in two rounds; HEAD 1.77 s in both. Mutation round trip about 1.4 s to 0.75 s; overview re-read about 1.7-2.7 s to 0.97 s. Runtime CPU per save 1.20-1.34 s to 0.40-0.43 s; worker 1.57-1.63 s to 1.39-1.41 s. The real TUI save on HEAD, from the save button press to the applied revision, has a median of 1.14 s (1.22 s including paint). Full per-save counts, pre-plan to HEAD: runtime Python calls 618,008 to 33,930; worker-runtime handshakes 74 to 0; runtime frozen-model hash calls 394,903 to 3,849; runtime file events 354 to 78; worker file events 603 to 164. SQL stayed about 140-160 statements and 6-10 ms per save, and fsync about 21 calls and 55 ms, both negligible throughout.

### worker-overview-reread | medium | Worker work for the post-save overview re-read now dominates a save

Worker Python calls per save did not move (176,108 to 179,518). The overview re-read is about 55% of a HEAD save. It runs as five durable profile-view operations, each journaled, and renders localized field views (about 2,160 `tr` calls per save before the plan). `src/cadrumo_runtime/host/frontend/tui/profile/manager_client.py:197` re-reads the whole overview after every field mutation. This path belongs to S09 of `2026-10-22-startup-performance-plan`, which so far changed only Home's first screen (`35934fefa0`).

### frontend-login-observation | medium | Login observation still captures the desktop logon on frontend requests

On the S04 harness run the runtime made about 5,460 `windows_desktop_logon:_sid_text_valid` calls per save, from login observation for frontend requests, not from the worker channel. `_collect_windows_logins` and `windows_desktop_sessions` still accounted for about 0.45 s exclusive per instrumented save after S04. The owner of `2026-10-22-startup-performance-authority-observation-adr` changed holding for logons without a lock surface (`7ab611be90`) and the aged-observation probe. A HEAD measurement after that probe change is still needed.

### pre-plan-tui-run-hang | low | The pre-plan tree's headless TUI run hung before sign-in

The pre-plan run of the TUI driver produced no iteration and was stopped by its 20-minute timeout. The HEAD run completed. Not triaged, and not reproduced on HEAD.

### stale-index-locks | low | Empty worktree index locks were left without a holding process

Four empty `index.lock` files in the shared tui worktree, at about 16:14, 17:37, 19:54 and 19:59, each had no git process holding it. They were removed only after checking. Long-running git calls killed by tool timeouts during hooks are the likely cause. Read-only git now runs with `--no-optional-locks`, and commits run with long timeouts.

## Recommendations

- worker-overview-reread: either return the committed overview, or the changed section, with the field mutation result, or keep the re-read off the durable journal. Changing the mutation result is a protocol change that needs an ADR, which S09's owner should weigh.
- frontend-login-observation: re-measure on HEAD after the aged-observation probe. If the cost remains, the authority-observation ADR's owner should decide whether a frontend connection's login capture can be held per connection like the worker's peer identity.
- pre-plan-tui-run-hang: only reproduce it if a regression on HEAD shows the same symptom.
