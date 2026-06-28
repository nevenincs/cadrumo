---
tags:
  - '#audit'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave12-research]]"
  - "[[2026-04-30-secure-persistence-foundation-wave12-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-wave11-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-final-security-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-final-security-resolution-audit]]"
---

# `secure-persistence-foundation` audit: wave-12 Argon2id KDF migration

## Scope

Audit gate for **wave-12**: hard-cutover migration of the file-fallback master-key provider's password-to-KEK derivation from scrypt (N=2^17, r=8, p=1) to Argon2id (memory_cost=19 MiB, time_cost=2, parallelism=1).

Wave-12 in scope:

- Substrate changes in `src/aeat/adapters/persistence/storage/_master_key.py`: v2 `_KdfParameters`, `_LegacyKdfParameters`, `_derive_kek` swap, version-gating loader, atomic `migrate_master_key_kdf` helper, `MigrationResult` record.
- New error class `MasterKeyKdfVersionError(MasterKeyUnavailableError)` + trilingual registry registration `AUTH_STORAGE_MASTER_KEY_KDF_VERSION`.
- CLI command `aeat security migrate-master-key-kdf [--store-dir]`.
- 10 new tests (6 substrate + 4 CLI). Pre-existing `test_kdf_params_are_human_readable` updated to assert v2 shape.
- New runtime dependency: `argon2-cffi>=23.1.0`.

Out of scope (deferred or unaffected):

- HKDF-SHA256 per-purpose KEK derivation in `_crypto.derive_key`. HKDF is the textbook-correct primitive when the IKM is a uniformly-random key.
- OS keychain backend. No KDF involved on that path.
- SQLCipher whole-database encryption (separate ADR pending).
- IDENTITY-class typed records widening of `SecretStore`.
- `_validate_*_id` consolidation refactor.

## Findings

### Strengths

**Hard cutover with no dual-support fence.** Per the wave-9 + user "no legacy code" directive, scrypt is reachable only inside `_derive_legacy_scrypt_kek`, which is called only from `migrate_master_key_kdf`. The substrate's regular load path never instantiates `_LegacyScrypt` — verified by reading `_master_key.py` and `grep`-ing for `Scrypt(` in the load-time call graph. After migration the scrypt branch is unreachable from the main flow.

**Typed runbook-pointing version-gate error.** `_unwrap_existing` does a `json.loads` preview on the raw `master.kdf` text *before* strict-pydantic parsing. Any `version != _KDF_PARAMS_VERSION` produces `MasterKeyKdfVersionError` whose message includes the literal string `aeat security migrate-master-key-kdf`. Operators see the runbook command in the error message itself rather than burying it in registry-suggestion lookups.

**Trilingual error-registry coverage.** New `AUTH_STORAGE_MASTER_KEY_KDF_VERSION` ErrorCode with es/en/hu messages plus `default_suggestion="aeat security migrate-master-key-kdf"`. The registry-enforcement test (`test_registry_enforcement.py`) passes — every `AeatError` subclass in the codebase has a registered code.

**Atomic-write discipline reuses the substrate's secure pattern.** The migration helper calls `FileFallbackMasterKeyProvider._write_bytes_secure` for both `master.kdf` and `master.key`, which on POSIX uses `os.open(O_WRONLY|O_CREAT|O_TRUNC, 0o600)` so files land restricted from creation rather than via post-hoc chmod (no TOCTOU window).

**Salt continuity across migration.** The per-store salt is read once and reused for both the legacy KEK derivation and the Argon2id derivation. A wrong-passphrase migration produces a clean AES-GCM tag mismatch and the v1 store is byte-identical to before the call. Verified by `test_migrate_wrong_passphrase_keeps_v1_intact`.

**Resume-idempotency.** `migrate_master_key_kdf` checks `version == _KDF_PARAMS_VERSION` at the top and returns `MigrationResult(skipped=1)` without rewriting any artefact. CLI surface reports "already v2; no action required" and exits 0. Verified by `test_migrate_idempotent_on_v2_store` (substrate) and `test_migrate_idempotent_on_v2_store` (CLI).

**OWASP-current Argon2id parameters.** `memory_cost=19 MiB, time_cost=2, parallelism=1` matches the OWASP Password Storage Cheat Sheet's first-tier recommendation. `argon2-cffi`'s default-parameter exposure is consistent with these values.

**Pydantic v2 strict-frozen records.** Both `_KdfParameters` (v2) and `_LegacyKdfParameters` (v1) use `ConfigDict(strict=True, frozen=True, extra="forbid")` and constrain `algorithm` to `Literal["argon2id"]` / `Literal["scrypt"]` respectively. A v1 file fed to v2 validation fails fast.

**No regression in the storage substrate.** Full storage suite passes 293/293 (5 skipped, all pre-existing live-marker skips). Combined storage + cli/security + errors registry: 334/334 pass.

**CLI parity with wave-10.** `aeat security migrate-master-key-kdf` follows the exact ergonomics of `rotate-master-key`: deferred imports (no Alembic plugin-discovery cost on unrelated subcommands), `_default_passphrase_callback` reuse (env var first, then interactive prompt), Rich-printed summary table, exit-1 on any error.

**Operator-impact zero on keychain installs.** The OS keychain backend stores 32 random bytes directly with no KDF involved. Keychain-backed installs are unaffected by wave-12 — only file-fallback installs need the migration.

### Residual risks (low-severity, accepted)

**R1 — Atomic-write hazard window between two file rewrites.** `migrate_master_key_kdf` writes `master.kdf` first, then `master.key`. If the process is killed between those writes, the on-disk state declares v2 but the wrapped key is still under the legacy KEK. Subsequent loads would: (a) parse v2 params, (b) derive Argon2id KEK, (c) AES-GCM-decrypt — failing with `MasterKeyUnavailableError` (legacy ciphertext under wrong KEK). Operator remediation: restore `master.kdf` from backup and re-run migration. Acceptable: the substrate already requires `master.key` + `master.kdf` + `salt` to coexist, and the failure mode is loud (clean error) rather than silent corruption. A whole-pair temp-dir + atomic rename would close this window but adds Windows-aware semantics; track as a future hardening if the operator-impact catalogue surfaces it.

**R2 — Legacy code retained for migration only.** `_LegacyKdfParameters` and `_derive_legacy_scrypt_kek` exist in the codebase post-migration. They are unreachable from the substrate's load path but are reachable from `migrate_master_key_kdf`. Once every operator has migrated (signal: zero v1 stores in the wild), a future wave can delete this code entirely. Acceptable for the current cutover: removing the migrator before operators have run it would brick installations.

**R3 — Argon2id parameters are baked-in constants.** `_ARGON2_MEMORY_COST_KIB=19*1024`, `_ARGON2_TIME_COST=2`, `_ARGON2_PARALLELISM=1` are module-level `Final`. Re-tuning for hardware shifts requires a code change + version bump. Acceptable: per ADR Q3, exposing these as operator-tunable settings widens the misconfiguration surface (an operator setting `memory_cost=1024` halves security with no clear feedback). A future v3 record can address this if the calibration target changes.

**R4 — `argon2-cffi` adds a CFFI dependency.** Wheel ships pre-built for Linux/macOS/Windows. Maintained by Hynek Schlawack (overlap with `attrs` / `structlog` / `service-identity`). Acceptable supply-chain footprint; the substrate already pulls `cryptography` (significantly larger) and `pydantic`. CI install matrix already covers all three platforms.

**R5 — Migration tool requires interactive passphrase or env-var.** No way to run unattended on a secrets-via-stdin pipeline beyond setting `AEAT_SECRET_PASSPHRASE`. Acceptable: unattended secret-store passphrase delivery is itself a runbook decision per installation, not a substrate concern.

### Findings against deferred-list items (none worsened)

- **SQLCipher whole-DB encryption (separate ADR)** — orthogonal to KDF migration. Wave-12 does not touch the SQLite DB.
- **IDENTITY-typed records in SecretStore widening** — `SecretStore` consumes the master key from the same provider; wave-12 changes only how the file backend wraps the key, not how the key is consumed.
- **`_validate_*_id` consolidation refactor** — pure code-quality, unaffected.
- **Connector + export governance hardening** — unaffected.

## Recommendations

**Pass the gate.** Wave-12 closes the last cryptographic-primitive finding from the final security audit, lands with hard cutover and explicit one-shot migrator, and has full test coverage of the threat model relevant to the substrate.

**Document the operator runbook in user docs.** The README + CLI `--help` text now reference the migration command; ensure the next docs sweep adds a "Migrating from v1 (scrypt) to v2 (Argon2id)" section for operators on file-fallback installs.

**Track the legacy-code-removal trigger.** When the project is confident every installation has migrated (e.g. after the first 1.0.0 release plus a deprecation grace period), open a wave-13 to delete `_LegacyKdfParameters`, `_derive_legacy_scrypt_kek`, the `_LEGACY_KDF_PARAMS_VERSION` constant, and `migrate_master_key_kdf` itself. The CLI command can stay as a defensive no-op or be removed in a follow-up version bump.

**Revisit R1 if the hazard window matters.** Currently the substrate's failure mode for "kill between master.kdf write and master.key write" is a clean error pointing at restore-from-backup. If telemetry from operator runbooks shows this hazard occurring in the wild, escalate by introducing a temp-dir + atomic-rename pattern.

**Do not regress on review latency.** External reviews (`@gemini` + `@codex`) requested on commit 6aa93e2 at PR #441 comments 4334294782 / 4334296211. Findings, when they arrive, are absorbed by amending the residual-risks section above rather than opening a wave-13 prematurely.

## Verdict

**Wave-12 audit gate: PASS.** Substrate + CLI + tests are coherent, hard-cutover, regression-free across the storage substrate, and address the last cryptographic-primitive finding from the final security audit. Residual risks R1–R5 are low-severity and explicitly accepted under the current attacker model.

The persistence substrate's cryptographic profile now matches OWASP-current best practice end-to-end: AES-256-GCM AEAD, HKDF-SHA256 per-purpose KEK derivation, Argon2id password-derived KEK, master-key rotation, KDF-version migration, and corpus integrity manifest.

Next per the standing no-deferring directive: review-feedback absorption from `@gemini` + `@codex`, then either land their findings or proceed to the next deferred-list item (SQLCipher ADR / `_validate_*_id` consolidation).
