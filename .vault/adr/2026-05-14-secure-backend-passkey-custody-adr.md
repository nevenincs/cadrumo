---
tags:
  - '#adr'
  - '#secure-backend-passkey-safety'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-14-secure-backend-passkey-safety-research]]'
  - '[[2026-04-12-data-storage-adr]]'
  - '[[2026-05-08-secure-storage-legacy-path-audit-reference]]'
---

# secure-backend-passkey-safety adr: master passkey custody + enrollment ux | (**status:** `accepted — execution-ready`)

## Problem Statement

The Secure backend mints the AES-256-GCM master key silently on first
encrypted write, never asks the operator for a passphrase, never
displays a recovery code, and never warns that loss of the OS keychain
entry or its companion passphrase destroys every sealed record in the
substrate (research §1, §2.1, §2.4). The on-disk file backend co-locates
the wrapped master key, KDF parameters, and salt under the same `var/`
parent as the SQLite ciphertext (research §2.2): a single stolen
directory hands an attacker the wrapped key, the KDF cost parameters,
and the ciphertext together, reducing the encryption-at-rest model to
the strength of the operator passphrase alone.

Three compounding defects make this a critical data-loss surface:

- Silent auto-mint with no operator consent (research §2.1, §2.4).
- Custody opacity: the operator is never told which of three resolver
  backends won, nor where the key landed (research §2.5).
- Dead-letter recovery surface: full BIP-39 recovery cryptography is
  implemented in `src/aeat/adapters/persistence/storage/master_key/_recovery.py`
  but never wired to any CLI verb; the substrate's own error messages
  point operators at `aeat security recover` and `aeat security provision`
  which do not exist anywhere in `src/aeat/entrypoints/cli/` (research §2.5,
  §2.7).

There is additionally no operator-facing lock or unlock concept. The
master key is cached at ClassVar scope in
`src/aeat/adapters/persistence/storage/master_key/_master_key.py`
(lines 348-349 and 473-475 per research §2.6) for the entire process
lifetime. A long-running invocation holds cleartext key material
indefinitely with no operator control.

This ADR decides custody, enrollment UX, recovery wiring, lock and
unlock semantics, rotation, the canonical CLI verb set, the data-loss
copy deck, the no-backwards-compat re-enrollment posture, and the
legal grounding under Ley 58/2003 retention obligations.

## Considerations

The research surveyed twelve industry comparables (1Password, Bitwarden,
age, GnuPG, KeePassXC, Aegis, restic, BorgBackup, rclone crypt, macOS
Keychain / Windows DPAPI / libsecret, HashiCorp Vault, Cryptomator and
VeraCrypt) in research §3 and distilled five invariants in §3.13: no
silent enrollment, explicit data-loss framing, a documented recovery
path, key material not co-located with ciphertext, and lock semantics
as a first-class verb. The substrate today violates all five.

Three custody options were surfaced in research §6.1 and §7:

- A.I — passphrase-mandatory with BIP-39 mnemonic recovery, OS keystore
  as short-TTL session cache, idle-timeout auto-lock (research §7.1).
  Mirrors 1Password and Bitwarden. Highest UX friction, highest safety.
- A.II — OS-keystore-primary, file backend reserved for headless or CI,
  mandatory printed mnemonic on enrollment for portability and
  loss-of-OS-account recovery (research §7.2). Lowest daily friction,
  depends on per-OS keystore reliability, weaker portability.
- A.III — Borg-keyfile-like operator-chosen `--key-file` path plus
  passphrase plus mnemonic (research §7.3). Maximal portability,
  highest cognitive load, weakest zero-config story which conflicts
  with the wizard one-command on-ramp mandate (research §6.2).

Legal exposure was researched in §4. Ley 58/2003 Art. 29 imposes the
retention obligation; Art. 66 sets the 4-year prescription window;
Codigo de Comercio Art. 30 raises the accounting-records floor to 6
years; Real Decreto 1619/2012 Art. 19-20 requires legible, integral,
accessible preservation of invoices. AEAT preserves a canonical copy
of every electronically-filed declaration on the Sede side, addressable
by CSV under Ley 39/2015 Art. 27.3 and Ley 40/2015 Art. 42 `[unverified
— specific historical depth on Sede not located in this pass]`. Local
loss of filed-declaration metadata is partially mitigated by Sede
re-download; local loss of supporting documents (invoices, ledgers,
working calculations) is NOT mitigated, because AEAT does not hold the
operator's pre-filing supporting records. The data-loss framing must
therefore name both the recoverable and non-recoverable surfaces
honestly (research §4.3).

Technical inputs:

- OWASP Password Storage Cheat Sheet 2024 baseline for Argon2id:
  memory cost 19 MiB, time cost 2, parallelism 1, salt 16 bytes,
  output 32 bytes. This matches the parameters already present in
  `_master_key.py:89-105` per research §2.1.
- BIP-39 24-word mnemonic primitives at
  `src/aeat/adapters/persistence/storage/master_key/_recovery.py`
  (research §2.7 and §6.4) are already implemented; only the CLI
  wiring is missing.
- The `dont_move_inflight_agent_work` and `no_backwards_compat_no_deprecation`
  project mandates: removed code stays removed, added code lands fully,
  no migration shims, no deprecation flags.

## Constraints

- The Secure backend must satisfy RGPD Art. 32 appropriate-measures
  for personal-data confidentiality, weakened today by the co-location
  anti-pattern (research §4.4).
- The decision surface is operator-visible at first run: the enrollment
  flow lives inside `aeat config init`, which is the wizard's
  one-command on-ramp.
- The CLI root remains exactly two surfaces (config + app), per the
  project root-two-only rule. No new `aeat security` root is permitted;
  the dead-letter `aeat security recover` and `aeat security provision`
  strings in `_master_key.py:558-563, 619-622, 1056-1058` must be
  rewritten to point at canonical `aeat config <verb>` forms.
- No backwards compatibility shims, no deprecation flags, no silent
  migration paths. First run on an existing install detects the absence
  of a manifest plus KDF params recorded under the new schema and
  refuses to operate, instructing the operator to back up `var/` to
  cold storage and run `aeat config init` from scratch.
- The decision must compose with ADR-2 (profile bucket vault
  lifecycle): per-bucket KDF parameters, per-bucket salt, and
  per-bucket recovery wraps are required so that ADR-2's per-bucket
  key schedule has a single-bucket precedent that already enforces the
  separation rule.
- Latency budget: Argon2id at the OWASP baseline parameters adds
  roughly 50-100 ms per unlock. Acceptable for an interactive
  passphrase prompt; not acceptable on every CLI call. The unlock
  session must therefore cache the derived KEK in process memory
  between unlock and lock, bounded by an idle-timeout auto-lock.

## Implementation

### 1. KDF — Argon2id at the OWASP 2024 baseline

The substrate derives every passphrase-bound KEK via Argon2id with
concrete parameters: memory cost 19 MiB, time cost 2, parallelism 1,
salt 16 bytes, output 32 bytes. These match the values already encoded
in `_master_key.py:89-105` (research §2.1) and the OWASP Password
Storage Cheat Sheet 2024 baseline. KDF parameters are persisted in the
bucket manifest as part of the ADR-2 contract and re-read on every
unlock so a future cost-bump is non-breaking. The KDF identifier and
its parameter version are recorded explicitly in the manifest so the
substrate refuses to unlock material derived under a parameter set it
does not implement.

### 2. Mandatory operator-chosen passphrase at enrollment

`aeat config init` collects a passphrase interactively, requires a
double-confirmation entry, and requires an explicit acknowledgement
flag (operator must type the literal acknowledgement phrase) before
any KDF derivation begins. Silent auto-mint is forbidden; the lazy
mint path in `_master_key.py:432-453` is removed in favour of an
explicit `aeat config init` driven mint that runs only after the
operator has supplied the passphrase, confirmed it, and acknowledged
the data-loss risk.

The non-interactive entry path refuses to mint a master key unless
`AEAT_SECRET_PASSPHRASE` is set in the environment AND an explicit
`--accept-data-loss-risk` flag is supplied to `aeat config init`. The
acknowledgement is recorded in the operator-visible audit trail. There
is no silent CI escape hatch; the headless deployment supplies the
acknowledgement flag deliberately.

### 3. Key and ciphertext separation — HARD INVARIANT

The passphrase-derived KEK is held in process memory only and is
never written to disk in cleartext. The KDF salt and KDF parameters
live in the per-bucket manifest (per ADR-2), separate from the
ciphertext store. The wrapped master DEK is persisted, but only the
DEK is wrapped: the KEK that wraps it is reconstructed on each unlock
from the passphrase plus the manifest's KDF salt and parameters.

The OS-keystore session cache (decision 5 below), when enabled, lives
in the OS keystore via the existing `keyring` adapter and never in any
file under the project tree or under `aeat_secret_store_dir`. The
substrate refuses to start when `aeat_secret_store_dir` resolves under
the `aeat_database_url` parent directory; this is a fail-closed startup
check, not a warning.

A linter rule and a corresponding integration test enforce both halves:
the test asserts that no cleartext KEK bytes are ever written under
`aeat_secret_store_dir`, `aeat_database_url`'s parent, or
`aeat_blob_store_dir` during a full enrollment plus unlock plus rekey
cycle. The linter scans the substrate source for any code path that
persists a value derived from the passphrase outside the OS keystore.

### 4. Recovery enrollment — BIP-39 24-word code

At enrollment, after the passphrase is double-confirmed, the substrate
generates a BIP-39 24-word recovery code via `generate_recovery_key`
from `src/aeat/adapters/persistence/storage/master_key/_recovery.py`
(research §2.7 documents the primitive as already implemented). The
code is displayed once. The operator must re-type the words at three
random positions (1Password-style confirm-by-retype) before the profile
is marked usable.

The recovery code derives a separate KEK that wraps the master DEK
into a second wrapped artefact. The recovery wrap is the inverse of
the passphrase wrap: either one independently unwraps the DEK. The
on-disk persistence of the recovery wrap is opt-in only via an explicit
`--persist-recovery-wrap` flag during enrollment; the default is
print-only, no on-disk recovery file. If the operator opts in to
on-disk persistence, the recovery wrap path defaults outside
`PROJECT_ROOT` (cross-platform default: `~/.config/aeat/recovery/` on
POSIX, `%LOCALAPPDATA%\\aeat\\recovery\\` on Windows) and the operator
is shown an acknowledgement screen describing the co-location risk
before the file is written.

The recovery primitives in `_recovery.py` (research §2.7 confirms they
are implemented but unwired) are wired through the new
`aeat config recover` verb (decision 7). The `complete_recovery` path
at `_master_key.py:660-738` is wired through the same verb to re-wrap
the recovered DEK under a fresh passphrase-derived KEK on the new
host.

### 5. Lock and unlock semantics

The substrate exposes explicit `aeat config unlock` and `aeat config lock`
verbs. The unlock verb prompts for the passphrase, derives the KEK,
unwraps the DEK, and holds the KEK plus the unwrapped DEK in
per-process instance state keyed to the active bucket. The lock verb
zeroises the KEK and DEK in memory and clears the instance state.

The ClassVar caches at `_master_key.py:348-349` (`KeyringMasterKeyProvider._cache`)
and at `_master_key.py:473-475` (`FileFallbackMasterKeyProvider._cached_passphrase`,
`_cached_master_key`) are removed. They are replaced with a
`BucketSession` instance scoped to the active bucket: the session is
constructed at unlock, destroyed at lock, and is the only object that
holds cleartext key material. Module-level singletons are forbidden
on this surface; the linter from decision 3 enforces this by rejecting
any ClassVar-typed cache on the master-key module.

The idle-timeout auto-lock defaults to 15 minutes and is configurable
via `aeat config set idle-lock-minutes <n>` where `n` is a positive
integer; the value lives in the per-bucket manifest. The auto-lock
runs on every CLI invocation: if the unlock timestamp recorded in the
ephemeral session file is older than the configured TTL, the next
invocation starts in the locked state and prompts for unlock.

The OS-keystore session cache is the second mechanism by which a KEK
survives across CLI invocations. When the operator opts in via
`aeat config set keystore-cache true`, an unlock writes the derived
KEK to the OS keystore under a per-bucket entry, scoped to the active
bucket's UUID per ADR-2. The keystore entry inherits the OS-level
lock semantics (Touch ID prompt on macOS, Windows Hello on Windows,
libsecret prompt on Linux). The idle-timeout still applies: an expired
session is locked even if the keystore entry survives. The keystore
opt-in is recorded in the audit trail.

### 6. Rotation — `aeat config rekey`

The `aeat config rekey` verb wraps the existing DEK under a fresh
passphrase-derived KEK. The DEK itself is not rotated; the ciphertext
is not re-encrypted. The operator supplies the current passphrase to
unlock and the new passphrase twice (confirm). The KDF salt is
regenerated. The new wrapped DEK replaces the prior one atomically
via `os.replace`, the same pattern used in
`FileFallbackMasterKeyProvider.complete_recovery` at `_master_key.py:660-738`
(research §2.7).

Full DEK rotation (re-encrypting every record under a fresh master
DEK) is a separate concern handled by the `_rotation.py` primitives
that exist at `src/aeat/adapters/persistence/storage/_rotation.py`
(research §2.7). That surface is out of scope for this ADR; it lands
through a follow-up verb only after the passphrase-rewrap surface is
stable. This ADR confines itself to passphrase rewrap.

### 7. CLI surface — canonical verb set

The exact verbs that this ADR introduces or rewires under `aeat config`:

- `aeat config init` — enrolls the operator: prompts for passphrase
  with double-confirmation, generates and displays the 24-word recovery
  code, requires confirm-by-retype of three random positions, then
  mints the master DEK and writes the bucket manifest.
- `aeat config unlock` — prompts for passphrase, derives the KEK,
  unwraps the DEK, opens a `BucketSession`.
- `aeat config lock` — zeroises the in-memory KEK and DEK, destroys
  the `BucketSession`, clears any OS-keystore session cache entry.
- `aeat config rekey` — re-wraps the existing DEK under a fresh
  passphrase-derived KEK.
- `aeat config show-recovery` — re-displays the 24-word recovery code
  after the operator unlocks (the operator must already know the
  passphrase; this verb does not regenerate the code, it surfaces the
  one the substrate already wraps).
- `aeat config verify-recovery` — prompts the operator to type all 24
  words; the substrate confirms the entry decodes to the same wrapped
  recovery KEK. Useful as a periodic operator-driven custody test.
- `aeat config recover --recovery-key <words>` — accepts a 24-word
  recovery code, unwraps the DEK via the recovery KEK, prompts for a
  fresh passphrase, re-wraps the DEK under the new passphrase-derived
  KEK, and writes the new wrapped DEK plus a fresh KDF salt to the
  bucket manifest. The original passphrase is never required.

The dead-letter references to `aeat security recover` and
`aeat security provision` at `_master_key.py:558-563`, `619-622`, and
`1056-1058` (research §2.5) are removed. Every error message at those
sites is rewritten to point at the canonical verbs above. The CLI root
remains exactly two surfaces; no new `security` root is created.

### 8. UX copy mandate — verbatim data-loss framing

Every enrollment prompt, every recovery prompt, and every lock-failure
error message contains, in plain language, the following sentence
verbatim:

> Loss of this passphrase AND this recovery code = permanent data loss.
> AEAT's portal retains the authoritative copy of any submitted
> declaration, but your local working state (drafts, evidence cache,
> transaction ledger) is irrecoverable.

This is a hard copy-deck mandate. The sentence appears in the es / en
/ ca locale catalogues with the same semantic content; locale-string
review confirms each translation preserves the both / and structure,
the named-surface enumeration (passphrase, recovery code), and the
explicit naming of irrecoverable local artefacts. The mandate is
enforced by a string-fixture test that asserts every operator-facing
enrollment, recovery, and lock-failure code path renders a string
containing the named surfaces.

### 9. No backwards compatibility — clean re-enrollment

Any currently-installed profile that was minted under the silent
auto-mint path is incompatible with the new substrate. There is no
migration shim, no silent upgrade, no compatibility flag.

First run of the new code on an existing install detects the absence
of a bucket manifest with KDF parameters recorded under the new schema
and refuses to operate. The error message instructs the operator to:

- Back up `var/` (the existing working state) to cold storage as an
  archival snapshot.
- Run `aeat config init` from scratch to re-enroll with a new
  passphrase and recovery code.
- Accept that records in the archived `var/` are NOT migrated into the
  new bucket; they remain readable only from the cold-storage snapshot,
  and only by a build of the substrate from the prior release.

This is consistent with the project's no-backwards-compat-no-deprecation
mandate: removed code stays removed, added code lands fully. The
substrate does not provide a migration tool that decrypts under the
silent-mint key and re-encrypts under the new passphrase-derived KEK;
such a tool would be exactly the kind of compatibility shim the
project rules forbid.

### 10. Legal grounding — Ley 58/2003 retention

Ley 58/2003 Art. 29 imposes on every obligado tributario the duty to
preserve books, registries, invoices, supporting documents, and any
other accounting and tax records throughout the prescription window
(Art. 66 of the same Ley, 4 years from the end of the voluntary-filing
window; Codigo de Comercio Art. 30 raises the floor to 6 years for
accounting books). Real Decreto 1619/2012 Art. 19-20 requires invoices
and their electronic equivalents to be preserved in legible, integral,
accessible form.

AEAT preserves the canonical copy of every electronically-filed
declaration on the Sede side, addressable by CSV under Ley 39/2015
Art. 27.3 and Ley 40/2015 Art. 42 `[unverified — specific historical
depth on Sede not located in this pass]`. The portal-side copy is the
legally-binding retention surface for filed-declaration metadata; local
loss of filed-declaration metadata is recoverable from Mis expedientes
on the Sede and therefore does not breach Art. 29.

Local loss of pre-filing supporting documents (invoices, ledgers,
working calculations, payment evidence) IS a breach of Art. 29 because
AEAT does not hold the operator's pre-filing records. The data-loss
framing in decision 8 names both surfaces honestly: the AEAT-portal
copy survives, the local working state does not. The operator's legal
exposure under LGT Art. 203 (infracciones por resistencia,
obstruccion, excusa o negativa) for unjustifiable absence of required
records is real if the operator loses both the passphrase and the
recovery code AND has no archival snapshot of the local working state.

The substrate's role is to make this exposure visible to the operator
at enrollment, not to assume it away. The UX copy mandate (decision 8)
states it explicitly.

## Rationale

**Selected option: A.II — passphrase-primary with OS-keystore session
cache (research §7.2 hybrid framing).**

The brief proposes A.II as the recommended pick. The research supports
this selection. The reasoning, validated against research §3.13 and
§7:

- A.II honours all five invariants in research §3.13: no silent
  enrollment (passphrase is mandatory at `aeat config init`), explicit
  data-loss framing (the copy mandate in decision 8), documented
  recovery path (BIP-39 24-word code with confirm-by-retype), key
  material not co-located with ciphertext (the KEK lives in process
  memory or in the OS keystore, the wrapped DEK plus KDF params live
  in the bucket manifest which under ADR-2 is in a per-bucket
  directory), and lock as a first-class verb (`aeat config lock` plus
  idle-timeout auto-lock).
- A.II supports the lock-and-unlock state machine the project needs.
  The KEK lives in process memory by default after unlock; the
  OS-keystore session cache is an opt-in convenience that the operator
  can disable to trade convenience for security (decision 5).
- A.II preserves the wizard one-command on-ramp mandate (research §6.2):
  enrollment is interactive inside `aeat config init` without forcing
  the operator to choose a key-file path (the A.III friction).
- The research's option-A descriptions in §6.1 explicitly frame A.II
  as the OS-keystore-cache hybrid; this ADR codifies it as
  passphrase-primary (the passphrase is the ground truth) with the
  keystore as a session cache only. The keystore is never the sole
  custody surface; an operator who loses the keystore but remembers
  the passphrase recovers without the recovery code.

**Rejected options:**

- A.I — passphrase-mandatory with no keystore caching. Rejected
  because the daily-use friction of typing the passphrase on every
  `aeat config show` or `aeat app modelo run` invocation is
  incompatible with the wizard's interactive ergonomics. The
  idle-timeout auto-lock in A.II reduces friction without sacrificing
  the safety floor.
- A.III — Borg-keyfile-like operator-chosen `--key-file` path.
  Rejected because the operator-cognitive load of choosing a key-file
  path conflicts with the zero-config first-run goal (research §7.3
  flags this as the trade-off). Operators who want explicit key-file
  custody are served by the `--persist-recovery-wrap` opt-in in
  decision 4, which produces an out-of-tree recovery file the operator
  can place wherever they want.

## Consequences

### Code rewrites required

The research enumerated the touch points; this ADR codifies them.

- `src/aeat/application/setup/_service.py:12-57` — `initialize_workspace`
  no longer triggers lazy mint via `workflow_state_repository().update(...)`.
  The setup service receives an already-unlocked `BucketSession` from
  the CLI layer; if no session is present it refuses to proceed.
- `src/aeat/entrypoints/cli/_config/__init__.py:628-695` —
  `aeat config init` is rewritten to drive the enrollment flow:
  passphrase prompt with double-confirm, recovery-code generation and
  confirm-by-retype, manifest write, then setup-service invocation.
  The function signature gains `--accept-data-loss-risk`,
  `--persist-recovery-wrap`, and the non-interactive gate on
  `AEAT_SECRET_PASSPHRASE`.
- `src/aeat/adapters/persistence/storage/master_key/_master_key.py` —
  the ClassVar caches at lines 348-349 and 473-475 are removed; the
  `BucketSession` instance state replaces them. The lazy-mint path at
  lines 432-453 is removed. The dead-letter references at lines
  558-563, 619-622, and 1056-1058 are rewritten to point at the
  canonical verbs. The `complete_recovery` path at lines 660-738 is
  wired through `aeat config recover`.
- `src/aeat/adapters/persistence/storage/master_key/_recovery.py` —
  the existing primitives (`generate_recovery_key`, `wrap_master_key`,
  `save_wrapped_master_key`, `encode_mnemonic`, `decode_mnemonic`,
  `unwrap_master_key`) are wired into new CLI handlers under
  `aeat config recover`, `aeat config show-recovery`, and
  `aeat config verify-recovery`. The module gains no new primitives;
  only the CLI plumbing is added.
- `src/aeat/application/wizard/_catalogue.py` and
  `src/aeat/application/wizard/_prompter.py` — new catalogue entries
  for passphrase double-confirm, data-loss-risk acknowledgement,
  recovery-code display, recovery-code confirm-by-retype, and the
  `--persist-recovery-wrap` opt-in screen. The prompter gains a
  no-echo secret-input mode for passphrase entry.
- Locale catalogues `locale/es/`, `locale/en/`, `locale/ca/` — every
  new operator-facing string from decisions 2, 4, 5, 7, and 8 is
  added. The verbatim sentence from decision 8 is reviewed for
  translation parity.
- `src/aeat/entrypoints/cli/_config/__init__.py` — new command bindings
  for `unlock`, `lock`, `rekey`, `show-recovery`, `verify-recovery`,
  and `recover --recovery-key`. The `aeat config set` verb gains the
  `idle-lock-minutes` and `keystore-cache` keys.
- `src/aeat/core/config.py` — the `aeat_secret_store_dir` default is
  preserved for headless deployments but the startup check from
  decision 3 refuses to operate when it resolves under the
  `aeat_database_url` parent. A new setting `aeat_idle_lock_minutes`
  (default 15) and `aeat_keystore_session_cache` (default false) are
  added.

### User-visible behaviour change — existing installs refuse to run

Every install that minted its master key under the silent auto-mint
path will refuse to operate on the first run of the new code. The
operator sees the typed error described in decision 9 and must back
up `var/` to cold storage before running `aeat config init` from
scratch. There is no migration tool. The operator's prior records
remain readable only via the cold-storage snapshot under the prior
release build.

### Irrecoverable-data scenario

If the operator loses BOTH the passphrase AND the 24-word recovery
code, the local working state is permanently unreadable. The AEAT
portal retains filed-declaration metadata addressable by CSV (decision
10) and is the legal record-of-truth for filings already submitted.
Pre-filing supporting documents (invoices, ledgers, working
calculations) held only in the local substrate are gone forever and
constitute a real exposure under LGT Art. 203 if AEAT requests them
during an inspection within the prescription window.

This is stated bluntly in the operator-facing copy at every enrollment
and recovery prompt per decision 8.

### Performance

Argon2id at the chosen parameters (memory cost 19 MiB, time cost 2,
parallelism 1) adds roughly 50 to 100 ms per unlock on a modern laptop
CPU. The unlock cost is incurred:

- Once per `aeat config init` (enrollment).
- Once per `aeat config unlock` after a lock or after idle-timeout
  expiry.
- Once per `aeat config rekey` (twice: unwrap with old passphrase,
  wrap with new).
- Once per `aeat config recover --recovery-key <words>` (HKDF on the
  mnemonic plus Argon2id on the new passphrase).

Between unlocks, the KEK is held in the `BucketSession` instance and
the per-call cost is zero. The latency budget for an unlocked
invocation is unchanged from today.

### Operational complexity

Three new operator-visible concepts: lock-and-unlock state, idle
timeout, recovery-code custody. The first two are handled by the
`BucketSession` instance and the idle-timeout config; the operator
interacts only via the `lock` and `unlock` verbs and the
`idle-lock-minutes` setting. The third (recovery-code custody) is
handled by the confirm-by-retype mandate at enrollment and the
operator-driven `verify-recovery` verb for periodic custody tests.

The substrate gains a new failure mode: an invocation can fail closed
because the session is locked. The error is typed and the message
points at `aeat config unlock`. The non-interactive escape hatch
(`AEAT_SECRET_PASSPHRASE` plus `--accept-data-loss-risk`) covers the
headless CI use case.
