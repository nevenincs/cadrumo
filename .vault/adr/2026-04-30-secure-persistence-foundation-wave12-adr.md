---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave12-research]]"
  - "[[2026-04-30-secure-persistence-foundation-final-security-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave11-audit]]"
---

# `secure-persistence-foundation` adr: wave-12 Argon2id KDF migration | (**status:** `accepted`)

## Problem Statement

The file-fallback master-key provider derives the operator-passphrase KEK using **scrypt** (`N=2^17, r=8, p=1`). The current and prior security audits both flagged this as a "modern recommendation deferred" — Argon2id is the OWASP-current first-tier password-hashing algorithm and the PHC-2015 winner. The user has now directed "no deferring": every flagged item lands in this PR.

The wave-12 problem is therefore: **migrate the password-derived-KEK algorithm from scrypt to Argon2id**, with hard cutover (no legacy decrypt path retained beyond the one-shot migration) and a CLI tool that operators can run once to convert their on-disk store.

Out of scope:

- The HKDF-SHA256 per-purpose KEK derivation in `_crypto.derive_key`. HKDF is the textbook-correct primitive when the IKM is a uniformly-random key (which the master key is); replacing it with Argon2id would be a downgrade.
- The keyring-backed master-key provider. The OS keychain stores 32 random bytes directly with no KDF involved.

## Considerations

Surveyed in the wave-12 research artefact:

- **Algorithm choice**. OWASP-current top-tier: Argon2id with `memory_cost=19 MiB, time_cost=2, parallelism=1`. Aligned with `argon2-cffi`'s defaults.
- **Migration shape**. Two viable shapes: (1) hard cutover with one-shot CLI migration tool, (2) indefinite dual-support. The user's standing "no legacy code" directive forces shape (1).
- **On-disk record evolution**. `_KdfParameters` v1 (`algorithm="scrypt", n, r, p`) → v2 (`algorithm="argon2id", memory_cost, time_cost, parallelism`). Pydantic strict-frozen + `extra="forbid"` makes the version transition typesafe.
- **Salt continuity**. The per-store 16-byte salt persists across the migration. Minting a new salt would mean a passphrase typo silently invalidates the operator's installation.
- **Test backends**. `EphemeralMasterKeyProvider` is unaffected; new tests scoped to `_test_master_key.py` (file backend) + `cli/test_security.py` (CLI command).
- **CI footprint**. `argon2-cffi` adds ~50–100 KiB wheel; ships for Linux/macOS/Windows. Maintained by the same author as `attrs` / `structlog`.

## Constraints

- **No silent fallback**. Per the wave-9 hard-cutover principle: once shipped, scrypt-wrapped `master.key` files cannot be loaded by the substrate. The loader version-gates and raises a clear runbook-pointing error.
- **Pydantic v2 strict-frozen**. All new records (the v2 `_KdfParameters` shape) follow the project mandate: `ConfigDict(strict=True, frozen=True, extra="forbid")`.
- **Trilingual error messages**. New `MasterKeyKdfVersionError` registered with es/en/hu messages and `default_suggestion="aeat security migrate-master-key-kdf"`.
- **CLI parity with wave-10**. The migration command follows the exact ergonomics of `aeat security rotate-master-key`: deferred imports, atomic per-file rewrite via `tempfile + os.replace`, summary table, exit-1 on error, resume-idempotent on already-migrated stores.
- **Atomic write discipline**. `master.key` and `master.kdf` are rewritten as a pair; the migration must update both atomically or neither. Implementation uses a fresh tempfile per artefact, fsync, then `os.replace` — same pattern as the rest of the substrate's at-rest writers.

## Implementation

Five phases. All land in this PR per the no-deferring directive.

### Phase 1 — Substrate: Argon2id wrapping primitive

In `_master_key.py`:

- Add `argon2-cffi` import (`from argon2.low_level import hash_secret_raw, Type`).
- Define `_ARGON2_MEMORY_COST_KIB`, `_ARGON2_TIME_COST`, `_ARGON2_PARALLELISM` module constants matching the F2 parameters.
- Bump `_KDF_PARAMS_VERSION` to `2`.
- Replace `_KdfParameters` fields: drop `n`, `r`, `p`; add `memory_cost: int`, `time_cost: int`, `parallelism: int`. Drop the default-`"scrypt"` algorithm and require `algorithm: Literal["argon2id"]`.
- Replace `_derive_kek` body: `hash_secret_raw(passphrase_bytes, salt, time_cost=..., memory_cost=..., parallelism=..., hash_len=KEY_SIZE, type=Type.ID)`.
- Loader version-gates: any `_KdfParameters` JSON with `version != 2` raises `MasterKeyKdfVersionError` pointing to the migration tool.

### Phase 2 — Substrate: migration helper

New helper in `_master_key.py`:

```python
def migrate_master_key_kdf(
    *,
    store_dir: Path,
    passphrase: bytes,
) -> _MigrationResult:
    """One-shot scrypt → Argon2id KDF migration."""
```

Reads `master.key` + `master.kdf`. If `master.kdf` is already v2, returns `_MigrationResult(skipped=True)` (resume-idempotency). Otherwise:

1. Read salt from on-disk `salt`.
2. Derive scrypt KEK from `passphrase + salt`.
3. AES-256-GCM-decrypt `master.key` → master_key bytes.
4. Derive Argon2id KEK from `passphrase + same salt`.
5. AES-256-GCM-encrypt master_key under new KEK → new ciphertext.
6. Write new ciphertext to `master.key.tmp`, fsync, `os.replace` → `master.key`.
7. Write v2 `_KdfParameters` JSON to `master.kdf.tmp`, fsync, `os.replace` → `master.kdf`.
8. Return `_MigrationResult(migrated=True)`.

The scrypt code path is **only invoked here** — it does not exist in the regular load path. Once migration completes, the scrypt branch is unreachable and gets removed when the helper itself is removed.

### Phase 3 — CLI: `aeat security migrate-master-key-kdf`

New command in `src/aeat/entrypoints/cli/security.py`:

```
aeat security migrate-master-key-kdf [--store-dir <path>]
```

If `--store-dir` is omitted, resolves from `Settings.aeat_secret_store_dir`. Prompts for the passphrase via the same `_resolve_passphrase` helper used by the file provider (or reads `AEAT_SECRET_PASSPHRASE` env var). Calls `migrate_master_key_kdf` and prints a Rich summary table:

| metric    | count |
|-----------|-------|
| migrated  | 0/1   |
| skipped   | 0/1   |
| errors    | 0     |

Exits 1 on error, 0 on success-or-skip. Resume-idempotent.

### Phase 4 — Errors: registry + class

- New `MasterKeyKdfVersionError(MasterKeyUnavailableError)` in `_errors.py`.
- Registry entry `INTEGRITY_STORAGE_MASTER_KEY_KDF_VERSION` with es/en/hu messages and `default_suggestion="aeat security migrate-master-key-kdf"`.

### Phase 5 — Tests

`_test_master_key.py` additions:

- `test_argon2id_round_trip_via_file_provider`: seed v2 store, prove `get_master_key()` returns the original bytes.
- `test_v1_store_rejected_with_runbook_pointer`: seed v1 (scrypt) store, attempt to load → `MasterKeyKdfVersionError` with suggestion.
- `test_wrong_passphrase_clean_error_v2`: seed v2 store, try to unwrap with wrong passphrase → `MasterKeyUnavailableError`, no plaintext leak.
- `test_migrate_v1_to_v2_round_trip`: seed v1 store, run `migrate_master_key_kdf`, verify v2 file structure, verify same passphrase still unwraps.
- `test_migrate_idempotent_on_v2_store`: seed v2 store, run migration → reports `skipped`.
- `test_migrate_wrong_passphrase_keeps_v1_intact`: wrong passphrase on a v1 store; v1 files untouched on disk.

`cli/test_security.py` additions (in a new `TestMigrateMasterKeyKdf` class):

- `test_migrate_then_load_round_trip`: end-to-end via CLI; seed v1, invoke command with `AEAT_SECRET_PASSPHRASE`, verify v2 file on disk and master-key load works.
- `test_already_v2_store_skips_cleanly`: invoke twice; second invocation reports `skipped`.
- `test_wrong_passphrase_exits_nonzero`.

### Phase 6 — Code-review request + audit gate

Per the standing "review requests are part of every wave" directive: immediately after the wave-12 commit lands, request fresh `@gemini` + `@codex` reviews on PR #441, then write the wave-12 audit-gate report.

## Rationale

**Why hard cutover (not dual-support).** The user's "complete removal of legacy code" directive forecloses dual-support. More substantively: a dual-support loader keeps the scrypt branch live forever, doubling the per-load surface area for review and creating a long-lived "downgrade-attack" window where a hostile process could rewrite `master.kdf` to claim `algorithm: "scrypt"` and force the loader through the weaker branch. Hard cutover with version-gating eliminates that surface.

**Why Argon2id over Argon2i / Argon2d.** Argon2id is the OWASP-recommended default; combines the side-channel resistance of Argon2i (data-independent first pass) with the GPU-attack resistance of Argon2d (data-dependent second pass). Argon2id is the only mode `argon2-cffi` exposes in its high-level API (`PasswordHasher` defaults to `Type.ID`).

**Why the OWASP `m=19MiB, t=2, p=1` parameter set.** Calibrated for ~1 second on commodity hardware; well-suited to a CLI's once-per-process cost. The substrate's file-fallback provider runs the KDF once at startup, so a 1s budget is invisible to the operator.

**Why reuse the existing salt.** A passphrase typo on migration day plus a new salt = silent installation lock-out. Reusing the salt means "wrong passphrase" produces a clean AES-GCM tag mismatch and the operator can re-run.

**Why a separate command instead of folding into `rotate-master-key`.** The two operations are conceptually distinct: rotation changes the master key bytes; migration changes the wrapping algorithm. Mixing them widens the failure-mode surface (was the rotation done, or just the migration?). Operators who want both run them sequentially.

**Why no plain-PBKDF2 option.** PBKDF2 is acceptable but strictly weaker than scrypt and Argon2id on memory-hardness; including it would add migration shape complexity for no security benefit.

## Consequences

**Operator impact (one-time).** Any installation with an existing file-fallback `master.key` must run `aeat security migrate-master-key-kdf` once. The `MasterKeyKdfVersionError` runbook pointer makes the action obvious. Operators on the keychain backend (`Settings.aeat_secret_store_backend in {"keyring", "auto"-with-keychain-available}`) are unaffected — they have no KDF to migrate.

**Dependency surface.** Adds `argon2-cffi` to `pyproject.toml`. Maintainer overlap with existing deps (Hynek Schlawack), MIT-licensed, ~50–100 KiB wheel per platform. Acceptable footprint.

**Performance.** ~500 ms – 1 s added to first master-key acquisition on the file-fallback path. Subsequent acquisitions in the same process hit the in-memory cache in `_master_key.py` and pay zero KDF cost. Net impact: imperceptible in interactive use, negligible in CLI scripts.

**Forward-compatibility.** Introducing the `version` field as a hard gate in the loader means future KDF migrations (`v2 → v3`) follow the same exact pattern: bump version, add migration helper, add CLI command, emit version-gate error from the loader. The pattern is now repeatable for any future cryptographic-primitive sunset (e.g., a hypothetical Argon2id → post-quantum-PBKDF transition).

**Audit trail.** The wave-12 ADR + audit gate document the algorithm transition; future security audits can grep for "scrypt" in `_master_key.py` and confirm zero hits, proving the legacy code was removed and not merely fenced off.

**Closes the last cryptographic-primitive finding** from the final security audit. After wave-12 lands, the substrate has: AES-256-GCM AEAD, HKDF-SHA256 per-purpose KEK derivation, Argon2id password-derived KEK, master-key rotation, KDF-version migration, and corpus integrity manifest. The cryptographic profile matches OWASP-current best practice end-to-end.
