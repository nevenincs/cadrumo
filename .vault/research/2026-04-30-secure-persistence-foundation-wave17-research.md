---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave15-16-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave14-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-final-security-audit]]"
---

# `secure-persistence-foundation` research: wave-17 Kent UX security integration

Research foundation for the wave-17 ADR. Two-axis investigation: (1) gap inventory across the existing Kent UX surfaces against the wave-1..16 substrate; (2) industry-standards survey across mature encrypted-storage tools to ground the design decisions in observed best practice.

## Context

Waves 1..16 shipped the cryptographic substrate end-to-end: AES-256-GCM AEAD, HKDF-SHA256 per-purpose KEK, Argon2id passphrase-derived KEK, master-key rotation across envelopes + blob-store wrapped DEKs, KDF-version migration with partial-recovery, corpus integrity SHA-256 manifest, per-file `exclusive_file_lock` with `O_CLOEXEC`/`O_NOINHERIT`, trilingual error registry. The substrate is **cryptographically complete**.

The Kent (operator) UX is **not yet enrolled** in this layer. A brand-new user running `aeat setup` followed by `aeat financial ingest --persist` will silently mint a master key without any feedback, never see the security-layer activation, and have no way to introspect whether the security configuration is healthy. Failure modes (lost passphrase, locked keychain, missing master key) surface as opaque cryptographic exceptions rather than UX-actionable errors.

This is the gap wave-17 closes.

## Part 1 — Gap inventory (existing Kent UX surfaces)

A targeted audit of every Kent-facing surface that interacts with the security layer, cross-referenced against the substrate's actual behaviour at HEAD.

### G1 — Silent first-run master-key minting (CRITICAL)

`src/aeat/application/setup/_env_writer.py:179-185` — `write_profile_file()` calls `save_encrypted_envelope(envelope, target, master_key_provider=_resolve_master_key_provider(), ...)`. On a fresh installation with the file-fallback backend, `_resolve_master_key_provider()` triggers `FileFallbackMasterKeyProvider.get_master_key()`, which silently mints a 32-byte master key and persists `master.kdf` + `master.key` + `salt`. The setup wizard prints nothing about this. The minting log message is `_log.info()` — invisible to TTY users unless `--debug` is set.

**Operator impact**: a user finishes the setup wizard believing they configured a profile, with no awareness that:
- A master key was just minted on their disk.
- The key wraps the profile they wrote.
- Loss of the key (corrupted disk, misplaced backup) means loss of the profile and every subsequent FINANCIAL/AUDIT/IDENTITY record.

### G2 — `aeat doctor` has zero security checks (CRITICAL)

`src/aeat/entrypoints/cli/doctor.py:891-923` — the `collect_rows` orchestrator wires roughly 40 health rows: certificate path, certificate friendly name, certificate backend, certificate verify URL, output language, profile path, drafts dir, submissions dir, manuals root, live-tests flag, etc. Zero rows touch:

- Whether the secret-store directory exists and is writable.
- Which backend is active (`KEYRING` / `FILE` / `AUTO`-fallback).
- For file-fallback: whether `master.key` + `master.kdf` + `salt` exist, are readable, and decrypt under the cached passphrase.
- For keyring: whether the OS keychain is accessible and reachable from the current process.
- Whether the master.kdf is at the expected version (post-wave-12 = v2 Argon2id).
- Whether any envelope on disk fails to decrypt under the active master key (canary for botched rotations).

**Operator impact**: an operator running `aeat doctor` after any of (system reinstall, profile copied between machines, OS keychain reset, KDF migration interrupted) cannot tell whether the security layer is healthy. The first warning surfaces only when a real persistence operation fails opaquely deep inside a CLI command.

### G3 — Documentation entirely silent on security (CRITICAL)

`README.md`, `docs/getting-started.md`, `docs/security-runbook.md` (added in wave-15+16):

- README never mentions encryption, master keys, or the security layer.
- `getting-started.md` describes the setup wizard, the `just bootstrap` flow, the "your first filing" path — **without ever explaining that `aeat setup` triggers master-key minting**, that subsequent CLI commands depend on the master key being available, or that the operator's profile is encrypted under that key.
- `security-runbook.md` (wave-15+16 added it) is operator-task-focused — `rotate-master-key`, `verify-corpus`, `migrate-master-key-kdf`. It does not cover the **first-run** path: no "How does the security layer activate?", no "Where is my master key stored?", no "What if I want my data unencrypted?", no "How do I back up the master key?".

**Operator impact**: a user reading the project's own docs has zero visibility into the security model that protects every byte they persist.

### G4 — No first-run integration test (HIGH)

`src/aeat/application/setup/test_cli.py:31-46` — the setup CLI test fixture injects an `EphemeralMasterKeyProvider`. The non-interactive end-to-end test (`test_setup_non_interactive_runs_end_to_end` at line 95-116) never exercises the real file-fallback path. No integration test simulates:

1. Brand-new user with no prior `master.key` / `master.kdf` / `salt`.
2. `aeat setup --non-interactive` minting the master key.
3. `aeat doctor` reporting healthy security configuration.
4. `aeat financial ingest --persist <stmt.csv>` round-tripping through the encrypted substrate.
5. `aeat secrets list` returning successfully.
6. Re-running `aeat setup` — does it preserve or stomp the master key?

**Operator impact**: regressions in the first-run path are not caught by CI.

### G5 — Opaque failure modes when master key unavailable (HIGH)

`src/aeat/entrypoints/cli/financial/ingest.py:33-68` and equivalent for every other persisting CLI: the master-key provider is invoked transitively via `_resolve_master_key_provider()` and the underlying `FileFallbackMasterKeyProvider.get_master_key()` raises `MasterKeyUnavailableError` (or `MasterKeyKdfVersionError` post-wave-12, or `KeyringUnavailableError` on keychain failures). The CLI's error-envelope renders these as `INTERNAL: ...` with the raw cryptographic detail.

The three failure classes are **not distinguished** in the user-facing message:
- **Keychain locked / unavailable** (recoverable by unlocking the OS keychain).
- **Wrong passphrase** (recoverable by re-entering).
- **Lost key material entirely** (only recoverable from a backup, if one exists).

A user who sees `MasterKeyUnavailableError: failed to decrypt master key` cannot tell which case they are in.

### G6 — No `aeat security provision` command (HIGH)

The substrate has `aeat security {rotate-master-key, verify-corpus, migrate-master-key-kdf}` — three operator-task tools. There is no Kent-facing **set up the security layer** command. New users have no entry point to:

- Choose between keychain-backed and file-fallback explicitly.
- See the master key being created.
- Set or change the file-fallback passphrase.
- Generate and view a recovery key.
- Test that the configuration is healthy.

The current behaviour is "first persistence operation triggers silent provisioning" — anti-pattern per the industry survey.

### G7 — No `aeat security key-export` (recovery / backup) (MEDIUM)

`borg key export` is the canonical first-class master-key backup operation — Borg explicitly tells users to run it after `borg init`. `aeat` has no equivalent. The only path to back up the master key is for the operator to manually copy `master.key` + `master.kdf` + `salt` (file-fallback backend) or `keyring`-internal storage (no portable backup).

**Operator impact**: lost-disk scenarios produce permanent FINANCIAL data loss.

### G8 — No opt-out for unsecured-DB mode (MEDIUM)

`src/aeat/config.py` (`SecretStoreBackend` enum) — three values: `AUTO`, `KEYRING`, `FILE`. None of them disable encryption. The substrate is hard-cutover to ciphertext at rest.

**Operator impact**: testing scenarios, throwaway data, CI environments, and educational use cases have no first-class path. Operators who want "just play with the tool, don't bother me with security" face an opaque setup. Per the industry survey, mature tools (Restic, Borg) keep this opt-out behind a hostile-named flag with NIF-or-equivalent guardrails.

### G9 — Profile-vs-encryption linkage undocumented (MEDIUM)

`docs/getting-started.md:64-84` describes the profile as a "JSON file" written by the wizard. The actual on-disk artefact is a `CipherEnvelope[AutonomoProfile]` at `SensitivityClass.IDENTITY` (`src/aeat/application/setup/_env_writer.py:176-187`). The encryption is bound to the master-key lifecycle — losing the master key means losing the profile.

**Operator impact**: operators don't know the profile is itself a cryptographic checkpoint.

### G10 — Settings discoverability gap (LOW)

`env/.env.example:115-139` documents `AEAT_SECRET_STORE_BACKEND`, `AEAT_SECRET_STORE_DIR`, `AEAT_BLOB_STORE_DIR`. None of these are mentioned in `README.md` or `docs/getting-started.md`. A docs-first reader never discovers that backend selection is configurable.

## Part 2 — Industry standards survey

Web research across **Bitwarden CLI, 1Password CLI, KeePassXC, age/rage, Borg, Restic, Kopia, Cryptomator, gocryptfs, GnuCash, Beancount, GPG**. Three doctrines emerge.

### D1 — Default-secure is the modern norm

Mandatory encryption is the modern default for any tool that stores meaningful data at rest. Bitwarden, 1Password, Kopia, Cryptomator, and KeePassXC simply **refuse** the unencrypted path. Restic and Borg keep an opt-out only behind a hostile-named flag (`--insecure-no-password`, `borg init -e none`) that is on the deprecation list — Borg 2 removes it entirely.

The pure file-encryption tools (age, rage) leave keyfile-protection-of-the-keyfile to the user but never produce unencrypted ciphertext.

GnuCash is a counter-example: SQLCipher is available at the SQLAlchemy layer but the project explicitly defers password-protection to the OS — "GnuCash is single-user; password-protect the OS account." A 14-year-old user-voice request for app-level passwords remains open. This is the "we punt on encryption" stance — relevant only because it's instructive in its limitations.

Beancount is the deliberate counter-example: plain-text by design, no encryption, no passphrase, no setup. Stated rationale: human readability, version-control friendliness, 20-year archival durability. Users wanting encryption compose it externally (gocryptfs, age, full-disk encryption).

**Pattern for `aeat`**: AEAT data is FINANCIAL + IDENTITY + AUDIT class with legal weight (Spanish tax filings). The Beancount stance does not fit. The GnuCash stance does not fit on Windows where the OS account is the operator's daily driver. The mandatory-encryption stance (Kopia, Cryptomator, Bitwarden) is the right baseline.

### D2 — Three master-key provisioning families

- **Passphrase-only** (KeePassXC, Borg, Restic, Kopia, Cryptomator, gocryptfs): user enters a passphrase at init; KDF (Argon2 or scrypt) derives the KEK; the KEK wraps a random per-store master key persisted alongside.
- **Keyfile-only** (age, rage): user-supplied keyfile, period. Filippo Valsorda's stated rationale: passphrase-protected identity files are not necessary for most use cases.
- **OS-mediated unlock** (1Password biometric, Bitwarden GUI): biometric or OS-keychain wraps the KEK. Pure CLIs almost never write secrets to the OS keychain themselves — they delegate to a daemon (1Password app, gpg-agent) or to the user (`export BW_SESSION="..."`).

The 1Password+Bitwarden hybrid (keychain-preferred, passphrase fallback) is the strongest CLI pattern observed.

**Pattern for `aeat`**: `aeat` already has `KeyringMasterKeyProvider` (OS-keychain) and `FileFallbackMasterKeyProvider` (passphrase-derived Argon2id). The architecture ALREADY matches the hybrid model. The wave-17 work is wiring the UX to make the choice explicit and visible.

### D3 — Onboarding scope is brutally narrow

Every tool that survived contact with users collapses first-run to **"name the store + supply one secret"**. Advanced choices (cipher, KDF cost, hash) hide behind explicit flags or Advanced toggles. Cryptomator's six-step wizard is at the upper limit of acceptable complexity.

GPG is the cautionary tale — `gpg --gen-key` originally asked users about key types, sizes, expiration, comment fields, and subkeys before they had encrypted anything. The `--quick-generate-key` / `--full-generate-key` split is a direct response. **Lessons**: do not ask the user about cryptographic primitives during onboarding; default expirations matter; the gap between "I have a key" and "I successfully sent an encrypted message" must be measured in seconds.

**Pattern for `aeat`**: the wave-17 provision command must be **two interactions max**: (1) "We're about to encrypt your data. Default: OS keychain (no passphrase needed). Switch to passphrase mode? [y/N]" + optionally (2) the passphrase entry. Every cryptographic primitive (Argon2id parameters, AES variant, HKDF context list) is hidden.

### D4 — Recovery-key UX is the strongest lost-passphrase mitigation

Cryptomator: at vault-create time, generates a **recovery key**, displays it once with explicit print-and-store instructions, never persists it. Lost password → user enters the recovery key (auto-completion UX helps when reading from paper). Lost both → unrecoverable.

gocryptfs: prints the master key once at init with the explicit instruction "Print it to a piece of paper and store it in a drawer."

Borg: documents `borg key export` as the canonical backup command after `borg init`. Issue #3913 explicitly asks `borg init` to print a louder warning to back up both keyfile and passphrase.

Bitwarden, 1Password: zero-knowledge — lose the master password, lose the vault.

**Pattern for `aeat`**: a Cryptomator-style recovery key + a Borg-style `aeat security key-export` command. Both are essential for FINANCIAL data with legal weight — silent permanent data loss is unacceptable.

### D5 — Failure-mode UX must distinguish three classes

Across the survey, the strongest tools distinguish:

- **Keychain locked / unavailable** (recoverable): "Unlock your keychain and try again."
- **Wrong passphrase** (recoverable, retry with backoff): "Passphrase didn't unlock the master key. Try again. [3 attempts before lockout]"
- **Recovery-key needed** (deliberate fallback path): "Master key is unavailable. Use `aeat security recover --recovery-key <code>` to restore."

Borg's generic "exceeded maximum password retries" is the anti-pattern called out in issue #7959. The fix is class-specific error messages.

### D6 — Sequencing: profile-first then encryption

Mature wizards establish operator identity (non-secret) BEFORE asking the encryption question. The non-secret operator NIF + business profile + contact details frame the question "we are about to store your tax records, choose how to lock them". Sequencing the other way around forces the user to think about cryptographic primitives before the tool has any context for them.

The 1Password Onboarding sequence is the canonical example: account email + name → secret key generation + master password → biometric setup → vault auto-binds to the identity. The encryption is the LAST step, framed by the established identity.

## Recommendation for wave-17 ADR

Translate the gap inventory + industry survey into four hard decisions:

**D1 — Opt-out posture**: **default-secure with hostile-named flag**. Mandatory encryption baseline (matches Bitwarden / 1Password / Kopia / Cryptomator). For testing / throwaway scenarios: `--insecure-no-encryption` flag + `AEAT_ALLOW_UNENCRYPTED=1` env var. **Refuse** the flag if a real NIF is in the operator profile (NIF-canary). Matches Restic/Borg-2 stance; legible-and-embarrassing per the survey.

**D2 — Master-key provisioning model**: **hybrid** (already built). Keychain preferred (auto-mode falls back to file-fallback on keychain unavailability); Argon2id passphrase fallback; document age-style keyfile path for headless / CI use. Wave-17 wires the UX wrapper — substrate is unchanged.

**D3 — Sequencing**: **profile-first then encryption**. The wizard establishes operator NIF + profile, then frames the security question. Pre-binds the keychain entry to the operator identity.

**D4 — Recovery + backup**: **Cryptomator recovery-key pattern + Borg `key-export` pattern**. At provision time: generate a 32-byte recovery key, derive a Cryptomator-style human-readable mnemonic encoding, display once, never persist. Add `aeat security key-export <out>` as a first-class CLI for keychain backup. Three-failure-class error messages distinguish keychain-locked / wrong-passphrase / recovery-needed.

The wave-17 ADR formalises these decisions; the wave-17 plan sequences the implementation; the wave-17 execute lands the code; the wave-17 audit gate verifies coverage.
