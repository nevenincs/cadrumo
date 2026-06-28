---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-final-security-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave11-audit]]"
---

# `secure-persistence-foundation` research: wave-12 Argon2id KDF migration

Research foundation for the wave-12 ADR. Examines whether to migrate the file-fallback master-key wrapping from **scrypt** to **Argon2id**, and how to do it as a hard cutover with no legacy decrypt path retained beyond the one-shot migration.

## Background

### Current key-derivation surface

The substrate has two key-derivation steps in two distinct contexts:

**(1) Per-purpose KEK derivation from a high-entropy 32-byte master key.** Implemented as `derive_key` in `_crypto.py` using HKDF-SHA256 with a per-purpose `info` parameter. This is **not in scope** for this wave. HKDF is the textbook-correct primitive when the IKM is already a uniformly-random key; replacing HKDF with Argon2id here would be a downgrade (wasteful CPU on already-random material, no security improvement).

**(2) Operator-passphrase-to-KEK derivation in the file-fallback master-key provider.** Implemented as `Scrypt(...)` in `_master_key.py` with parameters `N=2^17, r=8, p=1` and a 16-byte per-store salt. The derived KEK then AES-256-GCM-wraps the random 32-byte master key persisted in `master.key`. **This is the surface in scope.**

The keyring-backed master-key provider (`KeyringMasterKeyProvider`) stores 32 random bytes directly in the OS keychain (Windows Credential Manager, macOS Keychain, Linux libsecret). No KDF is involved on that path; the OS keychain is the trust boundary. **Out of scope.**

### Why Argon2id over scrypt is being asked

Catalogued reasons that surfaced across prior audits:

- **OWASP Password Storage Cheat Sheet (current edition)** explicitly lists Argon2id as the *first* recommendation, with scrypt and bcrypt as acceptable alternates. The substrate's current scrypt parameters (N=2^17, r=8, p=1) are explicitly OWASP-aligned, so we are at the strong end of the "acceptable" tier.
- **Password Hashing Competition (2015)** named Argon2 winner; Argon2id (the hybrid mode resistant to both side-channel and trade-off attacks) is the deployed variant.
- **Side-channel resistance.** Argon2id is data-dependent in its second pass and data-independent in its first, providing better cache-timing-attack resistance than scrypt's data-dependent layout. For a desktop CLI this is a low-magnitude concern (no hostile multi-tenancy), but it's strictly better.
- **Memory-hardness tunability.** Argon2id parameters expose memory cost in MiB directly (`memory_cost`), parallelism (`parallelism`), and time cost (`time_cost`), which is more legible to operators than scrypt's `N/r/p` triplet.
- **The internal final security audit + upstream reconciliation audit both flagged Argon2id as a deferred upgrade**, contingent on operator approval of the new dependency. The user has now directed "no deferring".

### The dependency footprint

`argon2-cffi` is the Python reference binding:

- Pure Python wheel + small C reference impl (`argon2_cffi_bindings`).
- Wheel size ~50–100 KiB on Linux/macOS/Windows; well-known CI footprint.
- Maintained by Hynek Schlawack (also maintains `attrs`, `structlog`, `service-identity`); active release cadence.
- License: MIT (`argon2-cffi`) + CC0 (`argon2`).
- No transitive heavyweight deps.

Trade-off: adds one wheel to the install matrix and one more line to `pyproject.toml`. Acceptable; the substrate already pulls in `cryptography` (which is significantly larger) and `pydantic` (also larger).

## Investigation findings

### F1 — Migration shape: dual-read-once, single-write-always

Two viable shapes:

1. **Hard cutover with one-shot migration tool.** Operator runs `aeat security migrate-master-key-kdf` once. The tool reads the current scrypt-wrapped `master.key`, decrypts the master key, re-wraps it under an Argon2id-derived KEK, and atomically replaces `master.key` + `master.kdf`. The `_KdfParameters.algorithm` field flips from `"scrypt"` to `"argon2id"`. Future loads only accept `algorithm == "argon2id"`; the scrypt branch is **deleted**. Operators who fail to run the migration tool see a clear error pointing them to the runbook.

2. **Dual-support indefinitely.** Both branches live forever, decoded by `algorithm` field. New writes always use Argon2id; reads accept either.

Per the user's standing directive ("complete removal of legacy code, lean and clean, no backwards looking codebase, no shadowing/stubbing/faking") shape (1) is mandatory. Shape (2) violates the no-legacy charter.

The migration tool itself follows the wave-10 `rotate_master_key` template: deferred imports, atomic per-file rewrite via `tempfile + os.replace`, summary table, exit-1 on any error. Resume-idempotency is naturally provided because re-running on an already-migrated file detects `algorithm == "argon2id"` and skips.

### F2 — Argon2id parameter selection

OWASP recommends, for password-hashing in interactive contexts:

- `m = 19 MiB` (memory cost), `t = 2` (time cost), `p = 1` (parallelism), or
- `m = 12 MiB`, `t = 3`, `p = 1`, or
- `m = 7 MiB`, `t = 5`, `p = 1`.

These are calibrated against ~1 second on commodity hardware. The substrate's KDF runs once on CLI startup and once again on master-key migration; latency is acceptable.

For the file-fallback provider — which is the *secondary* backend (keyring-first) — the calibration target should be ~500 ms on operator hardware. We propose: `memory_cost=19 * 1024` (19 MiB in KiB), `time_cost=2`, `parallelism=1`. These are the OWASP-current top-tier recommendation and align with `argon2-cffi`'s defaults.

`hash_len` stays at 32 bytes (AES-256 KEK).

Salt remains the same per-store 16 random bytes, persisted in the existing `salt` file. **Critical**: the salt is reused across the migration — on a single store, the operator's passphrase + same salt + Argon2id parameters must produce a KEK that wraps the master key. If we mint a new salt during migration, a passphrase typo on migration day silently locks the operator out. By reusing the existing salt we keep the failure mode "wrong passphrase = clean error".

### F3 — On-disk record evolution

Current `_KdfParameters` shape:

```
version: 1
algorithm: "scrypt"
n: 131072
r: 8
p: 1
salt_b64: <base64>
```

Proposed v2 shape:

```
version: 2
algorithm: "argon2id"
memory_cost: 19456    # KiB (19 MiB)
time_cost: 2
parallelism: 1
salt_b64: <base64>
```

The pydantic model gains `memory_cost`, `time_cost`, `parallelism` fields and **drops** `n`, `r`, `p`. Strict-frozen + `extra="forbid"` means a v1 file fails to parse as v2 (correct), and vice versa.

Loader logic:

```python
def _load_kdf_params(...) -> _KdfParameters:
    raw = json.loads(...)
    if raw.get("version") != _KDF_PARAMS_VERSION:  # 2
        raise SecretStoreError(
            "Master-key KDF format is v{found}, expected v{current}. "
            "Run `aeat security migrate-master-key-kdf` to upgrade."
        )
    return _KdfParameters.model_validate(raw)
```

This is the hard-cutover gate. Once shipped, scrypt-wrapped master keys cannot be loaded by the substrate at all without first running the migration. **No silent fallback.**

### F4 — Test coverage requirements

Mirror the wave-7 + wave-10 test discipline:

- **Substrate level** (in `_test_master_key.py`): KEK derivation correctness, parameter round-trip through `_KdfParameters`, version-rejection of v1 files, decrypt failure on wrong passphrase, decrypt failure on tampered salt.
- **CLI level** (in `cli/test_security.py`): end-to-end migrate-master-key-kdf round-trip — seed a v1 store, run the CLI, verify v2 store loads, verify the same passphrase still unwraps the master key, verify v1-after-migration is rejected.
- **Integration**: a full seed-FINANCIAL-envelope → migrate-KDF → decrypt-FINANCIAL-envelope to prove the rotation does not break consuming code.

### F5 — Documentation surface

The data-storage ADR (`.vault/adr/2026-04-12-data-storage-adr.md`) and the wave-1 ADR both reference scrypt-by-name in operator docs. After migration, those references need to be reconciled — but ADRs are immutable historical records, so the right move is: leave the prior ADRs as-is; document the migration in the wave-12 ADR (which becomes the new authoritative surface); update only the *operator runbook* sections of the README / docs / `aeat security --help` text.

### F6 — Failure-mode catalogue

For the migration tool:

- **Wrong passphrase.** Old scrypt KEK derives, AES-256-GCM tag check fails. Tool reports "could not unwrap existing master key — passphrase mismatch?" and exits 1. No artefacts changed.
- **Disk full mid-migration.** Atomic `os.replace(tempfile, target)` either succeeds or leaves the original file untouched. Resume by re-running.
- **Operator runs migration twice.** Second run reads `algorithm == "argon2id"`, decides "already migrated", exits 0 with a "no action needed" message.
- **Operator forgets to migrate, then runs any aeat command.** Loader sees `version != 2` and emits the runbook pointer. No data loss; clear remediation path.

### F7 — Test backends not affected

`EphemeralMasterKeyProvider` is in-memory only and never touches disk. Wave-12 changes nothing in tests that use the ephemeral provider — i.e., the vast majority of the suite. The new tests are scoped to `_test_master_key.py` (file backend) + `cli/test_security.py` (CLI command).

## Open questions

**Q1.** Should the v2 record include a `version_history` audit field listing prior algorithms and migration dates? Decision: no. ADRs are the audit trail; the on-disk record is a load-time configuration document and adding mutable history widens its threat surface.

**Q2.** Should the migration tool also mint a *new* random master key (rotating both KDF and key in one step)? Decision: no — that conflates two operations. Wave-10 already provides `aeat security rotate-master-key` for key rotation; wave-12 provides `aeat security migrate-master-key-kdf` for algorithm rotation. Operators who want both run them sequentially.

**Q3.** Should we expose `memory_cost` / `time_cost` as operator-tunable settings? Decision: no, **for now**. OWASP-current parameters are baked in. Adding tunables widens the misconfiguration risk (an operator setting `memory_cost=1024` halves security with no clear feedback). If a future hardware shift mandates re-tuning, we add a v3 record at that time.

## Recommendation

Author the wave-12 ADR with the **hard cutover** shape (F1 option 1), Argon2id parameters from F2, on-disk record evolution from F3, test coverage from F4, runbook update strategy from F5, and the failure-mode catalogue from F6. Land in this PR per the no-deferring directive.

The `argon2-cffi` dep addition is the only externally-visible change. CI install matrix already covers Linux/macOS/Windows wheels for `cryptography`; `argon2-cffi` ships the same wheel surface.
