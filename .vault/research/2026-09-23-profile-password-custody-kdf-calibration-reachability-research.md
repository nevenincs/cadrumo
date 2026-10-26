---
tags:
  - '#research'
  - '#profile-password-custody'
date: '2026-09-23'
modified: '2026-09-23'
body_schema: 'body-v2'
body_hash: 'sha256:3163fdb0f1aed503e6be3dc0b7fb4079d9e8e915f25cf8d7132f2214179471da'
related:
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `profile-password-custody` research: `KDF calibration reachability`

Can enrollment calibration, as the accepted custody decision specifies it, ever select a measured grid point? It matters because the calibration is the only mechanism that gives a profile stronger Argon2id parameters than the fixed `64 MiB, t=3, p=1` fallback, and because it is the largest single cost of creating a profile. On this host the measured branch is unreachable: every profile creation spends the full 15-second budget and then adopts the fallback, although a much stronger point derives inside the target band.

## Findings

### Every creation pays the whole budget and ends at the fallback

A fresh-process `config profile create` profiled on 2026-09-23 (dev environment, 24-core Windows host under 87% external load) took 22.1 s, of which `calibrate_profile_kdf` took 15.2 s: 11 supervised samples, 12 worker spawns, `_select_profile_kdf_calibration` called once and `_fallback_profile_kdf_calibration` called once. Two grid points were visited before the total deadline elapsed. Figures are relative; an absolute re-measurement on a quiet host is still owed.

### The timed quantity is not the derivation

`_measure_profile_kdf` (`src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py:524`) times the whole supervised sample: OS lease, worker spawn, ready handshake, the `calibrate` request (`_kdf_worker_supervision.py:79`) and the clean-exit wait. The worker's `_derive_calibration` (`_kdf_worker.py:153`) returns no timing. The worker's ready wait alone measured 1.0 to 1.9 s per spawn unprofiled under load, and 0.3 s per spawn in the profiled creation; an isolated import of the worker's closure costs 0.7 to 0.9 s. A sample therefore cannot fall below roughly 0.3 to 0.9 s whatever the Argon2 cost, while the band is 0.25 to 0.5 s (`kdf_supervision.py:67`).

### Strongest-first scanning cannot reach the band within the deadline

The grid has 90 points ordered by memory, then iterations, then parallelism, strongest first (`kdf_supervision.py:139`), and each point costs one warm-up plus five samples, six spawns (`kdf_supervision.py:265`). Argon2id medians measured in-process on this host (three runs each, loaded):

| memory MiB, t, p | median |
|---|---|
| 256, 10, 4 | 1.057 s |
| 256, 10, 1 | 3.303 s |
| 256, 4, 4 | 0.447 s |
| 256, 2, 4 | 0.235 s |
| 128, 6, 4 | 0.452 s |
| 128, 3, 4 | 0.150 s |
| 128, 3, 1 | 0.401 s |
| 64, 3, 4 | 0.292 s |
| 64, 3, 1 (fallback) | 0.242 s |
| 19, 2, 1 | 0.041 s |

The strongest in-band point is near `256, 4, 4`, the tenth point in scan order. Even with derivation-only timing and a single probe per point, the nine over-band points before it cost about 16.7 s of probes and spawns, which exceeds the 15-second total deadline.

### Which monotonicity is sound

At fixed lanes, Argon2id performs `iterations` passes over `memory` KiB blocks, so derivation time is strictly increasing in iterations at fixed memory and parallelism, and in memory at fixed iterations and parallelism. Parallelism is not monotone: at 64 MiB and t=3, p=4 measured slower than p=1 (0.292 s against 0.242 s), because lane threads cost more than they save at small memory. Consequently:

- dominance pruning at fixed parallelism skips nothing in strongest-first order, because every dominating point sorts earlier;
- pruning across parallelism, or by a proportional cost model, can skip a stronger in-band point and is not sound;
- a search over iterations within each (memory, parallelism) column, visiting memory from high to low, is sound and returns the same point the strongest-first ordering prefers, because that ordering only ranks in-band points.

### Existing profiles are not affected by a calibration change

Each profile persists its own KDF record inside its envelope (`records.py` `ProfileCustodyKdfParameters`, validated on unlock), so a calibration change alters only what a new enrollment selects.

### Not investigated

POSIX hosts and hosts with fewer than four cores were not measured. The lower band bound was not reassessed: a host fast enough to finish `256, 10, 4` below 250 ms would still fall back.

## Sources

- `src/cadrumo/adapters/persistence/storage/custody/kdf_supervision.py:67`, `:139`, `:160`, `:265`, `:298`, `:524`, `:591`
- `src/cadrumo/adapters/persistence/storage/custody/_kdf_worker.py:153`, `:201`
- `src/cadrumo/adapters/persistence/storage/custody/_kdf_worker_supervision.py:67`, `:79`
- RFC 9106 (Argon2), section 3: the memory-filling passes whose count is the iterations parameter.
- Measurements: fresh-process cProfile of `config profile create`, and in-process `argon2.low_level.hash_secret_raw` timings, both taken 2026-09-23 on the development host.
