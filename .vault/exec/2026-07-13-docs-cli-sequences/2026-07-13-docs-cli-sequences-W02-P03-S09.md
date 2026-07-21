---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S09'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Implement the per-sequence sandbox runner (fresh isolated_profile_storage_root, frozen_clock, injected profile_id, English output, live tests off, invoke_cached_cli per frame)

## Scope

- `dev/docs/sequences/_runner.py`

## Description

- Implement `sequence_sandbox` in `dev/docs/sequences/_runner.py`: a fresh real-crypto storage root per sequence via `isolated_profile_storage_root`, the project-wide frozen instant `SANDBOX_INSTANT` under `frozen_clock`, English output pinned through the central settings override, and the process working directory moved to a sandbox-owned scratch workdir seeded with a copy of the committed synthetic fixtures so relative inputs and outputs never touch the repository.
- Provision the deterministic injected profile identity `SANDBOX_PROFILE_ID` through the canonical atomic create — `register_active_profile` inside `profile_create_storage_span` driven by `workflow_state_repository` — with a synthetic fact set covering the modelo readiness gate; no parallel write path.
- Refuse live-AEAT frames fail-closed before any execution: any non-option argv token equal to `live` or `pull`, or starting with `pull-`, marks the frame unenrollable per ADR ruling D6 and the pull/file naming standard; additionally refuse to open a sandbox while the live-test opt-in is set.
- Enforce per-frame exit codes at run time: default expectation 0, a declared `@expect exit_code == <n>` accepted, any other exit fails fast with the resolved argv and an output tail.
- Invoke each frame in-process through the cached Click tree with a bounded retry keyed strictly on the shared-worktree transient registry-race markers.
- Define the strict-frozen transcript contract for the golden store: `SequenceTranscript` carrying per-frame `FrameExecution` rows (kind, authored command line, argv as executed, exit code, verbatim output, pre-mask parsed envelope, captured values) plus the sandbox storage root and workdir for text-frame normalisation.
- Pin the storage-root environment seam before any application import by reusing the docs-build `ensure_isolated_storage_root`, and defer the application facade imports to call time so importing the engine never resolves product settings.

## Outcome

Every sequence executes in full isolation on the existing test substrates — real KEK/DEK encrypted SQLite, no shared state across or within pages — and returns a typed transcript ready for the comparison and golden layers. A live-AEAT frame cannot execute, and a machine carrying retired product state cannot red a run.

## Notes

Layering decision: the runner imports `cadrumo.tests.cli_runner` and `cadrumo.tests.secure_sql` directly — both are public non-underscore modules of the shipped package and the ADR names them as the substrate; duplicating them in docs tooling would create a parallel hermetic-provisioning path. An initial module-level import of the application workflow facade crashed on machines carrying a retired `aeat.db` (settings resolve at import time inside the registry parity module); fixed by the deferred-import plus `ensure_isolated_storage_root` pattern above.
