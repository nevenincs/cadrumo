---
tags:
  - '#plan'
  - '#save-path-performance'
date: '2026-10-22'
tier: L1
related:
  - '[[2026-10-22-worker-authorization-channel-adr]]'
modified: '2026-10-22'
body_schema: body-v2
body_hash: 'sha256:105f0fff4440f269780056f5705a8ef3b9813311f29f1a869d1ad2b2d7009612'
---

# `save-path-performance` plan

Make a TUI profile save fast by removing the per-save runtime, worker and filesystem costs an external harness measured.

## Description

Approved 2026-10-22. Basis: the operator's instructions in this session, "begin delegating the optimization work to opus 5.5 agents (medium or high)" and "go" with "adr was approved too", given after the harness findings were presented.

An external harness outside the repository drove TUI profile field saves (`ProfileManagerClientComposition._field`, and the installed TUI headless through its autopilot door) against a caller-owned runtime and a clone of a real-sized profile. One save took 1.5-2 s. Database work was 6.5 ms and fsync 54 ms. The cost was CPU in authorization and protocol work: a quadratic scope intersection, 72 fresh worker authorization connections per save, a per-record log reopen, a per-handshake distribution scan, about 4,300 per-component custody opens and a journal root creation on every journal call.

Decision coverage: S04 implements `2026-10-22-worker-authorization-channel-adr`. S01-S03, S05 and S06 are implementation within existing decisions and change no contract, protocol or persisted schema; S05 keeps every containment, link and ownership refusal the custody primitives make today. The logon-inventory cost that remains on a caller-owned runtime belongs to `2026-10-22-startup-performance-authority-observation-adr` and was handed to that plan's owner. The overview re-read after a save belongs to S09 of `2026-10-22-startup-performance-plan`. Neither is in this plan.

## Steps

- [x] `S01` - Intersect access scopes with set algebra bounded to what one access names; `src/cadrumo/application/user_profile/access_policy.py, operation_access_policy.py and tests`.
- [x] `S02` - Keep the diagnostic log's descriptors between records with delete sharing and rotation following; `src/cadrumo/core/log_file_handler.py, src/cadrumo/core/locks.py and tests`.
- [x] `S03` - Read the installed product version once per process for every handshake; `src/cadrumo_client/transport/product_version.py and handshake call sites`.
- [ ] `S04` - Reuse verified worker authorization connections with a per-exchange incarnation recheck and a check-only exchange; `src/cadrumo_runtime/adapters/worker_authorization*.py, src/cadrumo_runtime/host/operation_progress_reporter.py, src/cadrumo_runtime/host/operation_authority.py and owning tests`.
- [ ] `S05` - Cut per-save custody path verification opens while keeping containment and link refusal; `src/cadrumo/adapters/persistence/storage/custody/filesystem_primitives.py, filesystem.py and owning tests`.
- [ ] `S06` - Stop creating the operation journal root on every journal call; `src/cadrumo/adapters/persistence/operations/journal.py, src/cadrumo/application/journal_repository.py and owning tests`.
- [ ] `S07` - Re-measure the TUI save path on the external harness and record before and after results; `.vault/audit`.

## Parallelization

S04, S05 and S06 touch disjoint files and run in parallel, one agent each. S07 runs after them. S01-S03 are committed (`711ad40ab9`, `d24a683937`, `3898dd6949`). Each agent commits only its own explicit paths. The orchestrator closes Steps and keeps the ledger. Other sessions edit this worktree concurrently, so files with foreign uncommitted changes are not edited without coordination.

## Verification

- Each Step's owning tests pass, including a test that fails against the previous code for each behaviour change, and an oracle or equivalence test where a decision path is rewritten.
- S04 covers the ADR's listed cases: reuse after a clean exchange; closure after timeout, frame error, cancellation or a partly read secret; refusal on incarnation mismatch; containment on loss with an outstanding permit and none when idle; revocation between two exchanges; stop closing idle connections; a check-only refusal granting no fence.
- Ruff, format, `just check-types`, import contracts and `dev/quality/tests/test_no_git_cli.py` pass on touched files.
- S07: on the harness, per-save worker handshakes fall from 72 to at most the pool size, custody opens and journal root creations fall, and save wall and per-process CPU medians improve against the recorded baseline on a quiet host.
