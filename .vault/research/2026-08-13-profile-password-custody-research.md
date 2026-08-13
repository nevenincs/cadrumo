---
tags:
  - '#research'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:09ea798caf4973972ba66cc040f1b1da19e8914272e104cb58cc71a24429c566'
related: []
---

# `profile-password-custody` research: `custody authority incident and option space`

The incident asks which durable authority can guarantee the product's normal profile flow: select a profile, enter its password, and unlock it. The current store-wide master-key provider, runtime `AUTO` routing, manifest recovery mirror, and optional keyring session cache do not form one durable per-profile authority. The evidence favors an independently password-wrapped profile data-encryption key, with recovery and keyring material kept outside normal-login authority. The ADR must settle its exact format, transactions, restore, deletion, and hard-cutover boundaries.

## Findings

### Runtime provider choice can diverge from enrollment custody

The implementation exposes a store-wide `FileFallbackMasterKeyProvider`, master-key records, and keyring-backed custody through one provider package rather than a durable profile-owned authority (`src/cadrumo/adapters/persistence/storage/master_key/__init__.py:1`). Git history records three repairs to AUTO/keyring split-brain behavior: commits `cf0414481611a819bcd193367b01867ea65b9601`, `ed32e783fca6d4de1b54963d0f6ecfec73058af4`, and `15e70a6aac126dfac1b8954e8a28475a7b3f4821`. Those repairs reduce individual failure modes but cannot make a runtime availability probe identify the provider that enrolled an existing profile.

### Current authority is store-scoped while the user contract is profile-scoped

The file provider persists `master.key` and `master.kdf`, and the application custody facade describes access to those store-level artifacts (`src/cadrumo/application/user_profile/_custody.py:27`). Bucket manifests carry public KDF parameters and a recovery-enrollment mirror (`src/cadrumo/adapters/persistence/storage/bucket/_manifest.py:133`). Multiple profiles therefore depend on shared custody state even though profile selection and password entry express an independent profile boundary.

### Recovery currently crosses the normal profile aggregate

Recovery status is read from its envelope and then mirrored into the active manifest through a separate write (`src/cadrumo/application/user_profile/_custody.py:154`, `src/cadrumo/application/user_profile/_custody.py:225`). Sealed archives also condition their member count and payload on optional `recovery.wrap` material (`src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_reader.py:227`). This coupling lets missing or damaged optional material affect otherwise valid password custody or backup completeness unless the new format separates the authorities.

### Password-derived independent profile custody fits the security boundary

NIST treats cryptographic keys as lifecycle objects whose protection, backup, recovery, and destruction require explicit controls. OWASP recommends authenticated encryption for stored data and Argon2id for password-derived protection. NIST's current password guidance permits Unicode and password managers and rejects composition-rule dependence. These sources support a bounded password KDF, authenticated wrapping, independent recovery, and explicit lifecycle transactions; they do not prescribe this product's file layout.

### The viable options have distinct failure domains

- A shared root key wrapped once per profile password preserves one cryptographic blast radius: compromise, loss, or rotation mistakes can still affect every profile.
- A shared root key that wraps per-profile keys improves data separation but leaves root custody necessary, so a valid profile password is not independently sufficient.
- A random per-profile key wrapped directly by that profile's password isolates profiles and password rotation. It requires per-profile transaction, backup, and recovery records.
- Direct password-derived data encryption avoids a wrap record but makes password or KDF rotation require full data re-encryption and complicates crash recovery.

The third option best matches the stated unlock contract, subject to the ADR defining optional recovery, stable key identity, rollback limits, supervised KDF execution, and hard-cutover refusal.

### OS session storage can accelerate but cannot own durable access

Python keyring is an abstraction over platform credential stores whose availability and behavior depend on the selected backend. Windows Job Objects can enforce process-tree and resource limits for supervised KDF workers, while POSIX process groups and resource limits provide the corresponding boundary. The repository already carries an executable Job Object precedent (`packaging/mcpb/build.py:207`), and the base runtime has `argon2-cffi` and authenticated-encryption support (`pyproject.toml:34`). Keyring can therefore remain a bounded session optimization without becoming the only durable copy of a profile key.

### Scope not investigated

This research did not attempt to recover production secrets, read retired artifact contents, design DEK rotation, or prove coherent offline rollback detection without an external monotonic witness. It also does not decide the architecture; the related ADR cluster owns those choices.

## Sources

- `src/cadrumo/adapters/persistence/storage/master_key/__init__.py:1`
- `src/cadrumo/application/user_profile/_custody.py:27`
- `src/cadrumo/application/user_profile/_custody.py:154`
- `src/cadrumo/application/user_profile/_custody.py:225`
- `src/cadrumo/adapters/persistence/storage/bucket/_manifest.py:133`
- `src/cadrumo/adapters/persistence/storage/bucket/_sealed_archive_reader.py:227`
- `packaging/mcpb/build.py:207`
- `pyproject.toml:34`
- Commits `cf0414481611a819bcd193367b01867ea65b9601`, `ed32e783fca6d4de1b54963d0f6ecfec73058af4`, and `15e70a6aac126dfac1b8954e8a28475a7b3f4821`
- https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final
- https://pages.nist.gov/800-63-4/sp800-63b.html#passwordver
- https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html
- https://keyring.readthedocs.io/en/latest/
- https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
