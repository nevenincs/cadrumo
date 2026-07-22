# Security policy

`aeat` prepares Spanish tax-form (modelo) data from your own financial records.
It handles taxpayer financial data and identifiers, so its security posture
matters. This document describes what the code protects, how to report a
vulnerability, and the threat model that scopes the protection.

The project is pre-alpha. Expect the surfaces described here to change between
versions.

## Reporting a vulnerability

Report suspected vulnerabilities privately. Do not open a public issue for a
security problem.

- **Primary channel: GitHub private vulnerability reporting.** Open the
  `Security` tab on this repository and select `Report a vulnerability`. This
  opens a confidential draft advisory visible only to you and the
  maintainers, with no email address or other secret required on either
  side. This is the intended disclosure path for this project.

  If the `Report a vulnerability` button is not visible, private
  vulnerability reporting has not yet been enabled on this repository. See
  the maintainer note below, and fall back to the secondary channel.

- **Secondary channel (not yet available):** a dedicated security-contact
  email address. None is published yet. A maintainer may add one to this
  document in the future as a secondary channel; until that happens, if the
  primary channel is unavailable, open a regular issue asking to be
  contacted privately and omit technical detail — do not post vulnerability
  details in a public issue.

> Maintainer follow-up: **Private vulnerability reporting** is a per-repository
> toggle under `Settings -> Code security -> Private vulnerability reporting`.
> On a public repository this is a free, one-click enable. This repository is
> currently private, and GitHub only offers private vulnerability reporting
> on private repositories as part of GitHub Advanced Security; confirm current
> plan eligibility before relying on it. If enabling it is not possible while
> the repository stays private, the options are: make the repository public
> (enabling the toggle becomes free), enable GitHub Advanced Security for this
> repository, or publish a secondary security-contact email as the working
> primary channel instead. This tracks the same private-repository plan
> constraint already recorded for branch protection.

Include in your report:

- A description of the issue and its impact.
- The steps to reproduce it.
- The affected version or commit.

Do not include real taxpayer data, live credentials, or session state in a
report. Redact identifiers and use synthetic values.

### What to expect

- Acknowledgement of the report.
- An assessment of whether the issue is in scope (see the threat model below).
- A fix or a documented mitigation for in-scope issues, released in a normal
  version update.

Because the project is pre-alpha and single-maintainer, response times are
best-effort, not contractual.

## Security posture

The following describes behaviour the code implements today.

### Local-only processing

`aeat` runs on your own machine and works one taxpayer at a time. It reads your
records, computes modelo figures, and exports a file for you to submit. It is
not a hosted service and keeps no central store of user data.

### No live AEAT submission

`aeat` builds, checks, and exports filings. It does not file them. No submit
command exists, and no code path contacts AEAT to file on your behalf. You
upload the exported file to AEAT yourself through the official channel.

External AEAT write paths are guarded behind an explicit opt-in
(`AEAT_LIVE_TESTS_ENABLED`) and default to dry-run. This keeps automated runs
from touching the live tax authority by accident.

### Sensitive financial data stays in encrypted storage

Purchase and sales invoices, bank statements, supporting documents, and any
evidence bytes derived from them persist only inside the encrypted
secure-storage backend, scoped to the active taxpayer profile. The code does
not write this data to temporary files, scratch directories, plaintext side
stores, on-disk caches, or logs. Decrypted bytes exist only transiently in
process memory.

### Encryption at rest

Sensitive records are encrypted with AES-256-GCM before they touch disk. Two
layers apply it:

- Column-level encryption wraps individual database columns (strings, raw
  bytes, and JSON values) through the crypto stack.
- Envelope-level encryption stores whole payloads as ciphertext envelopes.

Each record carries a sensitivity classification. A load rejects
ciphertext of the wrong class before the master key is consulted, and the
authenticated-encryption associated data binds each ciphertext to its purpose,
so a value encrypted for one column refuses to decrypt as another. Where the
code needs to look a value up without exposing it, it stores a keyed HMAC-SHA256
digest rather than the plaintext; object keys derive from a SHA-256 of the
identifier, never the cleartext taxpayer identifier.

### Master key handling

The at-rest master key is 32 bytes of random data. It is acquired through one of
two backends:

- The operating-system keychain (Windows Credential Manager, macOS Keychain,
  Linux Secret Service). This is the default where a usable keychain exists.
- An encrypted-file fallback for headless or CI hosts, where a passphrase-derived
  key-encryption key (Argon2id, per-store random salt) wraps the master key with
  AES-256-GCM.

The master key is never written in cleartext. A guard refuses to run under the
insecure in-memory provider when a real taxpayer identifier is present. Lost
access to the keychain or passphrase is recoverable through a BIP-39 recovery
mnemonic minted at setup; the mnemonic itself is never persisted to disk.

### Compiled-extension hardening on Homebrew Linux arm64

The Homebrew formula builds its Python C extensions from source on the
installing machine. On Linux arm64 only, the formula disables Homebrew's
pac-ret branch-protection compiler flag (`-mbranch-protection=standard`),
because Apple Virtualization.framework guests — the dominant Linux-arm64
environment (colima and Docker Desktop VMs on Apple silicon) — fault on the
ARMv8.3 pointer-authentication `retaa` instruction it emits. Extensions built
there carry no return-address-integrity hardening, matching the baseline of
the PyPI wheels, which are built without that flag. Native macOS arm64
Homebrew installs, where pointer authentication executes correctly, keep the
hardening.

## Threat model

### Assets protected

- Taxpayer financial data: invoices, bank statements, ledger entries, computed
  modelo figures, and filing drafts.
- Taxpayer identifiers: NIF, CIF, DNI, NIE, and NII values.
- Credentials and session state for external services.

### Trust boundaries

- Your machine and its logged-in operating-system user are trusted. `aeat` runs
  with your privileges and can read what you can read.
- The operating-system keychain (or the passphrase for the file fallback) is the
  root of trust for the at-rest encryption.
- Data at rest in the encrypted stores is treated as protected against anyone
  who reads the raw files without the master key.
- External services (the AEAT portal, and optional Google Drive/Sheets export or
  LLM providers when enabled) are outside the trust boundary. They are only
  contacted when you opt in.

### In scope

- Confidentiality of sensitive financial data and identifiers at rest.
- Leakage of sensitive data into logs, temporary files, scratch directories, or
  plaintext side stores.
- Correct handling of the master key and recovery material.
- Enforcement of the no-live-submission safety gate.
- Leakage of secrets or private data into committed source or bundled data.

### Out of scope

- A compromised host, malware running as your user, or an attacker with physical
  access to an unlocked, running session. Such an attacker already has your
  privileges and can read decrypted data.
- The security of external services you connect to (AEAT, Google, LLM
  providers). Their handling of any data you send is governed by their own
  policies.
- The correctness of tax calculations. A wrong figure is a filing-accuracy
  issue, not a security vulnerability; report it as a normal bug.
- Denial of service against your own local tooling.

## Handling bundled data

The tree under `src/cadrumo/_data` holds bundled reference data (official-source
corpus captures and curated registry data), not user data. Its handling rules,
including the prohibition on committing credentials or taxpayer data, are
documented in `src/cadrumo/_data/SECURITY.md`.
