---
tags:
  - '#research'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-04-12-data-storage-research]]'
  - '[[2026-04-12-cert-auth-research]]'
  - '[[2026-04-12-setup-wizard-research]]'
  - '[[2026-04-12-pr28-storage-retro-research]]'
  - '[[2026-04-12-data-storage-adr]]'
  - '[[2026-05-08-secure-storage-legacy-path-audit-reference]]'
---

# secure-backend-passkey-safety research: master-passkey enrollment + custody

## 1. problem statement

The Secure backend (the at-rest crypto substrate under
`src/aeat/adapters/persistence/storage/`) holds the canonical local copy
of every confidential artefact the application produces: presentation
evidence, justificantes (NRC, CSV codes), draft submissions, ledger
ratios, and the operator profile itself. All of this content is sealed
under a 32-byte AES-256-GCM master key.

Three substrate-level defects compound into a critical data-loss + UX-safety surface:

1. **Silent auto-mint.** A fresh `aeat config init` never asks the operator for a passphrase, never displays a recovery mnemonic, and never warns that loss of the OS keychain entry (or its companion passphrase) is a permanent, unrecoverable destruction of every sensitive record in the substrate. The master key is minted lazily on the first encrypted write or read, behind the operators back.
2. **Custody opaque to the operator.** The substrate ships with a three-backend resolver (`auto` / `keyring` / `file`) whose default is `auto`. The operator is never informed which backend won, where the key landed, or how to back it up.
3. **Co-location with ciphertext.** Both the encrypted SQLite database and the `file` backends wrapped master key, salt, and KDF parameters default to siblings under the same `var/` directory tree. A single stolen / rsynced / cloud-synced `var/` directory delivers every record AND the wrapped key to an attacker; passphrase strength is then the only line of defence. Encryption-at-rests threat model (host compromise / lost laptop / mis-shared backup) is half-defeated by the default layout.

There is high-quality recovery cryptography in the tree (`_recovery.py`: BIP-39 24-word mnemonic, HKDF-derived KEK, AES-256-GCM wrap of the master key, atomic on-disk persistence). It is not wired to any operator-facing CLI surface. The substrates own error messages point operators at commands (`aeat security recover`, `aeat security provision`) that do not exist.

The threat model the substrate must defend (in increasing severity):

- *Curious housemate* who briefly accesses an unlocked laptop. Defeated by OS account separation; not the substrates concern.
- *Lost or stolen laptop.* The substrate must guarantee that disk access alone does not yield plaintext. Current state: depends on backend. Keyring backend: protected by OS user login. File backend: protected ONLY by operator-supplied `AEAT_SECRET_PASSPHRASE` strength AND non-co-location of key + ciphertext.
- *Cloud-synced project directory* (Dropbox / OneDrive / iCloud Drive / Google Drive Desktop). The substrate must guarantee that an attacker who steals the synced folder cannot read the records. Current state: with file backend on default paths, the attacker has the wrapped key AND the ciphertext together.
- *Backup leak.* Same as cloud sync.

Equally, the substrate must defend the operator against themselves: loss of OS user account, OS reinstall, machine replacement, keychain corruption. Today, every one of those events is silently irrecoverable.

## 2. current implementation map

### 2.1. master-key minting and providers

The substrate exposes a `MasterKeyProvider` Protocol with four concrete implementations selected by the `aeat_secret_store_backend` setting:

- `KeyringMasterKeyProvider` -- backend = `keyring`. On first call, mints 32 random bytes via `secrets.token_bytes(KEY_SIZE)`, base64-encodes them, and writes the result to the OS keychain under service `aeat:secure-persistence` / account `master`. See `src/aeat/adapters/persistence/storage/master_key/_master_key.py` lines 80-84 (constants), 432-453 (mint path), 386-453 (`get_master_key`).
- `FileFallbackMasterKeyProvider` -- backend = `file`. Persists three artefacts under `aeat_secret_store_dir`:
  - `master.key` -- base64 of nonce + ciphertext + tag for an AES-256-GCM-wrapped 32-byte master key. Lines 504-506, 624-658.
  - `master.kdf` -- JSON Argon2id parameters (`memory_cost=19 MiB, time_cost=2, parallelism=1`, `version=2`, base64 salt). Lines 89-105, 124-135, 626-655.
  - `salt` -- 16 raw bytes, also embedded in `master.kdf.salt_b64`. Lines 98-99, 656.
  The KEK that wraps `master.key` is derived from the operators passphrase via Argon2id (`_derive_kek`, lines 203-218; `_derive_kek_with_params`, lines 771-781).
- `UnsecuredMasterKeyProvider` -- backend = `unsecured`. Returns a **published deterministic 32-byte constant** (`_UNSECURED_PUBLISHED_KEY`, lines 840-841). Guarded by the env-var canary `AEAT_ALLOW_UNENCRYPTED=1` (lines 987-998) and by the real-NIF refusal in `refuse_unsecured_with_real_nif` (lines 913-943, `_SYNTHETIC_TAX_IDS` lines 875-883). Provides ZERO confidentiality by design; intended for tests and tutorials.
- `EphemeralMasterKeyProvider` -- in-memory only, tests-only (lines 808-830).

Selection logic in `get_master_key_provider`, `src/aeat/adapters/persistence/storage/master_key/_master_key.py` lines 946-1059. The `auto` backend (default per `SecretStoreBackend.AUTO` in `src/aeat/core/config.py` line 179) first probes the OS keychain. On `KeyringUnavailableError` it falls back to the file backend silently and logs only at INFO (line 1019). On `MasterKeyKeychainLockedError` with no existing file-fallback artefacts it raises; with existing artefacts it routes through them (lines 1024-1059).

### 2.2. on-disk location of the key -- confirmed fatal-flaw evidence

Default settings in `src/aeat/core/config.py`:

- `aeat_database_url` default = `sqlite:///PROJECT_ROOT/var/aeat.db` (line 167).
- `aeat_secret_store_dir` default = `PROJECT_ROOT/var/secrets` (lines 201-204).
- `aeat_blob_store_dir` default = `PROJECT_ROOT/var/blobs` (lines 205-208).

For the file backend, the wrapped master key lives at `var/secrets/master.key`, the KDF parameters at `var/secrets/master.kdf`, the salt at `var/secrets/salt`, AND the SQLite database holding the ciphertext payload column lives at `var/aeat.db` -- **siblings under the same `var/` parent**.

A single recursive copy of `var/` or a `var/` directory that lands inside a cloud-synced directory delivers to an attacker:

1. The full ciphertext substrate (`var/aeat.db`, `var/blobs/`).
2. The wrapped master key (`var/secrets/master.key`) and its KDF parameters (`var/secrets/master.kdf` -- human-readable per the module docstring lines 29-32).
3. The salt that goes into Argon2id KEK derivation (`var/secrets/salt`).

Confidentiality of every record then reduces to: the strength of the operators `AEAT_SECRET_PASSPHRASE` against an offline Argon2id-grinding attack with `memory_cost=19 MiB, time_cost=2, parallelism=1` (OWASP top-tier params per lines 89-96, but offline-attackable nonetheless). A weak passphrase yields plaintext; a strong passphrase yields delay. The encryption-at-rest threat model is materially weakened.

For the `keyring` backend the situation is structurally different -- the key sits in Windows Credential Manager / macOS Keychain / Linux Secret Service, NOT in `var/`. A `var/` exfil yields ciphertext only. This is the regime the substrates threat model implicitly assumes, but `auto`-mode silently falls back to file when the keychain backend is `fail.Keyring` or `null.Keyring` (lines 292-312), and the operator is never told.

### 2.3. what is encrypted

Tracing the column-level encryption hooks in `src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py`: the `EncryptedBytes` `TypeDecorator` (lines 152-167 per grep) wraps SQLAlchemy column reads / writes. The `secure_objects` table at `src/aeat/adapters/persistence/storage/sql/secure_objects.py` stores payload bytes under that decorator (the `payload` column on `_orm.SecureObjectRow`). Namespaces include workflow state, user profile facts, ledger snapshots, and (per `src/aeat/adapters/persistence/storage/test_sensitive_persistence_policy.py`) classification-tagged records under `SensitivityClass`.

The `EncryptedBlobStore` at `src/aeat/adapters/persistence/storage/blob_store/_blob_store.py` mirrors the same crypto for content-addressed blobs.

In short: the substrate aspires to encrypt every "sensitive" classification on its way out of the application boundary. The exact classification matrix is enforced by `src/aeat/core/classification.py` and consumed at the column boundary.

### 2.4. entry points that trigger key creation

Master-key minting is **lazy** -- there is no eager provision path. The first call to `get_master_key()` on any provider mints if absent. Triggers found by tracing engine / repository / provider construction:

- `src/aeat/adapters/persistence/storage/sql/engine.py` -- `get_engine()` (referenced by `SecureObjectRepository.__init__`, line 149 of `sql/secure_objects.py`). The first SQL session opened on a column-encrypted table causes the `TypeDecorator` to call `get_master_key_provider().get_master_key()` and mint on demand.
- `src/aeat/application/setup/_service.py::initialize_workspace` lines 12-57 -- calls `workflow_state_repository().update(...)` which in turn opens an encrypted session on the workflow_state namespace. This is the first user-visible touch of the crypto substrate during a fresh `aeat config init` flow.
- `src/aeat/application/user_profile/_orchestration.py::register_active_profile` -- invoked from the same setup service, persists the operators facts via the secure-object repository.

Every one of these paths flows through `get_master_key_provider()` without any opportunity for the operator to choose a passphrase, acknowledge the data-loss risk, or be shown a recovery code.

The CLI surface in `src/aeat/entrypoints/cli/_config/__init__.py` lines 628-695 (`config init` command) defines a Typer command with options for `--profile`, `--tax-id`, `--activity`, `--iva-regime`, `--auth-provider`, `--certificate-path`, etc. **There is no `--passphrase`, `--recovery-key`, `--secret-store-backend`, `--unlock`, or `--rekey` option.** A grep for `passphrase`, `master key`, `recovery`, `mnemonic`, `unlock`, `passkey` across `src/aeat/entrypoints/cli/` returns zero matches against any operator-facing command body.

### 2.5. user-facing surface today

Grep for any operator-facing string mentioning passkey / passphrase / master key / recovery / unlock across the whole `src/aeat/` tree returns:

- Module docstrings inside the storage substrate (`src/aeat/adapters/persistence/storage/master_key/_master_key.py` and `_recovery.py`) -- internal documentation, never shown to operators.
- Error messages inside the file backend pointing operators at `aeat security recover --recovery-key` and `aeat security provision --force` (lines 558-563, 619-622, 1056-1058). **These commands do not exist anywhere in `src/aeat/entrypoints/cli/`.** The operator who hits a torn-install or passphrase-mismatch error sees instructions for a nonexistent command.
- The wizard catalogue (`src/aeat/application/wizard/_catalogue.py`) and prompter (`_prompter.py`) contain no prompt that touches the master-key / passphrase / recovery surface.
- Translation catalogues (locale .po files) contain no user-facing strings on any of: master key, recovery code, data-loss warning, passphrase choice, OS-keychain consent.

### 2.6. lock / unlock semantics

There is no operator-facing lock / unlock concept. Once acquired the master key is cached for the **lifetime of the process**:

- `KeyringMasterKeyProvider._cache` -- class-level dict keyed by `(service, username)`, lines 348-349, populated on read (line 452), cleared only by `_reset_for_tests` (lines 455-461) and the `atexit` hook (`_purge_caches_at_exit`, lines 794-805).
- `FileFallbackMasterKeyProvider._cached_passphrase`, `_cached_master_key` -- class-level, lines 473-475, populated on first resolve (lines 519-521, 567-568), cleared by `_reset_for_tests` and `atexit` (lines 783-805).

A long-running daemon would hold the master key in memory for its entire uptime. There is no seal / auto-lock-after-N-minutes concept. There is no `aeat config unlock` / `aeat config lock` command.

### 2.7. profile-lifecycle hooks

- **Rotation**: implemented at the crypto level (`src/aeat/adapters/persistence/storage/_rotation.py` lines 1-50 and beyond -- re-encrypts each cipher envelope under a new master key via temp-file + `os.replace`). Not wired to any CLI surface.
- **Re-key under new passphrase**: `FileFallbackMasterKeyProvider.complete_recovery` (`_master_key.py` lines 660-738) re-wraps a recovered master key under a freshly-derived KEK. Used by the recovery path only; not wired to a `--rekey` CLI command.
- **Export / backup of the key**: no operator surface. The recovery primitives in `_recovery.py` (`generate_recovery_key`, `wrap_master_key`, `save_wrapped_master_key`, `encode_mnemonic`) are never called from anywhere outside their own tests (`_test_recovery.py`) per the cross-package grep.
- **Profile deletion**: `config_profile_remove` exists at `src/aeat/entrypoints/cli/_config/__init__.py::config_profile_remove` (line 534 per the function list). It removes the profile record but does not rotate the master key or revoke prior ciphertext.

### 2.8. backups / exports of the master key

None implemented. The only thing the substrate can do today, when asked to give the key in a portable form so the operator can store it elsewhere, is -- nothing. The substrate has zero operator-facing recovery surface despite shipping a full recovery cryptosystem.

### 2.9. quarantine surface for unreadable rows

A partial mitigation exists: `SecureObjectRepository.quarantine_unreadable_rows` (`sql/secure_objects.py` lines 264-369) moves rows that fail AEAD-tag verification under the current master key into a `secure_objects_quarantine` table. It is invoked from `aeat config repair quarantine` (`_config/__init__.py` line 89). This helps an operator who has rotated keys mid-flight and lost the old one, by isolating now-unreadable rows rather than crashing every load. It does not recover the plaintext -- that is cryptographically unrecoverable once the sealing key is lost. The quarantine table is audit material, not a recovery surface.

### 2.10. summary table of current state

| Concern | State | Evidence |
| :--- | :--- | :--- |
| Operator chooses passphrase at enrolment | NO | `_config/__init__.py:628-695` |
| Operator told a master key was minted | NO | `_service.py:12-57` |
| Operator shown a recovery mnemonic | NO | grep of `entrypoints/` |
| Operator told where key lives | NO | grep of locale / prompter |
| Operator asked to acknowledge data-loss | NO | grep of locale / prompter |
| Recovery primitives implemented | YES (BIP-39 24-word) | `_recovery.py:1-303` |
| Recovery primitives wired to CLI | NO | grep of `entrypoints/` |
| Rotation primitives implemented | YES | `_rotation.py:1-60` |
| Rotation primitives wired to CLI | NO | grep of `entrypoints/` |
| Key co-located with ciphertext (file mode) | YES (`var/secrets/` + `var/aeat.db`) | `config.py:167,201-204` |
| OS-keychain custody (when available) | Used in `auto` mode silently | `_master_key.py:1000-1023` |
| Lock / unlock concept | NO -- cached for process lifetime | `_master_key.py:348,473` |
| Re-key under new passphrase | API exists, no CLI | `_master_key.py:660-738` |
| `aeat security provision/recover` referenced in errors | YES -- but commands do not exist | `_master_key.py:558,619,1056` |
| Quarantine for unreadable rows | YES | `sql/secure_objects.py:264-369` |

## 3. industry comparables -- enrolment and recovery UX

### 3.1. 1Password (Agile Bits)

- Enrolment: user chooses a master password (entropy-policed); the service additionally generates a 128-bit Secret Key client-side and combines both for KDF input (PBKDF2-HMAC-SHA256, 650,000 iterations per current public docs). The user is presented an Emergency Kit PDF containing the Secret Key, account email, and a blank for the master password.
- On-disk: the Secret Key never leaves the device secure enclave unencrypted; on-server only the verifier, never the key.
- Recovery: family/team accounts get an account-recovery group-quorum reset; standalone accounts have **no recovery** if both master password and Emergency Kit are lost.
- Framing: the Emergency Kit literally states that losing it forfeits access to the data.

### 3.2. Bitwarden

- Enrolment: master password (entropy-policed) is the only secret; KDF is PBKDF2-SHA256 (default 600,000 iterations) or Argon2id (opt-in).
- Recovery: optional recovery code generated post-enrolment that resets the master password.
- Framing: Bitwarden cannot reset your master password. First-run banner.

### 3.3. age / age-keygen

- Enrolment: explicit `age-keygen -o key.txt`. The user owns the file; the tool prints the public recipient on stdout and the private identity in `key.txt`.
- On-disk: wherever the user puts `key.txt`. Tool deliberately refuses to make custody decisions.
- Recovery: copy `key.txt` to safe storage. No recovery beyond possession of the file.
- Framing: docs explicitly say the user is the custodian.

### 3.4. GnuPG

- Enrolment: `gpg --full-generate-key` interactively prompts for key type, size, expiry, name/email, AND a passphrase. The passphrase wraps the private key.
- On-disk: `~/.gnupg/private-keys-v1.d/*.key` (passphrase-wrapped) separate from the agent in-memory cache.
- Recovery: `--gen-revoke` produces a revocation certificate the user is told to print and store separately; `--export-secret-keys` produces a portable backup. Loss of the passphrase = loss of access to encrypted content, but key revocation is still possible via the pre-generated cert.
- Framing: docs at every step.

### 3.5. KeePassXC

- Enrolment: mandatory master password, optional additional key file, optional YubiKey HMAC-SHA1 challenge-response.
- On-disk: the `.kdbx` is one file; the key file (if used) is a separate file the user is explicitly told to store elsewhere.
- Recovery: none. Loss = loss.
- Framing: first-run warning dialog recommends printing a recovery sheet.

### 3.6. Aegis (Android 2FA)

- Enrolment: choose password OR biometric-only OR none (with warning). Encrypted export available at any time.
- On-disk: vault is Android app-private storage, encrypted with Argon2id-wrapped key.
- Recovery: encrypted export file under user-chosen password.
- Framing: setup wizard explicitly warns that no-encryption means anyone with the phone can read the 2FA codes.

### 3.7. restic

- Enrolment: prompts for repository password on `restic init`.
- On-disk: repository contains `keys/<id>` files, each a JSON document with PBKDF2 / scrypt params and a wrapped master key. Up to N passwords can each independently unlock the same master key via `restic key add` (separate `keys/<id>` per password).
- Recovery: `restic key add` lets the user pre-provision a second password / passphrase as a recovery anchor.
- Framing: docs are explicit -- without password, data is irrecoverably lost.

### 3.8. BorgBackup

- Enrolment: chooses an encryption mode at `borg init`: `repokey` (key in repo, passphrase-wrapped), `keyfile` (key in `~/.config/borg/keys/`, passphrase-wrapped), `repokey-blake2`, `keyfile-blake2`, `authenticated`, `none`.
- On-disk: the `keyfile` variants explicitly separate key location from repo location.
- Recovery: `borg key export` produces a printable QR / paper-key backup; `borg key import` restores it.
- Framing: `borg init` prints a multi-line warning explaining the trade-off between repokey and keyfile modes.

### 3.9. rclone crypt

- Enrolment: `rclone config` prompts for password + salt; tool obscures the password with a published key via `obscure()`. Docs explicitly warn the obscured value is NOT a secret.
- On-disk: obscured password sits in `~/.config/rclone/rclone.conf` beside the remote definitions. This is exactly the co-location anti-pattern the present substrate suffers from, and rclone docs loudly warn about it.
- Framing: the password is stored in obscured form -- not for security.

### 3.10. macOS Keychain / Windows DPAPI / Linux libsecret

- Custody: OS-bound. Key never crosses an unencrypted boundary; it is bound to the user login. Backup / restore happens at the OS level (Time Machine, OneDrive sync of Credential Manager, etc.).
- Recovery: OS-mediated (FileVault recovery key, BitLocker recovery key, login keyring rebinding when the OS password changes).
- Framing: OS-vendor docs.

### 3.11. HashiCorp Vault

- Enrolment: `vault operator init` outputs 5 unseal keys + a root token. The five keys are produced via Shamir Secret Sharing (threshold 3 of 5 by default -- configurable).
- On-disk: nothing on disk yields plaintext until 3 of 5 unseal keys have been supplied to a running Vault process.
- Recovery: each holder of an unseal key is a recovery anchor; the threshold mechanism tolerates loss of up to (N - K) keys.
- Framing: extensive -- the init output is preceded by a multi-line warning that these keys must be distributed and securely stored.

### 3.12. Cryptomator / VeraCrypt

- Cryptomator enrolment: choose passphrase. Optionally generate a recovery key -- a long Base32 string the user is asked to print.
- VeraCrypt enrolment: choose passphrase, optional keyfiles. No recovery mechanism -- VeraCrypt threat model is remember-the-passphrase-or-lose-everything.
- Framing: Cryptomator: without password AND recovery key, data is unrecoverable. VeraCrypt: tedious-by-design first-run wizard repeats the warning multiple times.

### 3.13. common invariants

Distilling the survey, every system that does this responsibly satisfies (most of) the following invariants:

1. **No silent enrolment.** The user always provides at least one secret (passphrase) OR explicitly opts into an OS-keystore custody model with full understanding (use Touch ID / Windows Hello to unlock). The exception is Aegis biometric-only mode, which surfaces the trade-off explicitly in the setup wizard.
2. **Explicit data-loss framing.** The phrase if-you-lose-this-you-will-lose-your-data is said, in plain language, where the user cannot miss it -- usually accompanied by a one-time-only display of recovery material the user must capture.
3. **A documented recovery path.** Either (a) a recovery code / key file / mnemonic the user is told to back up, (b) a Shamir / quorum recovery scheme, or (c) explicit no-recovery, the-OS-keystore-or-AEAT-portal-IS-your-backup. Silent default of no recovery is not used by any reviewed system.
4. **Key material is not co-located with ciphertext in the same directory.** When the key lives on the same disk, it lives in an OS keystore (DPAPI, Keychain, libsecret), in a user-chosen path the tool refuses to default into the repo directory (age, Borg keyfile), or wrapped under a passphrase that is never persisted (restic, Bitwarden). The rclone obscured-password-beside-config pattern is explicitly documented as not-a-secret.
5. **Lock semantics exist.** The agent / process can be sealed (gpg-agent forget-cache, Vault seal, 1Password auto-lock-after-N-min, BitLocker / FileVault unlock-on-boot). A long-running daemon does not hold cleartext key material indefinitely with no operator control.

## 4. legal grounding -- Spanish autonomo retention

### 4.1. retention obligation

- **Ley 58/2003, General Tributaria, Art. 29.2.d-e** (BOE num. 302, 18 dic 2003) imposes on every obligado tributario the duty to keep books, registries, invoices, supporting documents, and any other accounting and tax records. Combined with **Art. 66 LGT** (the 4-year prescription period for tax liabilities), the operational floor is conservation for at least 4 years from the end of the voluntary-filing window.
- **Real Decreto 1619/2012** (reglamento de facturacion, BOE num. 289, 1 dic 2012) Art. 19-20 requires invoices and their electronic equivalents to be preserved in their original form guaranteeing legibility, integrity (no unauthorised modification), and accessibility for AEAT inspection throughout the retention period.
- **Codigo de Comercio Art. 30** raises the retention floor to 6 years for accounting records (libros, correspondencia, documentacion, justificantes).

### 4.2. AEAT-side canonical copies

- AEAT operates **Mis expedientes** and **Mis notificaciones** under Sede Electronica. Every electronically-filed declaration produces a justificante (CSV code, NRC for payments) that AEAT preserves on its side and the taxpayer can re-download via the Sede `[unverified -- specific durations not located in this pass]`.
- **CSV (Codigo Seguro de Verificacion)** -- under **Ley 39/2015 Art. 27.3** and **Ley 40/2015 Art. 42** (BOE num. 236, 2 oct 2015 for both), AEAT-emitted electronic documents bear a CSV that permits later re-verification on the Sede. The CSV anchors the AEAT-side audit trail.
- **Ley 6/2020 de servicios electronicos de confianza** (BOE num. 159, 6 jun 2020) implements eIDAS Regulation (EU) 910/2014 for the Spanish jurisdiction. Long-term preservation of qualified electronic signatures (LTV / AdES variants) is a regulated service -- taxpayers are NOT individually obligated to operate a qualified preservation service, but they are obligated to keep legible, integral, accessible copies (per RD 1619/2012).

### 4.3. legal exposure of local-loss

If the operator loses the local Secure-backend records but AEAT holds the canonical filed-declaration data on the Sede side:

- The **canonical filed return is recoverable** from Mis expedientes -- the taxpayer can re-download justificantes for every Modelo submitted electronically `[unverified -- extent of historical depth on Sede not located in this pass]`. This materially limits legal exposure: the AEAT record is the dispositive one for liability purposes.
- **What is NOT recoverable from AEAT** and IS legally required to be preserved by the operator (per LGT Art. 29 + RD 1619/2012):
  - Pre-filing supporting documents (invoices issued and received, bank statements, contracts, receipts).
  - Working calculations and intermediate ledgers that justify the declared amounts on audit.
  - Evidence of timely payment (NRC + bank confirmation) for the period of prescription.
  - Internal correspondence linked to operations (Codigo de Comercio Art. 30).
- The Secure backend may hold any of: justificantes (recoverable from AEAT), invoices (NOT recoverable from AEAT -- fully on the operator), ledgers (NOT recoverable), payment evidence (partially recoverable from AEAT via NRC lookup + bank).

**Conclusion**: framing local-loss as AEAT-portal-is-your-backup is partially true for filed-declaration metadata, materially false for supporting documents, and unsafe to use as the primary no-recovery argument in operator-facing UX. The operator legal exposure for lost supporting documents under an inspection is real (LGT Art. 203 -- infracciones por resistencia, obstruccion, excusa o negativa; sanctions for unjustifiable absence of required records).

### 4.4. RGPD overlap

The Secure backend additionally holds personal-data fields (operator NIF, name, address, possibly third-party NIFs in invoices). Under **Reglamento (UE) 2016/679 (RGPD)** Art. 32 (security of processing) the controller (the operator, when self-hosting; the app vendor if SaaS) must implement appropriate technical measures including pseudonymisation and encryption of personal data and ensure ongoing confidentiality. The co-location anti-pattern weakens the appropriate-measures defence in an Art. 33 / 34 breach-notification scenario.

## 5. profile bucket vault model -- the second ADR

This research informs two ADRs in the same sequence. ADR-1 covers
master-passkey custody, enrolment, and recovery (sections 2-4 plus
sub-sections 6.1-6.8). ADR-2 covers the **profile bucket vault
lifecycle** -- how multiple encrypted workspaces co-exist on one
operator install, how the active one is selected, how switching
works, and how isolation between buckets is enforced. Both ADRs
share this research file because the custody and lifecycle
decisions are deeply entangled: a per-bucket key schedule is
meaningless without correct switching semantics, and a switching
surface is unsafe without per-bucket key custody.

### 5.0. terminology convention adopted by this research

Per the operator mandate, this research adopts the following
canonical terms and the rest of the file SHALL use them
consistently:

- **Profile** -- the user-facing identity. A `profile_id` selects
  one declarant context (a NIF, an activity, an IVA regime,
  language preferences). One operator may have several profiles
  (autonomo + business, current year + amendment year, real +
  dry-run).
- **Bucket** -- the encrypted storage slice that holds every
  record associated with one profile. A bucket has its own key
  material (target state) and its own append-only event history.
  Today the codebase uses `bucket_id` consistently in code (see
  audit below).
- **Vault** -- a prose synonym for bucket, used where natural in
  operator-facing copy. The Google Drive mirror folder is also
  called `aeat-vault/` in the existing adapter
  (`_google_drive.py:48`); the collision is unintentional and
  ADR-2 should rename one or the other to avoid operator
  confusion.

The terminology is NOT consistently rolled out in user-facing
strings today: the locale catalogues mix bucket (commonly), vault
(in the Drive-mirror context only), and bare profile (when
referring to storage slices that are really buckets).
Standardisation is itself a deliverable of ADR-2.

### 5.1. codebase audit of the current profile bucket reality

#### 5.1.1. cardinality and binding

The relationship between profile and bucket is **1:1 and
trivially so**: at registration time, the same string is used as
both the `profile_id` and the `bucket_id`. Evidence:

- `src/aeat/application/setup/_service.py:30-54` -- the
  `initialize_workspace` service passes `command.profile_name`
  as both `profile_id` and `bucket_id` in the
  `InitializeWorkspaceResult` it returns.
- `src/aeat/application/user_profile/_orchestration.py:98` --
  `register_active_profile` constructs
  `ProfileBucketPointer(bucket_id=profile_id)`. Same string, no
  derivation, no namespacing, no slug-vs-display-name
  distinction.
- `src/aeat/application/wizard/_persistence.py:88-101` -- the
  wizard reuses `profile_name` as the bucket pointer key the
  same way.
- `src/aeat/application/workflow/_models.py:104-117` -- the
  `ProfileBucketPointer` pydantic record carries **only** a
  `bucket_id` field (1..128 chars). No vault metadata, no key
  reference, no on-disk path, no created-at, no KDF parameters,
  no passphrase hint, no recovery-enrolment flag. The pointer
  is effectively a renamed string.

Implication: there is no formal data model for a bucket as such.
Every bucket today is a virtual partition keyed by the
`bucket_id` column on the shared `secure_objects` table
(`src/aeat/adapters/persistence/storage/sql/secure_objects.py`),
and the bucket scope on the outbound storage provider's
directory tree (`var/storage/<profile>/`, see `_factory.py:157`).

#### 5.1.2. how the active profile is selected at process start

There are **three** independent definitions of the current
profile in the codebase, and they do not all agree:

- **Workflow-state active_profile**
  (`workflow/_models.py:147`) -- the canonical operator
  selection, persisted in the encrypted workflow state envelope.
  Set by `register_active_profile` / `select_profile`
  (`user_profile/_orchestration.py:72-124`) and by the CLI
  `aeat config profile use NAME` verb
  (`_config/__init__.py:471-491`).
- **Google adapter `resolve_active_profile`**
  (`adapters/outbound/google/_profile_binding.py:22-55`) -- reads
  the workflow state's active_profile, but accepts an override
  via the CLI's `--profile` flag. Used by every
  `aeat config google ...` command and by the outbound storage
  factory (`_factory.py:100-103, 154`). When `--profile` is
  given it wins, **without re-loading the bucket pointer or the
  master key**: the application keeps talking to the
  workflow-state-active bucket for everything else, but talks to
  the override bucket for Drive operations only. This is a
  partial-switch surface.
- **`Settings.aeat_default_profile_name`** -- a settings-level
  string used to name auth-acquisition lockfiles
  (`auth/_acquisition_lock.py:43-160`, `auth/_sessions.py:94`)
  and storage-state filenames. Not co-located with the
  workflow-state active_profile. A process can run with
  active_profile=business while holding auth locks under
  `operator-cert-auth.lock` if `aeat_default_profile_name` is
  the default. This is a cross-profile leak surface during auth
  acquisition.

There is no env var like `AEAT_PROFILE` or `AEAT_ACTIVE_BUCKET`
that selects the bucket at process start; the workflow-state
file is the only source of truth, and CLI `--profile` overrides
are partial.

#### 5.1.3. what changes when a user switches profile -- runtime trace

`select_profile` (`user_profile/_orchestration.py:104-123`)
executes the following on `aeat config profile use NAME`:

- Loads the lifecycle service for the new bucket
  (`build_lifecycle_service(bucket_id=profile_id)`) -- this opens
  an encrypted session against the **same** `var/aeat.db`, keyed
  on `bucket_id=NAME` for filtering. The DB connection is the
  same, the master key is the same, the open SQLAlchemy engine
  is the same.
- Calls `service.read(profile_id)` to confirm the target profile
  exists; this materialises ciphertext through the master-key
  cache.
- Rewrites `WorkflowState.active_profile` and appends a
  `profile.selected` workflow event.
- Returns.

What does **NOT** happen on switch:

- The master key is **not** invalidated, not zeroised, not
  reloaded. `FileFallbackMasterKeyProvider._cached_master_key`
  is a ClassVar dict (`_master_key.py:475`) shared across every
  bucket in the process. Switching profile leaves the cached
  master key bytes pinned to the prior bucket's KEK derivation
  and shared with the new bucket. Today this works only because
  every bucket uses the SAME master key -- there is no
  per-bucket key material.
- The SQLAlchemy engine is not closed; the encrypted connection
  pool is not flushed.
- Open file handles in the outbound storage adapter (under
  `var/storage/<old-profile>/`) are not closed before the new
  adapter at `var/storage/<new-profile>/` is built; the factory
  is invoked lazily per call site (`_factory.py:128`) and there
  is no central registry of open providers.
- The Google adapter token cache, the workflow-event history
  cursor, the in-process deadlines cache, and any
  application-layer memoisation all survive the switch
  unchanged.
- There is no audit event emitted to the **previous** bucket
  acknowledging the switch; only the new bucket and the
  WorkflowState see a `profile.selected` event.

In short: profile switching today is a label change on a single
shared cryptographic surface, not a vault switch.

#### 5.1.4. class-level singletons that survive a profile switch

Confirmed shared state across switches:

- `KeyringMasterKeyProvider._cache` -- ClassVar dict keyed by
  `(service, username)`, `_master_key.py:348-349`. Service and
  username are module-level constants, so this cache holds the
  one master key for the whole process lifetime. Cleared only
  by `_reset_for_tests` (line 456) and the atexit hook
  (`_purge_caches_at_exit`, lines 794-805).
- `FileFallbackMasterKeyProvider._cached_passphrase` and
  `_cached_master_key` -- ClassVar, `_master_key.py:474-475`,
  same lifetime semantics.
- The SQLAlchemy engine module-level singleton in
  `adapters/persistence/storage/sql/_engine.py` (per
  `get_engine` referenced from `sql/secure_objects.py:149`);
  reused across all buckets.
- The outbound storage providers built by `get_storage_provider`
  (`_factory.py:128`) are not cached at module level but the
  per-call build pattern means callers that hold a reference
  past a switch keep operating against the old bucket's root.
  `_local.py` `LocalFileSystemProvider` holds an absolute `root`
  path captured at construction.

#### 5.1.5. is there any code path that attempts to switch?

Yes:

- `aeat config profile use NAME` -- CLI verb at
  `_config/__init__.py:471-491`. Calls
  `select_profile(current, profile_id=name)`. The only
  user-facing switch verb. There is no
  `aeat config profile lock` or `aeat config profile unlock`.
- `aeat config profile remove NAME` --
  `_config/__init__.py:534`. Tombstones the active profile and
  resets active_profile to None; the bucket directory and DB
  rows are retained for audit history per
  `_orchestration.py:166-184`.
- `aeat config profile duplicate SOURCE TARGET` --
  `_config/__init__.py:568`. Copies one profile's facts into a
  new profile id; both end up sharing the SAME `var/aeat.db`
  and the SAME master key.
- Implicit overrides via the Google adapter `--profile` flag,
  documented above. Partial; does not switch the encrypted
  substrate.

There is no `aeat config profile new` verb (creation is folded
into `aeat config init`), and no `profile export` /
`profile import` / `profile lock` / `profile unlock` surface.

#### 5.1.6. on-disk isolation between buckets

**Interleaved.** Every bucket's records share:

- One SQLite DB: `var/aeat.db` (`core/config.py:166-168`).
  Partitioning is by the `bucket_id` column on the
  `secure_objects` table; ciphertext rows from every bucket sit
  in the same physical file.
- One blob store: `var/blobs/` (`core/config.py:205-208`).
- One audit sink: `var/audit/` (`core/config.py:209-212`).
- One secret store: `var/secrets/` (`core/config.py:201-204`)
  with one global `master.key`, one global `master.kdf`, one
  global `salt`. No per-bucket subdirectory exists.

The outbound storage adapter is the **only** subsystem that
isolates per-profile content on disk: `_factory.py:157` composes
`root = settings_resolved.aeat_local_storage_root / profile`,
so `var/storage/business/` and `var/storage/personal/` are
separate directory trees. This isolation is
**plaintext-directory-only**; the encrypted-substrate
subsystems are interleaved.

Implication: a single stolen `var/` directory plus one
passphrase yields plaintext for **every** profile on that
install. There is no defence-in-depth against cross-bucket
access once any bucket is unlocked.

#### 5.1.7. does the secret-store backend namespace by profile?

**No.** Both providers in
`src/aeat/adapters/persistence/storage/master_key/_master_key.py`
operate on global addresses:

- `KeyringMasterKeyProvider` -- service and username are
  module-level constants (lines 80-84) resolving to the fixed
  pair aeat:secure-persistence / master. One key for the whole
  install, regardless of how many profiles exist.
- `FileFallbackMasterKeyProvider` -- writes to
  `aeat_secret_store_dir/master.key`, `master.kdf`, `salt`
  (lines 504-506, 624-655). One set of files for the whole
  install.

There is no per-bucket KEK derivation, no per-bucket salt, no
per-bucket recovery wrap, no per-bucket OS-keystore entry.

#### 5.1.8. Google adapter profile bindings under switching

`adapters/outbound/google/_profile_binding.py:22-55` exposes
`resolve_active_profile(profile_override)`. Every read in
`_session_store.py` (the OAuth-client / OAuth-token /
Drive-config store) is keyed on the resolved profile name
(`_session_store.py:16`). The Drive-side records ARE
per-profile-namespaced -- different profiles can hold different
OAuth clients, tokens, and Drive folder IDs. This is the one
adapter that gets per-bucket isolation right at the **logical**
level.

However: those per-profile records are themselves stored in the
shared encrypted `secure_objects` table under the shared master
key. A `var/aeat.db` exfil yields every profile's Drive refresh
token under one master key.

Switch-correctness verdict: the Google adapter survives a
profile switch correctly **for record selection** (the right
token is loaded for the right profile), but **incorrectly under
isolation** (all tokens unlock with one master key). It also
exhibits the partial-switch property under `--profile`
overrides described in 5.1.2.

#### 5.1.9. test fixtures and integration tests exercising multi-profile

Searched for tests that create more than one profile in the same
process:

- `application/workflow/test_transaction_catalogue_resolution.py:75-90`
  -- the one test that explicitly exercises two profiles in
  sequence (bucket-alpha, then bucket-beta), verifying that
  `active_transaction_catalogue_repository` re-resolves to the
  correct bucket after a state mutation. Confirms switching at
  the application-router level is wired; does NOT exercise key
  invalidation or storage-handle teardown.
- `application/evidence/test_evidence.py:257-271` -- builds two
  evidence bundles under bucket-A and bucket-B in one test and
  verifies that show with bucket-B but bundle from bucket-A
  refuses. This is a cross-bucket leak-prevention test at the
  service surface, not a key-isolation test.
- `entrypoints/cli/test_profile_lifecycle_verbs.py` -- exercises
  `profile use`, `profile remove`, `profile duplicate`,
  `profile validate`, `profile preflight`. None of these tests
  assert anything about master-key cache state across a switch.

Finding in itself: there is **no test** that asserts the master
key is rotated, the cache is invalidated, an OS-keystore entry
is per-bucket, or an open file handle is closed across a profile
switch. The class-level cache pattern in
`_master_key.py:348, 474-475` would silently regress against
any future per-bucket key schedule without a single failing test.

### 5.2. industry comparables for multi-workspace switching

How comparable tools model multiple isolated encrypted workspaces
on one install:

- **1Password vaults** -- multiple vaults per account, each with
  its own access list and item set. Unlock is **per account**,
  not per vault: once the user is signed in, every vault they
  have access to becomes readable; the per-vault access list is
  a permissions concern, not a cryptographic one. Switching
  account forces full re-authentication.
- **Bitwarden organisations** -- the personal vault and each
  organisation vault have **separate symmetric keys**, all
  wrapped under the user's master key. Adding an org-member to
  a vault requires re-wrapping the org key under that member's
  public key. Each vault is cryptographically distinct.
- **KeePassXC** -- one `.kdbx` file per database, each with its
  **own** master password and optional key file. Switching is
  literally opening another file via the file menu; the
  previous database remains open in another tab and must be
  locked explicitly. UX has a first-class Lock-all-databases
  action.
- **Cryptomator** -- one **vault directory** per vault, each
  with its own `masterkey.cryptomator` file holding the wrapped
  key. Each vault has its own passphrase. The vault list lives
  in Cryptomator's own preference file (paths + display names +
  IDs); the contents of any vault require unlock. Explicit
  per-vault lock + unlock; vaults can be selectively kept
  unlocked.
- **VeraCrypt** -- one volume per file. Mount = unlock + assign
  drive letter + read-write the underlying filesystem.
  Dismount = lock + zeroise cached key + release the drive
  letter. Multiple volumes can be mounted concurrently; each is
  cryptographically and operationally distinct.
- **age / rage** -- recipient-file-based; each identity is its
  own keypair. Multi-identity workflows pass
  `-i id1.txt -i id2.txt` and the tool tries every identity
  against every recipient stanza. No central active identity --
  composition is per invocation.
- **Borg / restic** -- multiple repositories per install, each
  with its own key material (Borg keyfile or repokey mode;
  restic `keys/<id>` JSON files). Selection is **per command**
  via `--repo <path>` or `BORG_REPO` / `RESTIC_REPOSITORY` env
  var. There is no persistent active-repo concept; every
  invocation re-binds.
- **aws-vault** -- profile namespacing on top of the AWS CLI
  config; each profile has its own credentials stored in the
  OS keyring under a distinct keyring entry. Selection is
  `aws-vault exec PROFILE -- <cmd>`. Switching is a fresh exec;
  no in-process switch.
- **pass** -- one password-store directory; multi-store is
  achieved by setting `PASSWORD_STORE_DIR` per command. No
  in-process switch surface.
- **Browser profiles (Chrome, Firefox)** -- process-level
  isolation. Each profile runs in its own browser process tree
  with its own cookie jar, its own credential store, its own
  OS-keyring entry namespace. Switching profile = launching a
  different process. No in-process switch.

#### 5.2.1. invariants for safe multi-workspace systems

Distilling the survey:

- **Each bucket has its own key material.** Never a single
  process-global master key under which every bucket is filtered
  by an id column. Either each bucket has its own
  passphrase-derived KEK, or each bucket has its own DEK wrapped
  under the user's account key.
- **Switching buckets requires explicit teardown.** Close all
  open handles to the previous bucket's storage. Zeroise the
  previous bucket's master key in memory. Re-derive / re-unwrap
  the new bucket's key on demand. Tools that take this seriously
  expose **lock** as a first-class verb (KeePassXC, Cryptomator,
  VeraCrypt dismount).
- **The active bucket is process-level state.** It is read once
  on process start (env var, CLI flag, or persisted pointer),
  and any in-process switch is performed by tearing down and
  re-initialising the cryptographic surface, not by editing a
  label and reusing the same key.
- **List buckets without unlocking them.** The bucket index
  (names, IDs, KDF params, last-unlocked-at,
  recovery-enrolment flag) is plaintext metadata -- distinct
  from the encrypted contents. The user can choose which bucket
  to unlock without first proving they can read any other.
- **Locking is a first-class operation.** `vault lock`,
  `cryptomator lock`, `keepassxc-cli db-close`, `aws-vault
  clear`, gpg-agent reloadagent. Long-running processes do not
  pin cleartext key material indefinitely.
- **Concurrent access is prevented or serialised.** A bucket is
  either single-writer (file lock; Borg / restic use repository
  lock files), or multi-writer with conflict resolution
  (Bitwarden server-mediated). The naive co-location pattern
  (two processes both holding the same SQLite DB writable open)
  is avoided.

### 5.3. threat model expansion for multi-bucket

New attack surfaces introduced by multi-bucket support, on top of
the single-bucket threat model in section 1:

- **Cross-bucket leak via shared caches.** A process holds the
  master key for bucket A in a ClassVar cache; the operator
  switches to bucket B; the cache survives; an application bug
  reads `bucket_id=A` records under the active session. Today:
  structurally possible, prevented only by application code
  uniformly passing `bucket_id` through every query.
- **Wrong-bucket writes after a partial switch.** Application
  routes to bucket B for one verb but to bucket A for another
  in the same process (the `--profile` override partial-switch
  pattern is exactly this). Audit events are written to the
  wrong append-only log.
- **Locked-bucket metadata leakage.** Even with a future
  per-bucket key schedule, filenames / directory names / file
  sizes / modtimes leak which buckets exist, when they were
  last modified, and how much content they hold. The
  Cryptomator threat model accepts this leak; the VeraCrypt
  hidden-volume model defends against it. ADR-2 must pick.
- **Default-profile silent fallback masking a failed switch.**
  If `aeat config profile use NAME` fails halfway (e.g., the
  new bucket's master key cannot be derived), does the process
  silently keep operating against the previous bucket, or does
  it refuse to proceed? Today: silent fallback is the
  structural default (no key invalidation = no failure
  surface).
- **Backup tooling captures all buckets but only one
  passphrase.** An operator who exports `var/` to off-site
  backup transmits every bucket's ciphertext but only one
  passphrase guards them. The cross-bucket compromise model is
  one-passphrase-breaks-all.
- **Tombstone records cross-leak.** Per
  `_orchestration.py:172-184`, removing a profile retains the
  bucket pointer in `WorkflowState.profiles` (only
  active_profile is cleared). A future `profile_id` reuse
  against the same `bucket_id` string would collide; reuse is
  silently dangerous.
- **Bucket-id collision via duplicate.** `profile duplicate`
  creates a new bucket with a new id; the source bucket's
  ciphertext is **read** through the same master key, then
  **re-written** under the same master key with a new
  `bucket_id` filter. There is no cryptographic isolation
  between source and target.
- **`aeat_default_profile_name` desync.** The auth subsystem
  acquires locks under `Settings.aeat_default_profile_name`,
  not under `WorkflowState.active_profile`. A switched profile
  whose default-name setting was not also updated will write
  auth artefacts to the prior profile's lockfile namespace.


## 6. design implications -- what the ADRs must decide

The defect is real, the fix touches the user first contact with the product, and the substrate already ships half the cryptography needed. Two ADRs are required, sharing this research base. ADR-1 covers custody, enrolment, and passphrase UX (sub-sections 6.1-6.8). ADR-2 covers profile and bucket lifecycle (sub-section 6.9). The decision matrix in section 7 (options) and the open questions in section 8 are likewise split by target ADR.

### 6.1. custody model -- ADR-1

- **Option A: OS-keystore-primary, passphrase-secondary.** Default to `auto` (current behaviour), but make the resolved choice **visible to the operator** at enrolment, and require an Emergency-Kit-style recovery mnemonic regardless of which backend wins. Lose the OS account -> recover with mnemonic.
- **Option B: passphrase-primary, OS-keystore-cache.** Require a user-chosen passphrase up-front; cache the derived key in the OS keystore for friction-free re-unlock. Recovery is remember-your-passphrase plus an optional printable mnemonic. Closer to 1Password / Bitwarden model.
- **Option C: passphrase-only, no OS-keystore.** Drop `auto` and `keyring` backends from the default. Every interaction reads `AEAT_SECRET_PASSPHRASE` or prompts. Maximises portability, worsens daily UX (operator types passphrase every CLI invocation unless a session unlock is added).
- **Option D: hybrid quorum.** Vault-style -- N-of-M Shamir split across (passphrase, OS keystore, printed mnemonic). Engineering cost likely disproportionate for a single-user autonomo tool.

### 6.2. enrolment-flow shape -- ADR-1

Where does the prompt live? `aeat config init` is the natural anchor (per the wizard research one-command on-ramp mandate). Decisions:

- Inline at `aeat config init` (interactive only -- `--non-interactive` must error unless `AEAT_SECRET_PASSPHRASE` is set and an explicit `--accept-data-loss-risk` flag is supplied).
- Two-step: `aeat config init` writes the profile, prints a recovery mnemonic, requires `aeat config confirm-recovery <first-3-words>` to acknowledge the operator captured it (1Password-style confirm-by-retype).
- Wizard-driven via the existing `application/wizard` flow, with new catalogue entries for passphrase + recovery-acknowledgement steps.

### 6.3. key location -- ADR-1

The ADR MUST decide and codify that key material does not live under the same directory hierarchy as ciphertext. Candidate rules:

- **Rule K1**: when `auto` resolves to `keyring`, key lives in the OS keystore and `var/secrets/` does not exist.
- **Rule K2**: when `file` backend is used, default `aeat_secret_store_dir` to a path **outside** `PROJECT_ROOT`, e.g. `~/.config/aeat/secret-store/` on POSIX, `%LOCALAPPDATA%eat\secret-store\` on Windows. Refuse to start with `aeat_secret_store_dir` under the `aeat_database_url` parent.
- **Rule K3**: store the recovery-wrapped master key (`master.recovery.key`) printed-only and never persist it on the same disk by default. The operator may opt into on-disk recovery storage with an explicit flag and an acknowledgement.

### 6.4. recovery story -- ADR-1

- (R1) Print a 24-word BIP-39 mnemonic at enrolment (primitives exist per `_recovery.py:203-213`) and require the operator to retype 3 random words to confirm capture.
- (R2) Persist the recovery-wrapped master key (`save_wrapped_master_key`, `_recovery.py:273-285`) at an operator-supplied path that defaults OUTSIDE the project, OR refuse to persist it at all and force print-only.
- (R3) Add `aeat config recover --mnemonic <24 words>` that invokes `decode_mnemonic` -> `unwrap_master_key` -> `complete_recovery`.

### 6.5. lock / unlock semantics -- ADR-1

- Add a session-unlock concept (`aeat config unlock`, `aeat config lock`) backed by a short-lived ephemeral cache file in the OS-private temp dir.
- Bound the process-lifetime cache with a TTL.
- For long-running services (none currently exist), the seal / unseal pattern from Vault is the closest reference.

### 6.6. rotation and re-key -- ADR-1

- Wire the existing `_rotation.py` primitives behind `aeat config rotate-key` (cryptographic rotation under a fresh master key).
- Wire `FileFallbackMasterKeyProvider.complete_recovery` behind `aeat config rekey` (re-wrap the master key under a new passphrase without rotating ciphertext).

### 6.7. CLI surface -- ADR-1

A minimal verb set the ADR should converge on:

- `aeat config init` -- enrols a profile, prompts passphrase or selects OS keystore, displays recovery mnemonic with confirm-by-retype.
- `aeat config unlock` / `aeat config lock` -- session boundary.
- `aeat config rekey` -- re-wrap under new passphrase.
- `aeat config rotate-key` -- rotate the actual master key + re-encrypt ciphertext.
- `aeat config recover --mnemonic <24 words>` -- recovery path.
- `aeat config export-recovery` -- re-display or re-print the recovery mnemonic for an existing profile after operator reauthentication.
- `aeat config repair quarantine` -- already exists; keep.

Each of these must be reflected in the locale catalogues (es / en / ca) per the i18n mandate.

### 6.8. migration -- ADR-1

The user-base is small (single autonomo dev environment per the project north-star); a clean-cut wipe-and-re-enrol path is the honest answer. No backwards-compat shims (per `no_backwards_compat_no_deprecation`). The ADR should specify what happens to currently-installed profiles whose master keys were silently auto-minted: the operator runs `aeat config init --re-enrol`, the substrate decrypts existing records under the silently-minted key, re-enrols the operator through the new passphrase-and-mnemonic flow, re-wraps the master key under the new KEK, and prints the mnemonic. The decision of whether to keep the silently-minted key bytes (and re-wrap them) versus rotating to a fresh random key is itself a sub-decision for the ADR -- the former is faster and avoids re-encrypting every record; the latter is cleaner from an audit posture (no key bytes generated under the silent regime survive).

### 6.9. bucket-lifecycle decisions -- ADR-2

#### 6.9.1. cardinality and namespacing

- Is the canonical relation 1 install -> N profiles -> 1 bucket
  each (today's implicit model), N profiles -> N buckets with
  potential many-to-many sharing (Bitwarden organisations), or
  strictly 1 install -> 1 bucket -> 1 profile (KeePassXC-style,
  multi-install instead of multi-bucket)? The audit in 5.1
  documents today as 1:1, but the data model already allows N
  profiles per `WorkflowState`.
- Is the `profile_id` identical to the `bucket_id` (today's
  reality), or must they be decoupled (UUID-keyed bucket
  directory with a separate user-chosen profile slug)?
  Decoupling enables rename without ciphertext re-encryption
  and removes the collision-on-reuse hazard.
- Are bucket IDs globally unique across the install (current
  invariant: yes, because `dict[str, ProfileBucketPointer]`
  enforces uniqueness), or only per-process? The cross-machine
  import use case demands a UUID-style identifier.

#### 6.9.2. on-disk layout

- One bucket per directory: `~/.aeat/buckets/<bucket-id>/`
  containing `db.sqlite`, `blobs/`, `audit/`, `master.key`,
  `master.kdf`, `salt`, `manifest.json`. Per-bucket directory
  isolation is the Cryptomator / Borg-keyfile pattern.
- Or interleaved-with-column (current): one `var/aeat.db` for
  everything, partitioned by `bucket_id` column. Current
  pattern; demonstrated to interleave ciphertext rows for all
  buckets under one key.
- Or hybrid: separate ciphertext DB per bucket, single index DB
  for the bucket-list metadata (the Cryptomator model with an
  index file).

The ADR must choose. Per-bucket directory isolation is the only
option that achieves operator-comprehensible isolation (delete
this folder = delete that profile entirely) and
backup-tooling-friendly per-bucket export.

#### 6.9.3. bucket discovery without unlocking

- A plaintext bucket index (`~/.aeat/buckets/index.json` or
  similar) listing every bucket's `bucket_id`, display name,
  created-at, last-unlocked-at, KDF params, recovery-enrolment
  flag. NEVER the salt, the wrapped key, or the master key.
  The list must be readable without unlocking ANY bucket so the
  operator can choose which to unlock.
- Or: enumerate directories under `~/.aeat/buckets/` and read
  each bucket's plaintext `manifest.json` sidecar. Same effect,
  no central index file.
- The current codebase has no list-buckets surface; every read
  goes through the master-key cache. ADR-2 must add a
  `aeat config bucket list` verb that talks to the index only.

#### 6.9.4. active-bucket selection precedence

Define the precedence chain explicitly:

- `--bucket BUCKET_ID` CLI flag (per-invocation; overrides
  everything; never persisted).
- `AEAT_ACTIVE_BUCKET` env var (per-shell; overrides the
  persisted pointer; useful for headless CI).
- Persisted pointer in `~/.aeat/config.toml` (canonical default
  for interactive sessions; written by
  `aeat config profile use`).
- If none of the above resolves, refuse to proceed with a typed
  error (`NoActiveBucketError`) that suggests
  `aeat config bucket list` and `aeat config bucket use`.

The current Google adapter `--profile` override is a partial
implementation of step 1 for one subsystem only. ADR-2 must
unify the override into a single CLI-level option that switches
the ENTIRE process, not one adapter.

#### 6.9.5. switching semantics

The switch verb (`aeat config bucket use NAME`) must, in order:

- Refuse if there are uncommitted writes on the current bucket
  (open SQLAlchemy session in-progress, pending file uploads on
  the storage adapter, in-flight workflow run). Surfaced as a
  typed error with a `--force-discard` opt-out.
- Lock the current bucket: zeroise the in-memory master key,
  close every open SQLAlchemy connection, close the storage
  adapter file handles, evict the application-layer caches.
- Read the new bucket's KDF params from its plaintext manifest.
- Prompt for the new bucket's passphrase (or load it from the
  OS keystore entry for that specific bucket).
- Derive the new bucket's KEK and unwrap its master key.
- Open new connections / adapters scoped to the new bucket.
- Write `bucket.switched` event to the previous bucket's audit
  log AND `bucket.activated` to the new bucket's audit log.

Silent switch (current behaviour) is forbidden by this design.

#### 6.9.6. cache invalidation on switch

The class-level master-key cache pattern in
`_master_key.py:348, 474-475` is incompatible with multi-bucket.
ADR-2 must specify either:

- Instance-level caches scoped to a `BucketSession` object that
  is constructed at unlock and destroyed at lock. The current
  `MasterKeyProvider` protocol becomes a per-session factory.
- Or a ClassVar keyed by `bucket_id` plus an explicit
  `evict(bucket_id)` method called at lock; ClassVar entries
  are zeroised in place.

Independent of choice, every cache layer (the SQLAlchemy engine,
the storage-adapter providers, the deadlines cache, the Google
session-store cache) must register an eviction callback that
fires on `bucket_lock(bucket_id)`.

#### 6.9.7. per-bucket plaintext manifest

Each bucket has a `manifest.json` sidecar at
`<bucket-dir>/manifest.json` containing **only non-sensitive
metadata**:

- `bucket_id` (UUID).
- `display_name` (operator-chosen label).
- `created_at`, `last_unlocked_at` (UTC).
- KDF identifier (`argon2id`), `memory_cost`, `time_cost`,
  `parallelism`, `version`. NEVER the salt; the salt lives next
  to the wrapped key.
- `recovery_enrolled: bool` (whether `master.recovery.key`
  exists for this bucket).
- `schema_version` to support future bucket-format migrations.

The manifest is readable without unlock; tampering is detectable
on next unlock because the unlock fails if KDF params do not
match the wrapped-key envelope's recorded params.

#### 6.9.8. per-bucket vs shared passphrase

ADR-2 must mandate: passphrases are **per-bucket**. Sharing one
passphrase across buckets converts multi-bucket into
multi-namespace-under-one-key (today's defect). A single shared
passphrase is permitted only as a UX convenience the operator
may opt into explicitly, with a stated warning that the
cross-bucket compromise model is one-passphrase-breaks-all.

#### 6.9.9. per-bucket recovery code

Each bucket has its own BIP-39 mnemonic. Cross-bucket recovery
codes are forbidden -- the mnemonic that recovers bucket A must
not unwrap bucket B's key. ADR-1's recovery design (section
6.4) must extend the `_recovery.py` primitives to a per-bucket
key material schedule.

#### 6.9.10. bucket deletion

`aeat config bucket delete BUCKET_ID` -- explicit verb,
double-confirm (`--yes` plus retype of the bucket display name).
Removes the bucket directory entirely after a final audit-export
to `~/.aeat/deleted-bucket-<id>-<ts>/audit.jsonl` to preserve
legal-grounding compliance under LGT Art. 29 (the operator can
still produce a record of what existed and when).

Today's `profile remove` (tombstones the record but retains the
ciphertext rows under the same master key) is NOT bucket
deletion; ADR-2 must rename and separate the two verbs.

#### 6.9.11. bucket export / import for migration

`aeat config bucket export BUCKET_ID --to <path>` produces a
sealed bundle containing the bucket's directory tree (ciphertext
only) plus the bucket's plaintext manifest. The operator
transports this bundle to a new machine and runs
`aeat config bucket import <path>` which extracts under
`~/.aeat/buckets/<bucket-id>/`. The new install must prompt for
the bucket's passphrase before any unlock attempt; the
passphrase itself NEVER travels in the bundle.

This is the operator-portable analogue of the Cryptomator
copy-the-vault-directory workflow.

#### 6.9.12. concurrency -- process-level file lock per bucket

Today's `var/aeat.db` is one SQLite file shared by every bucket;
SQLite's locking is per-file, not per-bucket. With per-bucket
directories, each bucket gets its own `lock` file
(`~/.aeat/buckets/<id>/.lock`) acquired on unlock and released
on lock. Concurrent `aeat ...` invocations against the same
bucket serialise; against different buckets they parallelise.
Lock contention surfaces a typed `BucketBusyError` with a
`--wait <seconds>` opt-in.

#### 6.9.13. terminology rollout

ADR-2 must specify the locale-catalogue rewrite that
standardises bucket everywhere user-facing strings refer to
encrypted storage slices, and resolves the `aeat-vault/` Drive
folder collision (either rename the Drive folder or restrict
vault to a prose synonym never used as a structural noun).

#### 6.9.14. interaction with aeat_default_profile_name

The `Settings.aeat_default_profile_name` setting
(`auth/_acquisition_lock.py:43-160`) is a vestigial concept that
parallel-defines the profile for the auth subsystem. ADR-2 must
eliminate it (the auth lockfile namespace becomes the active
bucket id) or formalise its precedence relative to the
WorkflowState pointer.


## 7. options surfaced

ADR-1 (custody + enrolment + passphrase UX) selects from Options A.I, A.II, A.III. ADR-2 (profile/bucket lifecycle) selects from Options B.1, B.2, B.3. None is recommended here -- selection is the ADR phase job.

### 7.1. Option A.I -- 1Password-like: passphrase mandatory + mnemonic recovery

- Custody: operator-chosen passphrase, Argon2id KEK, AES-256-GCM wraps the master key. OS keystore caches the derived key with a short TTL for friction-free re-unlock; cleared by `aeat config lock` and by idle-timeout.
- Enrolment UX: `aeat config init` prompts twice for passphrase (confirm), prints a 24-word BIP-39 mnemonic, requires the operator to retype words at three random positions before the profile is marked usable. The screen contains the verbatim sentence: if you lose both your passphrase and this recovery code, every record in this profile will be permanently unreadable.
- Recovery: `aeat config recover --mnemonic` unwraps the master key and re-wraps under a new passphrase. The on-disk wrapped recovery file (`master.recovery.key`) is optional; operator may opt in with `--persist-recovery-wrap` and acknowledge co-location risk.
- Locking: `aeat config lock`, `aeat config unlock`, idle TTL on the process cache.
- Trade-offs: highest UX friction, highest safety, mirrors industry reference designs. Requires a TTY-only init path or an explicit non-interactive escape hatch.

### 7.2. Option A.II -- Keychain-primary: OS-keystore default + mandatory printed mnemonic

- Custody: OS keystore is the primary key home (status quo for `auto` mode that lands on `keyring`); the file backend is reserved for headless / CI. No silent fallback -- if the keystore is unavailable, the operator is asked to either retry or explicitly pick the file backend with an interactive passphrase.
- Enrolment UX: `aeat config init` discloses which backend was chosen in plain language, then prints a 24-word mnemonic that wraps the OS-keystored key for cross-machine portability AND loss-of-OS-account recovery. Retype confirmation required.
- Recovery: mnemonic-only. The wrapped recovery key is never persisted on disk by default.
- Locking: relies on OS-keystore lock semantics (Touch ID / Windows Hello prompts).
- Trade-offs: low daily friction, depends on per-OS keystore reliability, leaves headless deployments to a separate explicit configuration step. Loses portability between machines unless the operator runs `aeat config recover` on the new machine with the mnemonic.

### 7.3. Option A.III -- Borg-keyfile-like: explicit key-file path + passphrase

- Custody: operator chooses, at enrolment, where the passphrase-wrapped key file lives (`--key-file PATH`). The substrate refuses to default the path inside `PROJECT_ROOT`. The passphrase wraps the on-file key.
- Enrolment UX: `aeat config init` prompts for `--key-file` location with sensible cross-platform defaults (`~/.config/aeat/secret-store/` etc.). Prompts for passphrase. Prints recovery mnemonic.
- Recovery: mnemonic OR a second `borg key add`-style alternate passphrase / key-file the operator can pre-provision.
- Locking: session unlock backed by a short-lived ephemeral cache.
- Trade-offs: maximal portability (key-file is a single tangible artefact the operator can back up themselves), highest operator-cognitive load, weakest zero-config story which conflicts with the wizard research mandate.

### 7.4. Option B.1 -- single-bucket simplicity (no multi-bucket in v1)

- Profile and bucket remain 1:1; only one bucket per install.
  Multi-profile UX disappears -- a second profile means a second
  install directory (`AEAT_HOME=...` env var per shell).
- Trade-offs: lowest engineering cost, eliminates every
  cross-bucket threat-model row by construction. Sacrifices the
  autonomo + business use case where the operator legitimately
  wants two profiles on one machine without juggling install
  directories.
- Switching cost: per-shell env var; no in-process switch.
- Recovery story: per-install; the ADR-1 design applies
  unchanged.
- Code-impact estimate: small -- collapses the `dict[str,
  ProfileBucketPointer]` to a single optional, removes
  `select_profile` / `profile duplicate` / `profile use`. Locale
  catalogues simplify.

### 7.5. Option B.2 -- multi-bucket directory model

- Each bucket is its own directory under
  `~/.aeat/buckets/<id>/` with its own `db.sqlite`, `blobs/`,
  `audit/`, `master.key`, `master.kdf`, `salt`,
  `manifest.json`. Active-bucket pointer lives in
  `~/.aeat/config.toml`. Each bucket has its own passphrase.
  Each bucket has its own OS-keystore entry under service
  aeat:secure-persistence and account `bucket:<id>`.
- Trade-offs: matches Cryptomator / Borg-keyfile reference
  design; delivers operator-comprehensible isolation; defeats
  the one-passphrase-breaks-all cross-bucket compromise.
  Engineering cost is the design and migration: split the
  SQLAlchemy engine registry per bucket, refactor
  `_master_key.py` cache, rewrite `_factory.py` directory
  composition.
- Switching cost: explicit `aeat config bucket lock` /
  `aeat config bucket use NAME` flow; teardown + re-init takes
  seconds, not milliseconds.
- Recovery story: per-bucket BIP-39 mnemonic; per-bucket
  recovery wrapped key (optional, opt-in).
- Code-impact estimate: medium-to-large -- touches every
  adapter that holds bucket-scoped state, the entire
  master-key module, the config schema, the wizard, and the
  locale catalogues.

### 7.6. Option B.3 -- multi-bucket with OS-keystore index

- Same as Option B.2, plus the bucket index itself (the
  `~/.aeat/buckets/index.json` plaintext list of bucket IDs +
  display names + KDF params) is stored in the OS keystore
  under service aeat:secure-persistence and account
  `bucket:index`. Defeats tamper-with-the-index attacks where
  an adversary edits the plaintext index to point a bucket
  label at someone else's wrapped key file.
- Trade-offs: closes a tamper surface that the Cryptomator
  reference does NOT close (Cryptomator vaults are
  filesystem-discoverable and the index is
  per-app-install preferences without tamper protection). Cost:
  every list-buckets call goes through the OS keystore;
  headless / CI scenarios where the keystore is unavailable
  need a fallback (filesystem scan with a typed warning).
- Switching cost: identical to B.2 plus one keystore read on
  `aeat config bucket list`.
- Recovery story: per-bucket BIP-39 mnemonic; index entries
  can also be regenerated by filesystem scan if the OS-keystore
  index is lost (the bucket directories themselves are
  self-describing via their manifests).
- Code-impact estimate: B.2 plus a thin keystore-index adapter.


## 8. open questions for the ADRs

The open questions split into two groups by target ADR. ADR-1 covers custody, enrolment, and passphrase UX. ADR-2 covers profile and bucket lifecycle.

### 8.1. ADR-1 open questions -- custody + enrolment + passphrase UX

- Is the `auto` backend acceptable at all going forward, given the silent fallback property?
- Must `aeat config init` be **interactive-only** unless an unambiguous opt-out flag is supplied? Should `--non-interactive` refuse to mint a master key without an explicit recovery-disposition flag?
- Where exactly is `aeat_secret_store_dir` allowed to point? Codified rule: must NOT be under the `aeat_database_url` parent? Must NOT be under `PROJECT_ROOT` by default?
- Is the on-disk persistence of `master.recovery.key` retained as a default, retained as an opt-in, or removed entirely?
- What is the session-unlock TTL -- fixed, configurable, off-by-default for parity with current behaviour?
- Does `aeat config rotate-key` (re-encrypt ciphertext under a fresh master) become an audit-trigger or a routine maintenance command?
- For currently-installed profiles, does re-enrolment rotate the key bytes or merely re-wrap the existing key under a new passphrase?
- Are the dead-letter error messages that point at the nonexistent `aeat security recover` / `aeat security provision` commands kept (after wiring) or renamed to the new verb set (`aeat config recover`, `aeat config init --re-enrol`)?
- How is the recovery mnemonic surfaced in the trilingual locale catalogue without creating a translation surface that itself leaks word-position information at error time? The current `decode_mnemonic` already reports failures by position-only; the locale strings should follow.
- Does the substrate refuse to operate when it detects `aeat_secret_store_dir` co-located with the database file, or only warn? `[design choice -- fail-closed vs operator-acknowledged]`
- For the unsecured backend (`AEAT_ALLOW_UNENCRYPTED=1`), is the enrolment flow allowed to skip recovery entirely (current NIF-canary already refuses real tax ids)? Confirm the enrolment-flow ADR keeps unsecured-mode users on a separate code path with no mnemonic surface.

### 8.2. ADR-2 open questions -- profile / bucket lifecycle

- Is the canonical cardinality 1 user -> N profiles -> 1 bucket
  each (1:1 chosen explicitly), 1 profile -> N buckets (one
  identity, multiple isolated stores -- the dry-run-versus-real
  use case), or N profiles -> N buckets with sharing semantics?
  Today's code happens to be 1:1 but does not say so
  contractually.
- Should `bucket_id` and `profile_id` remain identical strings
  (today's reality), or be decoupled (UUID-keyed bucket
  directory with a renameable profile slug)? Decoupling
  enables operator rename without ciphertext re-encryption.
- Where on disk do buckets live -- under `PROJECT_ROOT/var/`
  (today, co-located with the working tree), under
  `~/.aeat/buckets/` (XDG / per-user), or operator-chosen at
  `aeat config bucket new --at PATH`?
- Is the bucket-index file plaintext on disk (Option B.2), in
  the OS keystore (Option B.3), or both with
  cross-validation?
- What is the precedence chain for active bucket? Proposed:
  `--bucket` CLI flag > `AEAT_ACTIVE_BUCKET` env var > persisted
  pointer in `~/.aeat/config.toml`. Codify or refute.
- Does the switch verb require explicit lock-then-unlock, or is
  implicit-switch-with-prompt acceptable for the single-shell
  interactive case?
- Must the switch fail closed when the in-process master-key
  cache cannot be zeroised (e.g., because a background thread
  is mid-write to the previous bucket)?
- For currently-installed profiles that share one
  `var/aeat.db`, what is the migration path to per-bucket
  directories? Proposed: one-shot
  `aeat config bucket migrate-from-legacy` reads every
  `bucket_id` value, splits the SQLite file by `bucket_id`
  column, writes per-bucket directories, and tombstones the
  legacy `var/aeat.db` after a manifest checksum confirms
  parity.
- Does `aeat config bucket delete BUCKET_ID` retain an
  audit-export (per LGT Art. 29 retention duty) by default, or
  only on opt-in via `--retain-audit-export`?
- Should `aeat config bucket export` include the
  recovery-wrapped key (so an importer can recover with the
  mnemonic alone) or omit it (so an importer must transport
  the recovery code separately)?
- What is the operator-facing terminology -- exclusively bucket
  in CLI verbs (`aeat config bucket use`), or profile with
  bucket as an implementation detail (`aeat config profile use`
  today)? The ADR must pick one and prune the other.
- Is there a separate vault surface (the Drive mirror folder
  `aeat-vault/`), and if so, must it be renamed to avoid
  collision with the bucket synonym?
- How does the existing `Settings.aeat_default_profile_name`
  reconcile with the bucket pointer -- removed entirely, or
  kept as a fallback for headless invocations where no
  workflow state has been minted yet?
- How are bucket-scoped audit events emitted on switch -- to
  the PREVIOUS bucket only, to the NEW bucket only, to BOTH,
  or to a global cross-bucket audit log? ADR-1's append-only
  event-history table (`BucketEventHistoryRepository`) is
  per-bucket today; the cross-bucket case has no home.
- Does a long-running daemon (none today, anticipated for live
  notification capture in EPIC #316) need a
  session-unlock-per-bucket protocol that can hold N buckets
  unlocked concurrently, or a strict-one-bucket-at-a-time
  invariant?
- For the `profile duplicate` verb that exists today: does it
  survive in Option B.2 / B.3 (copy ciphertext, re-encrypt
  under new bucket's key, prompt for new passphrase), or is it
  removed in favour of `bucket export` + `bucket import` with
  a rename?
- What is the test contract that prevents the class-level cache
  defect from regressing? Proposed: a property-based test that
  switches between two buckets N times and asserts that the
  master key bytes in process memory change on each switch (via
  a test-only introspection surface).
