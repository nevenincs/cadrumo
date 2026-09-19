---
tags:
  - '#research'
  - '#secure-storage-performance-hardening'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:e842bcaab8939820435e5c1b8c793c87cec228bf9ea131e076709a3b717d9bd3'
related:
  - "[[2026-08-13-secure-storage-hardening-successor-adr]]"
  - "[[2026-08-13-profile-password-custody-rollup-adr]]"
---

# `secure-storage-performance-hardening` research: `secure storage performance and robustness campaign`

The campaign must improve secure-storage latency without weakening fail-closed
custody, integrity, durability, or secret-handling guarantees. Empty
`aeat config profile list` discovery is sub-millisecond and performs no KDF,
decryption, or keyring work; the observed 5.2--8.5 second runtime is dominated
by eager imports and model construction. The wider audit found a separate
non-empty-path defect: listing constructs full custody aggregates, repeats
commit validation, reads password-envelope and sentinel metadata, takes locks,
and may repair label-head state. The evidence favors a new cross-cutting
campaign constrained by the existing custody and secure-storage ADRs. An ADR
must settle pure read projections, import boundaries, side-effect policy, and
measurable regression budgets.

## Findings

### The empty-store signal is import amplification, not cryptographic work

Five isolated samples took 5,224--7,754 ms; an independent run reached 8,541 ms
under heavier host contention. An already-imported repository empty scan took
0.16--0.58 ms. Inventory checks retired paths before returning when the capsule
root is absent; this intentional fail-closed path contains no envelope unwrap,
KDF, decrypt, or keyring call. `src/cadrumo/adapters/persistence/storage/custody/_capsule.py:721`

One `cProfile` run attributed 8.69 of 8.98 seconds to imports, including 1,237
Pydantic model constructions. The `application.workflow` facade loads broad
adapter and engine graphs before its lightweight profile scan; independent
timing placed that facade at 2.64--3.13 seconds. The config payload module also
imports unrelated surfaces. `src/cadrumo/application/workflow/__init__.py:94`
`src/cadrumo/entrypoints/cli/_config_payloads.py:22`

Keeping eager facades makes small commands pay for unrelated AEAT, certificate,
filing, registry, Google, and schema surfaces. A PEP 562 lazy facade matches the
existing user-profile facade and preserves the canonical public import boundary.
A private command-specific import violates that boundary and is not viable.

### Non-empty listing crosses custody and mutation boundaries it does not need

The payload needs UUID, authenticated label, and active selection, but listing
builds a full view per capsule. It re-recognizes commits, takes a transaction
lock, reads commit, password envelope, sentinel, label, creation journal, and
label head, and verifies label provenance. No Argon2 or decrypt runs, but roughly
four commit validations occur per profile. `src/cadrumo/application/user_profile/_profile_repository.py:88`
`src/cadrumo/application/user_profile/_profile_repository.py:144`
`src/cadrumo/application/user_profile/_profile_repository.py:176`

The label-head verifier can publish or recover state, so listing can mutate.
Output rendering can resolve the active profile again, duplicating work.
`src/cadrumo/adapters/persistence/storage/custody/_label_head_repository.py:54`
`src/cadrumo/entrypoints/cli/_common.py:703`

A pure `ProfileSummary` inventory can preserve UUID/commit/label provenance
while excluding envelope, sentinel, KDF, session, and repair work. The ADR must
settle a read-only label witness. Keeping full aggregates maximizes validation
but couples discovery availability to custody and repair machinery.

### Robustness requires budgets and negative gates, not one benchmark

Separate budgets are needed for subprocess startup, command resolution, empty
inventory, and per-profile growth. Tests should count file/commit reads, prove
no KDF/decrypt/keyring calls, and prove a list does not create unrelated paths.
One isolated invocation created 27 directories and an empty log file during
startup. `src/cadrumo/core/config.py:1427`

Binding gates include retired-layout refusal even without `buckets/`; canonical
UUID and no-follow bounded commit discovery; fail-closed malformed markers;
UUID-bound labels; and full custody checks on explicit inspection/repair.
`src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py:191`

Absolute thresholds remain unselected because the shared Windows host was
contended. Quiet-CI medians and structural gates need calibration. Populated
scaling, adverse filesystems, concurrent mutation, antivirus impact, and other
secure-object namespaces remain uninvestigated and belong in the campaign plan.

## Sources

- `src/cadrumo/adapters/persistence/storage/custody/_capsule.py:721`
- `src/cadrumo/adapters/persistence/storage/custody/_capsule_discovery.py:191`
- `src/cadrumo/adapters/persistence/storage/custody/_label_head_repository.py:54`
- `src/cadrumo/application/user_profile/_profile_repository.py:88`
- `src/cadrumo/application/user_profile/_profile_repository.py:144`
- `src/cadrumo/application/user_profile/_profile_repository.py:176`
- `src/cadrumo/application/workflow/__init__.py:94`
- `src/cadrumo/entrypoints/cli/_config_payloads.py:22`
- `src/cadrumo/entrypoints/cli/_common.py:703`
- `src/cadrumo/core/config.py:1427`
- `.vault/adr/2026-08-13-secure-storage-hardening-successor-adr.md:23`
- `.vault/adr/2026-08-13-profile-password-custody-rollup-adr.md:34`
- `.vault/adr/2026-08-13-profile-state-aggregate-successor-adr.md:34`
- `.vault/adr/2026-08-13-profile-bucket-lifecycle-successor-adr.md:40`
- `.vault/research/2026-06-14-storage-backend-security-review-research.md:88`
- `.vault/research/2026-06-14-storage-backend-security-review-research.md:157`
