---
tags:
  - '#audit'
  - '#security-crypto-swarm-2026-05-30'
date: '2026-05-30'
modified: '2026-05-30'
related: []
---



# security-crypto-swarm-2026-05-30 audit: cryptography and encryption surfaces

## Scope

Axis 1 of 6 in the recurring multi-agent security audit swarm. Read-only review of the AEAT at-rest crypto stack: `SecureObjectRepository`, the encrypted column decorators, the file-backed `Envelope` and `CipherEnvelope` formats, the master-key and DEK-wrap providers, KDF parameters, OAuth and Cl@ve Móvil persisted state, certificate password handling, hash usage for content addressing, and constant-time comparison discipline. No source files were modified.

The overall posture is unusually strong: every at-rest path runs through AES-256-GCM with HKDF-SHA256 sub-key derivation and AEAD-bound AAD, the passphrase KDF is Argon2id at OWASP-current top-tier parameters, nonces are sourced from `secrets.token_bytes`, the unsecured backend is fenced behind a hostile-named env gate plus a NIF-canary, and the OS keychain provider proves persistence with a round-trip read. The findings below are best-practice gaps and one HIGH-confidence smell rather than exploitable vulnerabilities.

## Findings

### MEDIUM | src/aeat/adapters/persistence/storage/master_key/_master_key.py:1281-1285 | published-key unsecured backend bleeds key bytes into source

The unsecured backend hard-codes `_UNSECURED_PUBLISHED_KEY = b"AEAT_UNSECURED_TEST_KEY" + b"\x00" * 9` as a Final module-level constant and uses it as both the KEK and the DEK in `_provider_enter` (line 1332). Combined with the inline comment that this key "provides ZERO confidentiality", the design is intentional, but it permanently locates a real cryptographic key in the source tree where greps, screenshots, and future refactors can copy it into log lines or test fixtures. The NIF-canary at `_refuse_unsecured_active_bucket_with_real_profile` (line 1161) defends the production data path, but the canary fails open on `sqlite3.Error` (line 1185-1186) — a malformed DB file silently downgrades to "no profile to check" and allows unsecured activation. Tighten the canary to fail-closed on any DB read error, and consider moving the published key into a settings-resolved value with a build-time check rather than a `Final` constant.

### MEDIUM | src/aeat/adapters/persistence/storage/crypto/_encrypted_columns.py:204-260 | HashedLookup HMAC key derived with empty salt

`HashedLookup._derive_lookup_key` calls `derive_key(key_material=master_key, salt=b"", context=_HKDF_CONTEXT_COLUMN_LOOKUP)` with an empty salt for HKDF-SHA256. The deterministic-lookup property is intentional, but with no salt every consumer that shares the active master key produces identical HMAC sub-keys, and the derived key is the same across processes for the same plaintext. The docstring warns against low-entropy plaintexts; that warning is correct but unenforced — a low-entropy column (e.g. an enumeration) would leak its distribution to anyone with read access to the SQLite file. Either inject a per-deployment salt sourced from the bucket manifest, or add a runtime guard that refuses to register `HashedLookup` on columns whose declared cardinality is bounded.

### MEDIUM | src/aeat/adapters/persistence/storage/master_key/_master_key.py:294-296 | best-effort zeroisation is not actually called on key buffers

`_zeroise` is documented as "called on every cached buffer at shutdown" via an atexit hook (line 282-296), but the actual master-key bytes returned by `get_master_key()` (line 1442) and the wrapped DEK bytes (line 1237) are immutable `bytes` objects produced by `secrets.token_bytes` and `AESGCM.decrypt`. The atexit hook can only zeroise `bytearray` buffers, and no such bytearray is ever populated with the master key in this module. The "memory zeroisation" defense is therefore documentation, not behaviour. Either remove the misleading comment, or refactor the key cache to hold `bytearray` buffers and copy out on use.

### LOW | src/aeat/adapters/outbound/storage/_google_drive.py:685-686 | Drive integrity falls back to MD5

`md5 = entry.get("md5Checksum")` is the only integrity check applied to Drive payloads on pull; when present, content_hash is set to `f"md5-{md5}"`, otherwise to the literal string `"sha256-unverified"`. Google Drive exposes only MD5 over its v3 API, so the choice is forced, but the "sha256-unverified" sentinel is silent — a caller that expects a sha256 hash will get a string that looks plausible and never raises. Surface the unverified state as a typed flag on the metadata record rather than embedding it in the hash string, so consumers cannot accidentally pattern-match on the `sha256-` prefix.

### LOW | src/aeat/adapters/outbound/aeat/auth/_session_store.py:96-98 | storage-state SHA-256 used for tamper-detection without HMAC

`_storage_state_sha256` is a plain `hashlib.sha256(payload).hexdigest()` over the JSON-serialised Playwright storage state, and the Cl@ve Móvil resume path compares it to a metadata-carried value (`_clave_movil.py:1064`). Since both the storage state and the metadata are stored inside the same encrypted SecureObjectRepository record, an attacker who can mutate one can mutate the other, so the comparison is best understood as a corruption check rather than a tamper check. The plain `==` comparison on hex strings (line 1064) is not constant-time. Use `hmac.compare_digest` for the comparison and rename the field to make the corruption-vs-tamper distinction explicit in the API.

### LOW | src/aeat/adapters/persistence/storage/master_key/_master_key.py:332-353 | passphrase env var read without `pop` widens subprocess inheritance

The docstring at line 320-342 explicitly chooses to keep `AEAT_SECRET_PASSPHRASE` in `os.environ` for legitimate re-read paths. The reasoning is sound, but the consequence is that every subprocess spawned by the application — including third-party tools invoked via `subprocess.run` for diagnostics, browser launches via Playwright, or shell-outs from CLI verbs — inherits the master-key passphrase in its environment block. On Windows the env block is visible to any same-user process via `NtQueryInformationProcess`. Add an explicit scrub at every subprocess boundary (pass `env=` rather than inheriting), and document the inheritance posture in the operator security model.

### LOW | src/aeat/adapters/persistence/storage/master_key/_master_key.py:830-841 / 904-912 | mint write order recoverable but not journaled

Both `_mint_new` and `complete_recovery` write `master.key`, `master.kdf`, and `salt` as three independent atomic-replace operations under the same `master.lock`. A crash between writes leaves a "torn state" detected at next load (line 706-720), with a clear operator runbook. The substrate refuses to re-mint on torn state, which is the right call. Consider adding a journal sidecar (`master.pending.json` with the planned triple) written before the first replace and unlinked after the third, so the recovery runbook can distinguish "torn during mint" from "torn during recovery" without relying on operator memory.

## Recommendations

Prioritise the unsecured-backend canary fail-closed fix (MEDIUM, finding 1) and the `HashedLookup` empty-salt question (MEDIUM, finding 2) — both are structural and warrant a small ADR. The zeroisation discrepancy (MEDIUM, finding 3) is a documentation honesty fix unless the team chooses to commit to real key zeroisation. The four LOW findings are best-practice hardening that can land as a single hygiene PR.

Summary: 0 HIGH, 3 MEDIUM, 4 LOW — total 7 findings.
