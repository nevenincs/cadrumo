---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:cc68429935ebe9dd8c0d9cbc9eb68e4904ced256023b5c27405c41d80f908746'
step_id: 'S24'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Add byte-exact pointer capture, atomic restore, idempotent clear with restrictive temporary permissions and fsync, complete short writes in the hardened byte writer, prove complete writes against a real operating-system descriptor, delegate master-key secure writes to the canonical hardened writer, remove the duplicated sensitive-persistence exemption, and expose the core pointer API

## Scope

- `src/cadrumo/core/_bucket_pointer_io.py`
- `src/cadrumo/core/atomic_write.py`
- `src/cadrumo/core/__init__.py`
- `src/cadrumo/core/tests/test_atomic_write.py`
- `src/cadrumo/adapters/persistence/storage/master_key/_master_key_io.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_sensitive_persistence_policy.py`

## Description

- Ground the pointer and hardened-write boundary with fresh explicit-port code and ADR searches, then corroborate every implementation, caller, direct filesystem mutation, and complete-write analogue with exact symbol searches.
- Add exact-byte pointer capture, hardened atomic restore, and idempotent durable clear while preserving strict parsed reads and deterministic pointer serialization.
- Export the new pointer operations through the cycle-safe lazy core facade.
- Complete short descriptor writes with the established memoryview-and-offset loop and reject non-positive progress.
- Prove the write-all behavior through a capacity-limited real operating-system pipe with a bounded reader and byte-exact payload assertion.
- Remediate the independent review's permanent-backpressure reproduction by propagating `BlockingIOError`, bounding the writer itself in spawned child processes, and guaranteeing descriptor, thread, and process cleanup on every test path.
- Detect the master-key writer's duplicated hardened filesystem mechanics, re-ground the expanded scope with a fresh explicit-port code search, and preserve its semantic facade while delegating all bytes to the core authority.
- Remove the retired direct `os.open` and `os.write` policy exemptions and attribute the surviving core descriptor write to the complete-write helper.
- Run focused Ruff, the complete atomic, pointer, sensitive-persistence policy, and master-key roundtrip suites, a fresh facade-import probe, and the uncached five-contract import graph.
- Rerun semantic and exact duplication searches after implementation without changing later caller-routing scope.

## Outcome

PASS. Core now owns byte-exact active-profile pointer capture, restore, clear, and deterministic hardened writes.

- `capture_pointer` preserves arbitrary pointer bytes and distinguishes absence with `None`; `restore_pointer` atomically reinstalls bytes or delegates absence to `clear_pointer`.
- `clear_pointer` is repeatable and requests a parent-directory sync only after a successful unlink.
- `write_pointer` retains deterministic UTF-8 TOML serialization while sharing the hardened byte replacement authority.
- `atomic_write_secure_bytes` remains the stable master-key semantic facade but now delegates to the sole hardened core filesystem writer; its duplicated descriptor implementation and policy exemptions are gone.
- The lazy `cadrumo.core` facade resolves all three new operations without recreating the Settings bootstrap cycle.
- Focused Ruff passed all six owned Python paths.
- The remediated focused unit lane passed 59 tests across atomic writes, pointer IO, the pointer model, sensitive-persistence policy, and master-key roundtrips.
- Both real-pipe nodes passed ten consecutive runs. Cooperative attempts require one byte-exact 1 MiB completion while permitting correctly propagated transient backpressure; the separate full-pipe/no-reader child requires permanent backpressure to propagate within the five-second process bound.
- The fresh uncached import graph analyzed 3,418 files and 16,136 dependencies; all five contracts were kept and zero were broken.

## Notes

Post-implementation RAG and exact searches found the expected direct text capture, direct restore, and unlink owners in profile orchestration, the profile repository, and profile health. They remain intentionally unchanged for Steps S26-S28. The searches also found separate complete-write loops for lockfiles and secure materialisation, whose descriptor-level policies are distinct from target-level hardened atomic replacement. The only master-key secure-write declaration now delegates directly to the core hardened writer, and exact caller search found no remaining master-key `os.open`, `os.write`, replacement, sync, or cleanup dialect.

The docstring workflow used an independently RAG-grounded Researcher, an isolated RAG-grounded Author, and an Editor pass. It changed only the owned source docstrings and made no user-document claim that later caller routing is complete.

The independent `s24-write-all-blocking-spin` MEDIUM finding is remediated. The review's full nonblocking pipe with no reader can no longer enter the former catch-and-retry loop: the operating-system `BlockingIOError` propagates unchanged. The memoryview offset loop remains responsible only for positive short-write completion. Spawned-process regression coverage bounds the writer before any join, terminates and kills on timeout, closes both pipe descriptors in the child, and rejects a one-write mutation as an incomplete payload rather than mistaking it for success.

The broad feature Vault check's campaign-owned checks were clean. Its failed status came only from the same 29 pre-existing `feature-rename-integrity` diagnostics in unrelated historical execution folders recorded by the W01 prerequisite, plus one informational fresh-clone mtime skip. No unrelated Vault artifact was changed.
