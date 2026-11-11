---
tags:
  - '#plan'
  - '#profile-password-custody'
date: '2026-11-11'
tier: L1
related:
  - '[[2026-08-13-profile-password-custody-rollup-adr]]'
  - '[[2026-10-28-debug-startup-reliability-adr]]'
modified: '2026-11-11'
body_schema: body-v2
body_hash: 'sha256:709a9d191fdd7dc16c25be6d1d58a33004f54ae401f74f30826b09cda6ef5a3d'
---

# `profile-password-custody` plan

Strengthen a fallback password envelope at a later password sign-in, on top of the password-replacement journal.

## Description

Approved 2026-11-11. Basis: the operator approved automatic KDF strengthening at sign-in on 2026-11-10, relayed by CADRUMO-COORDINATOR, who on 2026-11-11 approved the order "password-replacement journal first, then sign-in strengthening on top" and required crash injection at every step boundary with recovery to exactly one consistent state, old or new.

A profile whose password envelope sits at the fixed fallback KDF point is strengthened without asking the person: after a password sign-in on such a profile the worker measures a stronger point in the background, and at a later password sign-in it rewraps the same data key under that point with the password the attempt already holds. The rewrap uses the password-replacement journal that landed first (T43), so a crash at any boundary resolves to the old or the new envelope and never to neither.

Decision coverage: `2026-08-13-profile-password-custody-rollup-adr`, amendment 2026-11-11, governs S01 to S05 and fixes its five binding constraints (journal first; secret-free, yielding background calibration held per host and boot; rewrap inside the sign-in attempt with nothing retained; only with no other live session and no automation enrollment; the attempt follows its own replacement onto the successor worker without rollback). The scoped exception in `2026-10-28-debug-startup-reliability-adr` governs S04 only.

## Steps

- [ ] `S01` - Calibration yields to waiting sign-ins: pid-checked lease waiter markers, and a background calibration mode that abandons (never falls back into a mint) when a waiter appears; `src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py`.
- [ ] `S02` - Mint a password replacement at a supplied measured point: enforce grid, eligibility floor and strictly-stronger-than-committed at the mint; same DEK, epoch and journaled replacement path; `src/cadrumo/adapters/persistence/storage/profile_custody.py`.
- [ ] `S03` - Worker: after a fallback profile's password sign-in, calibrate in the background and hold a strictly stronger point in worker memory; at a later password sign-in with no other live session and no automation enrollment, rewrap with the same password and report custody replaced; `src/cadrumo_runtime/host/profile_login.py`.
- [ ] `S04` - Runtime: carry the custody-replaced outcome from the worker, retire the replaced binding, follow the same attempt onto the successor host, prove again and admit; exempt only that attempt from generation-replacement cancellation; `src/cadrumo_runtime/host/profile_connection_login.py`.
- [ ] `S05` - Tests: background calibration yields; mint refuses weaker or equal points; end-to-end sign-in strengthens a fallback profile once and admits on the new generation; skipped with another live session or automation; crash at each boundary settles through the T43 journal; `src/cadrumo_runtime/host/tests`.

## Parallelization

Sequential, one executor. S02 builds on S01's calibration mode, S03 on S02's mint, S04 on S03's outcome, and S05 proves the whole chain.

## Verification

- A fallback profile signed in twice by password ends on a strictly stronger committed point with the same data key and epoch, and the second sign-in is admitted on the successor generation.
- The mint refuses a point below the eligibility floor, off the grid, or not strictly stronger than the committed one.
- With another live session or an automation enrollment the sign-in admits unchanged and writes nothing.
- Crash injection at every boundary of the rewrap (after intent staging, after the re-head, after durability, after the swap, before the clear) recovers to exactly one consistent envelope, old or new, and the password still opens it.
- A waiting unlock is never delayed past one calibration sample by the background measurement.
- Ruff, format, ty, radon (no C or worse), the import gate, the custody and runtime host suites and dev/quality plus dev/sanitizer pass against the tui base.
