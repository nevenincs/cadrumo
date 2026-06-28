---
tags:
  - '#plan'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave17-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-wave17-research]]"
---

# `secure-persistence-foundation` plan: wave-17 Kent UX security integration

Phased implementation plan for the wave-17 ADR. Eight phases, each landing as one or more atomic commits with full test coverage. Designed for sequential execution; later phases depend on earlier ones (e.g. provision needs the error subclasses from phase 2).

## Phase 1 — `aeat doctor` security rows

**Goal**: `aeat doctor` reports the security layer's health.

**Files**:
- `src/aeat/entrypoints/cli/doctor.py` — extend `collect_rows`.
- `src/aeat/entrypoints/cli/test_doctor.py` — add tests.
- `src/aeat/adapters/persistence/storage/__init__.py` — re-export any helpers required.

**New rows** (each follows the existing `Row(label, status, detail, hint)` pattern):

1. **Secret-store dir** — exists + writable + correct permissions on POSIX (0o700).
2. **Active backend** — `keyring` / `file` / `unsecured` / `auto-fallback-active`.
3. **Master-key readiness** — for file-fallback: master.key + master.kdf + salt all present and decryptable under the cached passphrase. For keyring: probe `_probe_backend()`. For unsecured: warn loudly.
4. **KDF version** — must be `_KDF_PARAMS_VERSION=2` (Argon2id, post-wave-12). v1 → red row pointing at `aeat security migrate-master-key-kdf`.
5. **Recovery-key backup** — `master.recovery.key` exists in `aeat_secret_store_dir`. Yellow if missing; "consider running `aeat security key-export`" hint.
6. **Unsecured-mode canary** — if active backend is `unsecured`, surface a RED row with the well-known-key fingerprint and a strong remediation hint.

**Tests**:
- `test_doctor_reports_secret_store_dir_exists`
- `test_doctor_reports_active_backend_keyring`
- `test_doctor_reports_active_backend_file_fallback`
- `test_doctor_reports_active_backend_unsecured` (with NIF-canary refusal)
- `test_doctor_warns_on_v1_kdf` (post-wave-12 canary)
- `test_doctor_warns_on_missing_recovery_key`

**Commit message**: `feat(cli): wave-17 phase 1 — aeat doctor security rows`.

## Phase 2 — Three-failure-class error subclasses

**Goal**: distinguish keychain-locked / passphrase-mismatch / material-missing in error type + message.

**Files**:
- `src/aeat/adapters/persistence/storage/errors.py` — three new subclasses.
- `src/aeat/core/errors/_registry.py` — three trilingual entries.
- `src/aeat/adapters/persistence/storage/_master_key.py` — narrow throw sites in both providers.
- `src/aeat/adapters/persistence/storage/_test_master_key.py` — assert subclass instances.

**New error classes**:

```python
class MasterKeyKeychainLockedError(MasterKeyUnavailableError):
    """Raised when the OS keychain is reachable but locked.

    Recoverable by unlocking the keychain (Touch ID / Hello / desktop unlock).
    Suggestion: 'unlock your OS keychain and retry'.
    """

class MasterKeyPassphraseMismatchError(MasterKeyUnavailableError):
    """Raised when the file-fallback passphrase does not unwrap master.key.

    Recoverable by re-entering the passphrase. Suggestion: 'verify your
    passphrase; if forgotten, run `aeat security recover --recovery-key`'.
    """

class MasterKeyMaterialMissingError(MasterKeyUnavailableError):
    """Raised when no master-key material exists at all.

    Neither the keyring entry nor the file-fallback artefacts are present.
    Suggestion: 'run `aeat security provision` to set up the security layer'.
    """
```

**Registry entries** (es / en / hu):

- `AUTH_STORAGE_MASTER_KEY_KEYCHAIN_LOCKED` — "El llavero del sistema está bloqueado." / "OS keychain is locked." / "Az operációs rendszer kulcstartója zárolva."
- `AUTH_STORAGE_MASTER_KEY_PASSPHRASE_MISMATCH` — "La frase de paso no coincide." / "Passphrase did not unlock the master key." / "A jelszó nem oldotta fel a mester kulcsot."
- `AUTH_STORAGE_MASTER_KEY_MATERIAL_MISSING` — "Falta material de clave maestra." / "No master-key material exists." / "Nincs mester kulcs anyag."

**Throw-site refinements**:
- `KeyringMasterKeyProvider._probe_backend()` — when `fail.Keyring` is detected, raise `MasterKeyKeychainLockedError` (not just `KeyringUnavailableError`).
- `FileFallbackMasterKeyProvider._unwrap_existing()` — distinguish "decrypt failed" (passphrase mismatch) from "file missing" (material missing) at the appropriate branch.

**Commit message**: `feat(storage): wave-17 phase 2 — three-failure-class master-key errors`.

## Phase 3 — `UnsecuredMasterKeyProvider` + opt-out plumbing

**Goal**: introduce the deterministic-key provider that powers the `--insecure-no-encryption` mode.

**Files**:
- `src/aeat/adapters/persistence/storage/_master_key.py` — new `UnsecuredMasterKeyProvider` class.
- `src/aeat/adapters/persistence/storage/__init__.py` — export.
- `src/aeat/adapters/persistence/storage/errors.py` — `UnsecuredModeRefusedError(SecretStoreError)`.
- `src/aeat/core/errors/_registry.py` — trilingual entry.
- `src/aeat/config.py` — add `aeat_allow_unencrypted` setting + `SecretStoreBackend.UNSECURED`.
- `src/aeat/adapters/persistence/storage/_master_key.py::get_master_key_provider` — wire `unsecured` backend.
- `src/aeat/application/setup/_env_writer.py` — NIF-canary refusal at profile-load time.

**`UnsecuredMasterKeyProvider`**:

```python
class UnsecuredMasterKeyProvider:
    """Master-key provider for testing / throwaway scenarios.

    Returns a deterministic 32-byte key derived from a published
    constant. The substrate's encryption pipeline is unchanged; only
    the wrapping key is publicly known. Provides ZERO confidentiality.

    Activation requires both:
    - AEAT_ALLOW_UNENCRYPTED=1 environment variable.
    - aeat_secret_store_backend=unsecured (or --insecure-no-encryption flag).

    Refused at profile-load time when the active profile carries a
    valid NIF/NIE/CIF (NIF-canary).
    """

    _PUBLISHED_KEY: ClassVar[bytes] = (
        b"AEAT_UNSECURED_DO_NOT_USE_FOR_PROD" + b"\x00" * 4
    )

    def get_master_key(self) -> bytes:
        return self._PUBLISHED_KEY
```

**Opt-out plumbing**:
- Settings: `aeat_allow_unencrypted: bool = False` + add `UNSECURED = "unsecured"` to `SecretStoreBackend`.
- `get_master_key_provider`: when `backend == UNSECURED`:
  - if not `settings.aeat_allow_unencrypted` (env-var driven via pydantic-settings): raise `UnsecuredModeRefusedError("AEAT_ALLOW_UNENCRYPTED=1 is required to use the unsecured backend")`.
  - else: return `UnsecuredMasterKeyProvider()`.

**NIF-canary refusal** in `_env_writer.write_profile_file()`:

```python
def _refuse_unsecured_with_real_nif(profile: AutonomoProfile, provider: MasterKeyProvider) -> None:
    if isinstance(provider, UnsecuredMasterKeyProvider):
        if validate_spanish_tax_id(profile.tax_id, allow_synthetic=True):
            # Real NIF — refuse the unsecured-mode write.
            raise UnsecuredModeRefusedError(
                f"unsecured mode is incompatible with a real NIF ({profile.tax_id!r}); "
                "either remove --insecure-no-encryption or use a synthetic NIF (e.g. '00000000T').",
            )
```

(The wave-2 NIF validator already distinguishes "valid NIF" from "synthetic / placeholder". Wave-17 adds the canary at the profile-write boundary.)

**Tests**:
- `test_unsecured_provider_returns_deterministic_key`
- `test_unsecured_backend_requires_AEAT_ALLOW_UNENCRYPTED`
- `test_unsecured_mode_refused_with_real_nif`
- `test_unsecured_mode_accepted_with_synthetic_nif`

**Commit message**: `feat(storage): wave-17 phase 3 — unsecured-mode opt-out + NIF-canary refusal`.

## Phase 4 — `aeat security provision` interactive command

**Goal**: the canonical first-run command for setting up the security layer.

**Files**:
- `src/aeat/entrypoints/cli/security.py` — new `provision_cmd`.
- `src/aeat/entrypoints/cli/test_security.py` — `TestProvisionCommand` test class.
- `src/aeat/adapters/persistence/storage/_recovery.py` — new module: recovery-key generation + BIP-39-style mnemonic encoding + recovery-key wrapping.
- `src/aeat/adapters/persistence/storage/_test_recovery.py` — round-trip tests.

**`aeat security provision` flow**:

```
1. Check current state. If keys already exist: refuse unless --force.
2. Backend prompt:
     "Choose backend:
        [1] OS keychain (recommended; default)
        [2] File-fallback (passphrase-based)
        [3] Unsecured (testing only — requires AEAT_ALLOW_UNENCRYPTED=1)"
3. For (2): prompt for passphrase + confirmation.
4. Generate master key.
5. Generate recovery key (32 random bytes); display Cryptomator-style 24-word mnemonic.
   "Save this recovery key. We will never show it again. Without it,
   you cannot recover your data if you lose your passphrase or keychain."
6. Wrap master.key with recovery-key-derived KEK (HKDF over recovery-key
   bytes); persist as `master.recovery.key` in secret-store dir.
7. Round-trip verify: encrypt + decrypt a 16-byte canary; abort + roll
   back on failure.
8. Print "Security layer provisioned." + the recovery-key mnemonic ONCE.
```

**Recovery key encoding** (`src/aeat/adapters/persistence/storage/_recovery.py`):
- BIP-39-style: 24 words from a fixed 2048-word wordlist (English, fits in repo at ~13 KB).
- Each word encodes 11 bits → 24 words = 264 bits = 32 bytes + checksum.
- Standard BIP-39 checksum (SHA-256 first byte / 4 bits for 32-byte payload).

**Tests**:
- `test_recovery_key_round_trip_via_mnemonic`
- `test_recovery_key_rejects_invalid_checksum`
- `test_recovery_key_unique_per_provision`
- `test_provision_refuses_when_keys_exist_without_force`
- `test_provision_keychain_path`
- `test_provision_file_fallback_path`
- `test_provision_emits_recovery_key_once`
- `test_provision_round_trip_verify_aborts_on_failure`

**Commit message**: `feat(cli): wave-17 phase 4 — aeat security provision interactive command`.

## Phase 5 — `aeat security recover --recovery-key` + `aeat security key-export`

**Goal**: complete the recovery + backup story.

**Files**:
- `src/aeat/entrypoints/cli/security.py` — `recover_cmd` + `key_export_cmd`.
- `src/aeat/entrypoints/cli/test_security.py` — tests.
- `src/aeat/adapters/persistence/storage/_recovery.py` — recovery-key unwrap helper.

**`aeat security recover --recovery-key "<24 words>" [--new-passphrase]`**:

```
1. Validate the 24-word mnemonic checksum.
2. Read `master.recovery.key`; unwrap master.key bytes via the
   recovery-key-derived KEK.
3. Re-mint the master.key + master.kdf + salt under the operator's
   chosen NEW backend (keychain or file-fallback).
4. Round-trip verify.
5. Print "Master key recovered. The previous master.key has been replaced."
```

**`aeat security key-export <output-path>`**:

```
1. Confirm the active provider is keyring or file-fallback (not
   unsecured — would be misleading).
2. Build a portable JSON record:
   {
     "schema_version": 1,
     "exported_at": "<iso8601>",
     "backend": "keyring" | "file",
     "kdf_params": <master.kdf JSON> (file backend only),
     "salt_b64": <salt b64> (file backend only),
     "wrapped_master_key_b64": <master.key b64>
   }
3. Write to <output-path> with mode 0o600.
4. Print "Master-key state exported to <output-path>. Store this off-site."
```

The export is encrypted-at-rest already — it just packages the existing wrapped artefacts in a portable container. No new cryptography is introduced.

**Tests**:
- `test_recover_round_trip_with_new_passphrase`
- `test_recover_rejects_wrong_recovery_key`
- `test_key_export_round_trip_via_provision_into_fresh_store`
- `test_key_export_refuses_unsecured_mode`

**Commit message**: `feat(cli): wave-17 phase 5 — aeat security recover + key-export`.

## Phase 6 — Setup wizard wire-in

**Goal**: `aeat setup` invokes `aeat security provision` after the profile-write step.

**Files**:
- `src/aeat/application/setup/_wizard.py` — call into provision flow.
- `src/aeat/application/setup/_env_writer.py` — refactor profile-write to NOT silently mint; require provision-first.
- `src/aeat/application/setup/test_cli.py` — update tests.

**Sequencing**:

```
aeat setup [--non-interactive]
  → collect operator profile (existing)
  → write env file (existing)
  → write profile file via the new `aeat security provision` flow
    (which mints the master key BEFORE the profile is written so the
    profile is encrypted under a known-provisioned key, with the
    recovery key shown to the user)
```

**Backward compatibility for existing operators**: if `master.kdf` already exists, skip the provision step (operators already provisioned via the silent-mint path land on a healthy state).

**Refactor**: `_env_writer.write_profile_file` checks `_resolve_master_key_provider()` succeeds with material-missing → `MasterKeyMaterialMissingError`. The setup wizard catches this and routes through provision; the standalone CLI usage points the user at `aeat security provision` first.

**Tests** (existing test surface adjusted):
- `test_setup_non_interactive_provisions_security_layer`
- `test_setup_skips_provision_when_keys_already_exist`
- `test_setup_displays_recovery_key_once`

**Commit message**: `feat(setup): wave-17 phase 6 — wire aeat security provision into setup wizard`.

## Phase 7 — Documentation

**Goal**: every Kent-facing surface mentions the security layer where relevant.

**Files**:
- `README.md` — new `## Security` section: high-level summary; pointer to runbook + getting-started.
- `docs/getting-started.md` — new `## First-run security setup` section between the wizard and the financial-ingest sections; covers what the wizard does, what the recovery key is for, the unsecured-mode opt-out, and the doctor check.
- `docs/security-runbook.md` — new sections: `## Recovery flow`, `## Key export and import`, `## Failure-mode quick reference` (the three-class table).
- `env/.env.example` — document `AEAT_ALLOW_UNENCRYPTED`, document `aeat_secret_store_backend=unsecured` value.

**Commit message**: `docs(security): wave-17 phase 7 — first-run + recovery + opt-out documentation`.

## Phase 8 — First-run integration test

**Goal**: end-to-end CI coverage for the brand-new-user path.

**Files**:
- `tests/integration/test_first_run_security.py` — new file.

**Test scenarios**:

1. **Fresh-fs first-run keychain path** (skip on platforms without keyring):
   - empty tmp_path; `AEAT_SECRET_STORE_BACKEND=keyring`.
   - `aeat setup --non-interactive --tax-id 00000000T --modelo 130 ...`.
   - assert `aeat doctor` returns 0; security rows all green.
   - `aeat financial ingest --persist <fixture-stmt.csv>`.
   - assert ciphertext on disk; round-trip `aeat secrets list` works.
   - `aeat security key-export /tmp/aeat-key-backup.json`.
   - re-run `aeat setup` — confirm idempotent (no second provision).

2. **Fresh-fs first-run file-fallback path**:
   - `AEAT_SECRET_STORE_BACKEND=file`; `AEAT_SECRET_PASSPHRASE=test-pp`.
   - same flow; assert provision prompts captured the passphrase.
   - assert recovery-key was emitted exactly once.

3. **Fresh-fs first-run unsecured path with synthetic NIF**:
   - `AEAT_ALLOW_UNENCRYPTED=1`; `AEAT_SECRET_STORE_BACKEND=unsecured`.
   - `aeat setup --tax-id 00000000T` (synthetic).
   - assert success; `aeat doctor` reports the unsecured-mode warning loudly.

4. **Fresh-fs first-run unsecured path with real NIF (refusal canary)**:
   - same env; `--tax-id 12345678Z` (validates as real NIF).
   - assert `aeat setup` exits 1 with `UnsecuredModeRefusedError`.

**Commit message**: `test(integration): wave-17 phase 8 — first-run security integration test`.

## Phase 9 — Audit gate + reviews

**Goal**: close the wave properly.

**Artefacts**:
- `.vault/audit/2026-04-30-secure-persistence-foundation-wave17-audit.md` — verdict + residual risks.
- PR comment requesting `@gemini review` + `@codex review`.
- PR body update: wave-17 row in the wave-roadmap table; cryptographic-profile section refreshed; verification block updated.

## Risk + complexity assessment

| Risk | Mitigation |
| ---- | ---------- |
| BIP-39 wordlist license | Use the public-domain English BIP-39 list (Bitcoin Core uses it; well-established). Bundled in `src/aeat/adapters/persistence/storage/_bip39_wordlist.py`. |
| Recovery-key UX clarity | Mirror Cryptomator's "print this and store it" wording verbatim (already battle-tested). |
| Setup-wizard regression | All existing setup tests must pass unchanged after phase 6 (the wizard's external behaviour for existing-store operators is identical). |
| `aeat doctor` check explosion | New rows are scoped to a `_security_rows()` helper so the doctor's main path stays readable. |
| `MasterKeyUnavailableError` subclass break | Existing test surface uses `pytest.raises(MasterKeyUnavailableError)` which still matches via inheritance. No breakage. |

## Dependencies between phases

Phases 1–3 are independent; can land in any order.
Phase 4 depends on phase 2 (error subclasses) + phase 3 (unsecured backend opt-out wiring needed for the "unsecured" provision branch).
Phase 5 depends on phase 4 (recovery-key generation lives in `_recovery.py` introduced by phase 4).
Phase 6 depends on phase 4 (provision command exists) + phase 2 (refactored throws).
Phase 7 depends on all earlier phases (documents what's actually shipped).
Phase 8 depends on all earlier phases (exercises the full surface).
Phase 9 depends on all earlier phases.

## Estimated commits + LoC

- Phases 1–6: 1 commit each → 6 commits.
- Phase 7: 1 commit.
- Phase 8: 1 commit.
- Phase 9: audit-gate doc + PR-body refresh = 1 commit.
- **Total: 9 commits, ~1500–2000 LoC across src + tests + docs.**

## Out of scope (explicitly)

- **Multi-operator host support**: per the project's autónomo-target constraint, single-operator-per-host is the canonical case. The keyring service identifier prefix (D3 mention) is defensive-only; no multi-tenant UX flows.
- **Hardware-token backends** (YubiKey, secure enclave): future wave; out of wave-17 scope.
- **Cryptographic primitive swap** (post-quantum KDF, ChaCha20 alternate AEAD): wave-12 ADR locked-in Argon2id; wave-17 does not re-open that decision.
- **Substrate changes**: explicitly out of scope per the wave-17 ADR.

## Verification gates

Each phase ships with:
- Lint clean (ruff check + ruff format).
- Type check clean (`ty`).
- Unit tests pass (per-module).
- Integration tests pass (after phase 8).
- Pre-commit hook clean.
- No skipped tests (per the project mandate).

The wave-17 audit gate (phase 9) verifies:
- Every gap G1–G10 from the research artefact is closed.
- Every D1–D4 ADR decision is implemented as accepted.
- The first-run integration test exercises every backend path including the NIF-canary refusal.
- Documentation covers the operator runbook for every new surface.
