---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave17-research]]"
  - "[[2026-04-30-secure-persistence-foundation-wave15-16-audit]]"
  - "[[2026-04-30-secure-persistence-foundation-wave14-adr]]"
---

# `secure-persistence-foundation` adr: wave-17 Kent UX security integration | (**status:** `accepted`)

## Problem Statement

The wave-1..16 substrate is cryptographically complete (AES-256-GCM AEAD, HKDF-SHA256 per-purpose KEK, Argon2id passphrase-derived KEK, master-key rotation across envelopes + blob-store DEKs, KDF-version migration, corpus integrity manifest, per-file locks). However the **operator UX is not enrolled in the security layer**: master-key minting is silent, `aeat doctor` has zero security checks, documentation never mentions encryption, failure modes surface as opaque cryptographic exceptions, and no first-class flow exists for backup, recovery, or first-run provisioning.

Wave-17 closes the UX-side gap. The substrate stays unchanged; the work is wiring the user-facing surface so the security layer is **legible, controllable, recoverable, and auditable** by the operator.

## Considerations

Surveyed in the wave-17 research artefact:

- **Ten gaps catalogued** in the existing Kent UX (G1 silent first-run, G2 doctor-no-security-rows, G3 docs-silent-on-security, G4 no-first-run-test, G5 opaque-failure-modes, G6 no-provision-command, G7 no-key-export, G8 no-opt-out, G9 profile-encryption-linkage-undocumented, G10 settings-discoverability).
- **Six industry-pattern doctrines** (D1 default-secure-is-norm, D2 three-provisioning-families, D3 onboarding-brutally-narrow, D4 recovery-key-essential, D5 three-failure-classes, D6 profile-first-sequencing).
- Survey covered Bitwarden CLI, 1Password CLI, KeePassXC, age/rage, Borg, Restic, Kopia, Cryptomator, gocryptfs, GnuCash (counter-example), Beancount (counter-example), GPG (cautionary tale).

## Constraints

- **No substrate changes**: wave-1..16 cryptographic primitives are accepted-as-final. Wave-17 only adds UX wrapping + CLI commands + doctor checks + documentation. Any change to the substrate is out of scope.
- **No live-submit re-introduction**: per the project's permanent live-submit prohibition (PR #446 + memory). Wave-17 cannot add commands that touch a remote AEAT service.
- **Trilingual error registry**: every new error class must be registered in `aeat.core.errors._registry` with es/en/hu messages. No raw `ValueError` / `RuntimeError` at user-facing boundaries.
- **Pydantic v2 strict-frozen** for any new record types.
- **No mocks/fakes/skips**: per the project mandate. New tests exercise real master-key paths via `EphemeralMasterKeyProvider` for in-process control + a real file-fallback integration test for first-run coverage.
- **Bounded scope**: wave-17 is the LAST wave of the secure-persistence-foundation epic. Anything that doesn't fit is closed by-rejection or marked release-notes scope (per the wave-14 closure pattern).

## Hard Decisions

### D1 — Opt-out posture: default-secure with hostile-named flag | **status: accepted**

Default behaviour: **mandatory encryption** for every persistence operation. Matches Bitwarden / 1Password / Kopia / Cryptomator / KeePassXC. The substrate's existing hard-cutover (no plaintext fallback) is preserved.

For testing / throwaway / educational scenarios: introduce an explicit opt-out gated behind **two simultaneous signals**:

1. The `AEAT_ALLOW_UNENCRYPTED=1` environment variable (legible-and-embarrassing per the survey).
2. The `aeat_secret_store_backend=unsecured` setting OR `--insecure-no-encryption` CLI flag.

Implementation: a new `UnsecuredMasterKeyProvider` that derives its 32-byte master key from a **published deterministic constant** (`b"AEAT_UNSECURED_DO_NOT_USE_FOR_PROD" + 4 NUL bytes`), so the substrate's encryption pipeline is unchanged but the wrapping key is publicly known. This preserves the hard-cutover invariant (every byte is still ciphertext on disk) while making "unsecured" a discoverable attribute (the well-known key fingerprint is visible in `aeat doctor`).

**NIF-canary refusal**: at every load-or-mint of the operator profile, the substrate inspects the active master-key provider. If `UnsecuredMasterKeyProvider` AND the profile's `tax_id` validates as a real NIF/NIE/CIF (per the wave-2 validator), the load fails with `UnsecuredModeRefusedError` and a clear message: "Unsecured mode is incompatible with a real NIF. Either remove the `--insecure-no-encryption` flag, or use a synthetic NIF (e.g. `00000000T`)."

**Why deterministic-key over true-plaintext**: the substrate's substrate (encrypted blob store, secret store, every governance envelope) has hard-coded the AEAD path. Adding a "skip encryption" branch would re-introduce dual-mode plumbing that wave-9 explicitly removed. A deterministic-key provider is "encryption with a published key" — provides zero confidentiality, but keeps the substrate's invariants (every record is a `CipherEnvelope` / `EncryptedBlob`; rotation, integrity, redaction all still apply).

**Rejected**: a settings-flag that bypasses encryption end-to-end. Reason: dual-mode plumbing across the entire substrate is unacceptable code burden + violates the wave-9 hard-cutover principle.

### D2 — Master-key provisioning model: hybrid (keychain-preferred + Argon2id passphrase + keyfile escape) | **status: accepted**

The substrate already provides:
- `KeyringMasterKeyProvider` (OS keychain — Windows Credential Manager / macOS Keychain / Linux libsecret).
- `FileFallbackMasterKeyProvider` (Argon2id passphrase-derived KEK wrapping a random 32-byte master key).
- `EphemeralMasterKeyProvider` (in-memory, tests only).

Wave-17 adds the UX wrappers + a new keyfile-import path:

- **`aeat security provision`** — interactive command that walks the user through:
  1. Backend choice prompt (keychain / file-fallback / unsecured).
  2. For file-fallback: passphrase prompt + confirmation.
  3. Generate the master key.
  4. Display the recovery key once (D4) — Cryptomator pattern.
  5. Round-trip verify (encrypt + decrypt a canary record).
- **`aeat security provision --backend keyfile --keyfile <path>`** — non-interactive provisioning from an operator-supplied 32-byte key file. Use case: headless / CI / cross-machine portability.

The 1Password+Bitwarden hybrid pattern is preserved: keychain is preferred when available; file-fallback Argon2id passphrase is the resilient backup; keyfile import is the escape hatch for headless servers.

**Rejected**: replacing the file-fallback's Argon2id with a different KDF for ergonomic reasons (e.g. operator-tunable). Argon2id with OWASP-current parameters is locked-in per wave-12 ADR Q3.

### D3 — Sequencing: profile-first then encryption | **status: accepted**

The wave-17 setup wizard sequences as:

1. **Operator profile**: `aeat setup` collects NIF, business profile, contact details, applicable modelos. (Existing wave-N flow.)
2. **Security provisioning**: explicitly invoked at the end of `aeat setup` (or runnable standalone via `aeat security provision`). The non-secret profile data establishes the operator identity; the security question is then framed as "we're about to encrypt your tax records — choose how to lock them".

The sequencing also pre-binds the keyring entry to the operator's NIF: the keychain service identifier is `aeat:secure-persistence:<nif-prefix>` so multi-operator hosts (rare for the autónomo target, but defensive) keep stores isolated.

**Rejected**: encryption-first then profile (matches GPG anti-pattern). Reason: forces the user to think about cryptographic primitives before the tool has context.

**Rejected**: combined wizard with intermixed profile + encryption questions. Reason: increases cognitive load; the survey's "brutally narrow onboarding" pattern says one decision at a time.

### D4 — Recovery + backup + failure-mode UX | **status: accepted**

Three new operator-facing surfaces, all parts of the same recovery story:

#### D4a — Recovery key (Cryptomator pattern)

At provision time, the substrate generates a fresh 32-byte recovery key. Encoded as a **24-word BIP-39-style mnemonic** for human-readability. Displayed **once** with explicit print-and-store instructions ("Print this and store it somewhere safe. We will never show it again. Without this you cannot recover your data if you lose access to the keychain or the passphrase.").

The recovery key wraps the master key via AES-256-GCM (recovery-key-wrapped master.key file persisted as `master.recovery.key`), so the recovery flow is **independent** of the active master-key provider. Operator can later use `aeat security recover --recovery-key "<24 words>"` to mint a fresh master.key from the recovery wrapping.

The recovery key is **never persisted on disk** at provision time. The `master.recovery.key` file (the wrapped master key) IS persisted; the recovery key itself is the operator's responsibility.

#### D4b — `aeat security key-export <output-path>`

First-class CLI for backing up the wrapped master key. Output is a plaintext-JSON file containing the encoded `master.key` + `master.kdf` + `salt` artefacts (file-fallback) OR a portable wrapping of the keyring-stored key (keychain). Operators are instructed to copy this file to off-site storage.

The export is **not** the recovery key — it's a portable copy of the encrypted-store artefacts. Distinct purposes:
- **Recovery key** (D4a): unlocks the master key WITHOUT the passphrase / keychain. For "I forgot my passphrase".
- **Key export** (D4b): a portable copy of the entire encrypted-store state. For "my disk died" / "I'm migrating to a new laptop".

#### D4c — Three-failure-class error messages

New typed error subclasses + trilingual registry entries:

- `MasterKeyKeychainLockedError(MasterKeyUnavailableError)` — recoverable via keychain unlock; CLI prints actionable message.
- `MasterKeyPassphraseMismatchError(MasterKeyUnavailableError)` — wrong passphrase; CLI offers retry with backoff.
- `MasterKeyMaterialMissingError(MasterKeyUnavailableError)` — neither key file nor keychain entry exists; CLI prompts for `aeat security provision` or `aeat security recover --recovery-key`.

Existing call sites that raise `MasterKeyUnavailableError` are not regressed — the new subclasses are inheritance-compatible. Wave-17 narrows the throws inside the master-key providers to use the appropriate subclass.

## Implementation

### Phases (8 phases)

1. **Phase 1 — `aeat doctor` security rows.** Add 4-6 health rows: secret-store dir + permissions, active backend, master-key readiness (file-fallback: master.key + master.kdf + salt; keychain: probe), KDF version (post-wave-12 v2), unsecured-mode warning, recovery-key-wrapped backup presence.

2. **Phase 2 — Three-failure-class error subclasses.** New error classes in `aeat.adapters.persistence.storage.errors`; trilingual registry entries; narrow throws in `KeyringMasterKeyProvider` + `FileFallbackMasterKeyProvider`.

3. **Phase 3 — `UnsecuredMasterKeyProvider` + opt-out plumbing.** New provider class; `aeat_secret_store_backend=unsecured` mode; `AEAT_ALLOW_UNENCRYPTED=1` gate; NIF-canary refusal at profile-load time.

4. **Phase 4 — `aeat security provision` interactive command.** Backend prompt; passphrase prompt; recovery-key generation + display; round-trip verify; profile-first invocation from `aeat setup`.

5. **Phase 5 — `aeat security recover --recovery-key`** + `aeat security key-export <out>`. Recovery-key unwrap path; first-class export of master.key / master.kdf / salt as portable JSON.

6. **Phase 6 — Wave-12 setup-wizard wire-in.** `aeat setup` invokes `aeat security provision` after the profile-write step. Existing setup tests updated.

7. **Phase 7 — Documentation.** `docs/getting-started.md` first-run-security section; `docs/security-runbook.md` recovery-flow section; README `## Security` block; `env/.env.example` `AEAT_ALLOW_UNENCRYPTED` documented.

8. **Phase 8 — First-run integration test.** `tests/integration/test_first_run_security.py` — brand-new fs, profile-first wizard, security-provision, doctor health-check, financial-ingest round-trip, second-run idempotency.

### Phase 9 — Audit gate + reviews

Wave-17 audit-gate document + `@gemini` + `@codex` review requests on the executed substrate.

## Rationale

**Why this wave is essential despite the substrate being cryptographically complete.** A cryptographically complete substrate that the user cannot interact with safely is a usability failure. The wave-1..16 work is invisible to the operator — silent-success on the happy path, opaque-failure on the unhappy path. Wave-17 closes the loop: every security-relevant operation has a Kent-facing surface, every failure mode has a class-specific actionable message, every persisted record is recoverable.

**Why hostile-named flag instead of mandatory-only.** The strongest tools converge on hostile-flag opt-outs (Restic `--insecure-no-password`, Borg `-e none` deprecated). Refusing the opt-out entirely means testing scenarios route around the substrate by setting up parallel infrastructure — worse than a legible escape hatch. The deterministic-key approach also keeps the substrate invariants intact.

**Why Cryptomator recovery-key + Borg key-export.** AEAT data is FINANCIAL + IDENTITY + AUDIT class with legal weight. Permanent silent data loss from a forgotten passphrase is unacceptable. The two patterns address two different recovery scenarios (lost passphrase vs lost machine) and compose cleanly.

**Why narrow onboarding.** GPG's sin was making users decide cryptographic primitives during onboarding. Wave-17 hides everything behind sensible defaults (keychain when available, Argon2id-OWASP-current when not) and asks the user only one binary question: "encrypt with the OS keychain (recommended) or a passphrase you'll remember?".

## Consequences

**Substrate unchanged.** Every wave-1..16 invariant holds. The substrate's hard-cutover, classification policy, rotation contract, KDF migration, corpus integrity, file-locking — all intact.

**Operator surface materially expanded.** Five new CLI subcommands (`security provision`, `security recover`, `security key-export`, `security status`, plus the `--insecure-no-encryption` flag exposed across all persisting commands). `aeat doctor` grows ~6 security rows. Setup wizard grows one explicit security step.

**Documentation grows.** `docs/getting-started.md` adds a first-run-security section (~150 lines). `docs/security-runbook.md` grows a recovery-flow section. README adds a `## Security` block.

**No legacy code retained.** Per the no-legacy mandate: when wave-17 ships, the silent-mint behaviour goes away — `_resolve_master_key_provider()` no longer auto-mints if the security layer hasn't been provisioned. First-time call without provisioning produces `MasterKeyMaterialMissingError` pointing at `aeat security provision`. Backward incompatibility is intentional: existing stores keep working (they have a `master.kdf` already); only NEW installations require explicit provisioning.

**Test surface grows.** First-run integration test + provision/recover/export unit tests. Estimated +200 LoC of test code.

**Forward-compatibility.** Any future security-layer feature (post-quantum KDF migration, hardware-token backends, MDM-managed key escrow) inherits the wave-17 UX scaffolding (`aeat security` family, doctor checks, error classes). The pattern is repeatable.

**Closes the secure-persistence-foundation epic.** After wave-17 lands, the substrate is feature-complete AND the operator UX is enrolled. The post-wave-17 roadmap is bounded: documentation polish, release-notes scope, normal feature evolution.
