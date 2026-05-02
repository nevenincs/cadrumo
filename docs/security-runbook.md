# Security operator runbook

The `aeat security` CLI exposes the operator-facing commands for the
secure-persistence substrate: provision, recover, key-export,
rotate-master-key, verify-corpus, migrate-master-key-kdf. This runbook
covers each, including the quiesce-then-act expectation that underpins
the per-file locking contract.

All commands act on **local disk only**. None touches a remote AEAT
service.

## First-run provisioning

```sh
aeat security provision [--backend {keyring,file,unsecured}] [--force]
```

Walks the operator through master-key minting and recovery-key generation.
The substrate refuses to clobber an existing master key without `--force`.

Backend choices:

- **`keyring`** (recommended): OS keychain (Touch ID / Hello / libsecret).
  Master key is stored in the OS keychain; no passphrase needed.
- **`file`**: passphrase-derived KEK (Argon2id) wraps a random 32-byte
  master key in `master.key`. Required for headless / CI installations.
- **`unsecured`**: testing-only mode that uses a published deterministic
  master key (zero confidentiality). Requires `AEAT_ALLOW_UNENCRYPTED=1`
  and refuses any operator profile with a real NIF/NIE/CIF.

After minting, the substrate displays a **24-word recovery key** ONCE.
**Print it. Store it somewhere safe.** Without the recovery key, a
forgotten passphrase or lost keychain means losing every persisted
record. The substrate persists a recovery-key wrapping at
`master.recovery.key` so future `aeat security recover` calls can
unwrap the master key from the mnemonic alone.

## Recovery from a lost passphrase / keychain

```sh
aeat security recover --recovery-key "<24 words>"
```

Unwraps the master key from `master.recovery.key` using the mnemonic,
then re-mints the file-fallback artefacts (`master.key` /
`master.kdf` / `salt`) under your new passphrase. Preserves the
master-key bytes so every existing on-disk record continues to
decrypt cleanly.

If you typed the mnemonic incorrectly, the helper exits with a clear
"did not unwrap" message and leaves the existing on-disk state
untouched. Retry with the correct words.

## Portable backup

```sh
aeat security key-export --out path/to/backup.json
```

Bundles the recovery wrapping plus the file-fallback artefacts into
a portable JSON file. Store off-site (cloud backup, encrypted USB
drive, paper printout). To restore on a new machine: copy the bundle
back into the configured `aeat_secret_store_dir`, then run
`aeat security recover` to re-mint the active backend state.

The export is itself ciphertext at rest — no new cryptography is
introduced; the export is a portable repackaging of the existing
wrapped state.

## Master-key rotation

```sh
aeat security rotate-master-key --old-key-file old.hex --new-key-file new.hex
```

Re-encrypts every governance envelope under the new master key **and**
re-wraps every blob-store DEK (data-encryption key) under the new
master key. Both scopes are visited in one invocation; the summary
table reports per-scope counts.

### Operator workflow

1. **Mint a new 32-byte master key**:

   ```sh
   python -c "import secrets; print(secrets.token_hex(32))" > new-key.hex
   chmod 0600 new-key.hex
   ```

2. **Quiesce the substrate**: stop every long-running `aeat`
   command, every editor that has the project open, and every test
   harness that touches the persistence layer. The rotation acquires
   `exclusive_file_lock` per envelope across the whole
   read+decrypt+re-encrypt+atomic-write sequence; concurrent
   repository writers will block on the same lock with the
   configured timeout.

3. **Run the rotation**:

   ```sh
   aeat security rotate-master-key \
     --old-key-file ./old-key.hex \
     --new-key-file ./new-key.hex
   ```

4. **Verify the per-scope summary**: both `rotated` and `skipped`
   counts are healthy; both `errors` columns are zero. The CLI exits
   non-zero if either scope reports errors.

5. **Decommission the old key**: move `old-key.hex` to a sealed
   offline backup, then overwrite the operating master-key source
   (keyring entry or file-fallback `master.key`) with the new key
   bytes.

### Resume idempotency

Re-running the command after a partial run is safe. Already-rotated
files / wrapped DEKs decrypt cleanly under the new key and land in
`skipped`. Operators can interrupt and resume without data loss.

### Note for installations rotated before the wave-18 hardening

Earlier substrate versions targeted the wrong directory when
walking secret-store DEKs (the helper pointed at `aeat_secret_store_dir`
rather than `aeat_blob_store_dir`). Installations that rotated under
those versions may have left their secret-store DEKs wrapped under
the old master key while the operator decommissioned that key.
After upgrading, run the rotation again under the corrected helper:

```sh
aeat security rotate-master-key \
  --old-key-file ./old-key.hex \
  --new-key-file ./new-key.hex
```

Use the SAME old/new key pair as the original rotation. The helper
is resume-idempotent — already-rotated files land in `skipped`,
secret-store DEKs that the previous run missed land in `rotated`.
The summary's `rotated` count for the secret-store should be
non-zero on the first re-run; subsequent re-runs report `skipped`
across the board.

## Corpus integrity verification

```sh
aeat security verify-corpus --corpus {casillas,manuals,normatives,vat}
```

Walks the named corpus root, computes a SHA-256 digest per file, and
compares the result against a recorded directory-level manifest
(`corpus.manifest.json`). Exit-1 on drift, missing sidecar, or
invalid manifest. Suitable as a pre-tag CI gate.

### Operator workflow

1. **Initialise the manifest** (first run only):

   ```sh
   aeat security verify-corpus --corpus casillas --regenerate
   ```

   This walks the corpus and writes the manifest sidecar.
   Commit `corpus.manifest.json` to the repository.

2. **Verify before tagging a release**:

   ```sh
   for c in casillas manuals normatives vat; do
     aeat security verify-corpus --corpus "$c"
   done
   ```

   Wire this into `just lint` / `just check` for CI.

3. **After an intentional corpus update**: re-run with
   `--regenerate` and commit the new sidecar in the same PR.

## KDF migration (scrypt → Argon2id)

```sh
aeat security migrate-master-key-kdf [--store-dir <path>]
```

Re-wraps the file-fallback master key from scrypt (v1) to Argon2id
(v2). Operators on the keychain backend (`aeat_secret_store_backend`
∈ `keyring` / `auto-with-keychain`) are unaffected; this command only
acts on file-fallback installations.

### Operator workflow

1. **Ensure the existing passphrase is reachable** — set
   `AEAT_SECRET_PASSPHRASE` in the environment, or be ready to type
   it at the interactive prompt.

2. **Run the migration**:

   ```sh
   aeat security migrate-master-key-kdf
   ```

   The summary table reports `migrated` (1 or 0) and `skipped` (1 if
   the store was already at v2).

3. **Verify normal operation**:

   ```sh
   aeat secrets list
   ```

   Should return without prompting for the passphrase a second time
   (the in-process cache works post-migration).

### Resume idempotency

Re-running the command on an already-v2 store reports
`skipped=1, migrated=0` and exits 0.

### Crash-recovery contract

The migration writes `master.key` first (under the Argon2id KEK),
then flips `master.kdf` to v2. A crash between those two writes
leaves a recoverable state: the next invocation of the migration
helper detects that the v2 KEK already unwraps `master.key` and
completes the transition by writing `master.kdf` alone. Operators
never get locked out of a half-migrated store.

## Quiesce-then-act expectation

All three commands expect the substrate to be **idle** at invocation
time:

- `rotate-master-key` holds `exclusive_file_lock` per envelope; a
  concurrent repository writer blocks until the rotation releases
  the lock (or vice-versa, blocking the rotation).
- `migrate-master-key-kdf` holds `exclusive_file_lock` on the master
  key path; a concurrent first-time `get_master_key` blocks.
- `verify-corpus` does not hold any lock but expects the corpus
  files to be stable across the walk + digest pass.

The substrate's repository writers all use the same lock timeout
(`DEFAULT_LOCK_TIMEOUT`); concurrent operations resolve correctly
but at the cost of wall-clock latency. For a clean operator
experience, stop the substrate before running any of these
commands.

## Quadlingual error surfaces

Every error raised by these commands carries an `aeat.core.errors`
registry code (e.g. `AUTH_STORAGE_MASTER_KEY_KDF_VERSION`,
`INTEGRITY_STORAGE_CORPUS_MANIFEST_TAMPER`) with es / en / ca / hu
messages through the project language contract. The CLI's error envelope renders the message in the
configured language (`AEAT_OUTPUT_LANGUAGE`).

## See also

- `.vault/adr/2026-04-30-secure-persistence-foundation-wave11-adr.md` — corpus integrity manifest design
- `.vault/adr/2026-04-30-secure-persistence-foundation-wave12-adr.md` — Argon2id KDF migration design
- `.vault/audit/2026-04-30-secure-persistence-foundation-wave15-16-audit.md` — review-feedback absorption + blob-store rotation closure
- Master-key rotation: see commit `bd12a7b` (initial wave-10 substrate) and the wave-16 SECURITY-CRITICAL extension that added blob-store DEK rotation.
