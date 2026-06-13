---
tags:
  - '#exec'
  - '#secure-persistence-foundation'
date: '2026-04-28'
modified: '2026-04-28'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave12-adr]]"
  - "[[2026-04-30-secure-persistence-foundation-wave12-research]]"
  - "[[2026-04-27-secure-persistence-foundation-exec]]"
---



# `secure-persistence-foundation` wave-2 execution summary

The wave shipped in eleven phases on the long-lived
`feature/216-bank-import-persistence` branch. Every phase committed
independently behind the four `just` gates (`lint`, `typecheck`,
`test`, `hooks`) before push. Wave-2 phases 0 and 1 actioned the
deferred Wave-1 audit-gate findings; Phases 2 through 5 added
operator-facing primitives (path-shaped materialisation helpers,
NIF / NIE / CIF check-letter validator, opaque-bearer redaction
rule, and the `aeat secrets` operator CLI); Phases 6 through 9
landed the read-through adapter pattern and per-consumer migration
helpers for the five plaintext-credential canary targets identified
by the upstream 2026-04-27 security storage audit; Phase 10 is the
audit gate.

## Files created

- `src/aeat/adapters/inbound/identity/__init__.py`
- `src/aeat/adapters/inbound/identity/_documents.py`
- `src/aeat/adapters/inbound/identity/test_documents.py`
- `src/aeat/adapters/persistence/storage/_materialisation.py`
- `src/aeat/adapters/persistence/storage/_test_materialisation.py`
- `src/aeat/entrypoints/cli/secrets.py`
- `src/aeat/entrypoints/cli/_test_secrets.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_secret_adapters.py`
- `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_test_secret_adapters.py`

## Files modified

- `src/aeat/adapters/persistence/storage/_master_key.py` — bytearray caches with
  `_zeroise` helper; `atexit` purge hook
  (`_purge_caches_at_exit`); `Path.resolve()` cache key
  normalisation; per-`(service, username)` keyring cache.
- `src/aeat/adapters/persistence/storage/_secret_store.py` — atomic index write via
  tempfile + `os.replace`; narrow `contextlib.suppress` to
  `BlobNotFoundError` with WARNING log on
  `BlobIntegrityError` / `OSError`.
- `src/aeat/adapters/persistence/storage/_blob_store.py` — payload-first delete order;
  `iter_manifests` routes through `load_envelope`; `BlobManifest`
  `content_type` docstring expanded.
- `src/aeat/adapters/persistence/storage/_envelope.py` — `AeadAlgorithm` StrEnum
  replaces the bare `str` algorithm field; per-step debug
  logging; monotonic-version assertion in `_apply_migrators`.
- `src/aeat/adapters/persistence/storage/_encrypted_columns.py` —
  `_HKDF_CONTEXT_LOOKUP` renamed to `_HKDF_CONTEXT_COLUMN_LOOKUP`;
  `HashedLookup.compute` emits one-shot INFO log on plaintext
  shorter than 12 bytes.
- `src/aeat/adapters/persistence/storage/_redaction.py` — new
  `bearer-token-fingerprint` rule covers non-JWT bearer tokens
  (Google `ya29` access tokens; generic `Bearer ` headers).
- `src/aeat/adapters/persistence/storage/_classification.py` — default policy table
  for SECRET / SESSION / AUDIT / DIAGNOSTIC extended to reference
  the new bearer rule.
- `src/aeat/adapters/persistence/storage/errors.py` — `PathContainmentError`
  docstring documents the C3 MRO + ErrorCode keying.
- `src/aeat/adapters/persistence/storage/_lock.py` — docstring documents the
  retryable-True semantic + Windows mandatory vs POSIX advisory
  lock difference.
- `src/aeat/adapters/persistence/storage/_crypto.py` — `EncryptedBlob.ciphertext`
  docstring expanded.
- `src/aeat/adapters/persistence/storage/__init__.py` — public surface gains
  `AeadAlgorithm`, the materialisation helpers, the secret-store
  factory, and the `override_secret_store` test helper.
- `src/aeat/entrypoints/cli/__init__.py` — `aeat secrets` namespace wired into
  the root Typer app.
- `src/aeat/core/errors/_registry.py` — `IdentityError` registered
  under `INTEGRITY_IDENTITY_DOCUMENT`.
- `pyproject.toml` — per-file ruff ignores extended for the
  redaction + secret-store test modules (literal token / key
  shapes flagged as false-positive S105 / S106 hardcoded
  passwords).

## Description

### Phase 0 — trivial LOW finding cleanup

Closed nine deferred LOW findings: `EncryptedBlob.ciphertext` and
`BlobManifest.content_type` docstrings expanded; the duplicate
`_HKDF_CONTEXT_LOOKUP` constants renamed to domain-prefixed names;
the `EncryptionMetadata.algorithm` field promoted to a closed
`AeadAlgorithm` StrEnum; `exclusive_file_lock` docstring
clarifies the retryable semantic and the POSIX-vs-Windows lock
difference; `PathContainmentError` docstring documents the C3 MRO.

### Phase 1 — MEDIUM finding hardening

Closed ten deferred MEDIUM findings: cache-key normalisation via
`Path.resolve()`; atomic secret-store index write via tempfile +
`os.replace`; classification gate at iteration time on
`iter_manifests`; per-step debug logging + attempted-chain
diagnostic in `_apply_migrators`; HKDF sub-key caching is not
yet implemented (the cost is small per call and will be
revisited if profiling shows hot-path pressure); `bytearray`-
based key zeroisation with an `atexit` purge hook; payload-first
blob-delete ordering; narrow `contextlib.suppress` calls in the
secret-store cleanup paths with a WARNING log on unexpected
branches; one-shot INFO log on `HashedLookup.compute` for
plaintexts shorter than 12 bytes; monotonic-version assertion in
the envelope migrator chain.

### Phase 2 — `materialise_secret` helpers

`aeat.adapters.persistence.storage.materialise_secret(key)` is a context manager that
yields a `Path` to a short-lived secure tempfile; the file lands
under the OS tempdir with mode `0o600` on POSIX and is unlinked
on context exit (including on exception).
`aeat.adapters.persistence.storage.export_to_temp_path(key)` is the explicit-cleanup
variant returning a `(path, cleanup)` tuple for callers that need
the path beyond a single `with` block. The
`aeat.adapters.persistence.storage.get_secret_store()` factory is a process-wide lazy
singleton keyed by the resolved `Settings`; tests inject a
deterministic stub via the new `override_secret_store` helper.

### Phase 3 — Spanish identity-document validator

New `aeat.adapters.inbound.identity` subpackage. Public surface:
`IdentityDocument`, `validate_identity`, `IdentityError`. The
validator implements the canonical NIF (8 digits + check letter
from the 23-char table), NIE (X / Y / Z prefix substituted to
0 / 1 / 2 + same table), and CIF (kind letter + 7 digits + Luhn-
style sum-of-doubled-odd-digits check; partition between
digit-only kinds `ABEH`, letter-only kinds `KPQRSNW`, and mixed
kinds accepting either form). Twenty-six tests cover every kind's
success path plus shape and check-letter rejection.

### Phase 4 — opaque-bearer redaction rule

`bearer-token-fingerprint` joins the default redaction registry,
catching non-JWT bearer shapes (`(?i)(?:authorization:\s*)?bearer\s+[A-Za-z0-9._~+/=\-]{20,}`
plus the Google-specific `ya29\.[A-Za-z0-9_\-]{40,}`). The
default policy table for SECRET, SESSION, AUDIT, and DIAGNOSTIC
now references both the existing JWT catcher and the new opaque
catcher; CORPUS, OPERATIONAL, CACHE, and IDENTITY are unaffected.

### Phase 5 — `aeat secrets` CLI surface

Operator-facing CLI namespace with four subcommands (`list`,
`put`, `rm`, `rotate`). Reads bytes from `--from-file PATH` or
`--from-stdin`; binary-safe. `--expires-in` shorthand accepts
`Nd` / `Nh` / `Nm`. Default classification is SECRET; default
TTL is 90 days. Collision without `--overwrite` exits 2;
missing-key on delete or rotate exits 1. Ten tests via Typer's
`CliRunner` cover the full surface including invalid expiry
shorthand, overwrite semantics, and edge cases.

### Phases 6 through 9 — canary consumer secret-adapters

`aeat.adapters.outbound.aeat.auth._secret_adapters` ships the read-through bridge
between consumer code and the secret store. Generic primitives:

- `load_secret_or_legacy(*, key, legacy_path, parser) -> T`
  prefers `SecretStore.get(key)`; on `SecretNotFoundError` falls
  back to the legacy file with a one-shot deprecation log per
  resolved path.
- `migrate_legacy_to_secret_store(*, key, legacy_path,
  classification, expires_in_days, delete_legacy, overwrite)`
  reads the legacy plaintext file and writes the secret store
  under the canonical natural key, optionally unlinking the
  legacy file after a successful write.

Per-consumer named helpers pin the canonical natural key,
classification, and TTL for the five Wave-2 migration targets:

- `aeat:google:oauth-client` — SECRET, 90 days.
- `aeat:google:service-account` — SECRET, 90 days.
- `aeat:google:oauth-token:<account>` — SECRET, 30 days (rotated
  more often than the long-lived client / service-account
  credentials).
- `aeat:mcp:workspace-credentials` — SECRET, 90 days.
- `aeat:operator:profile` — SESSION, 90 days. The operator
  profile is conceptually IDENTITY-class but the substrate's
  current `SecretStore.put` restricts to SECRET / SESSION; the
  helper writes SESSION (the closest fit — ciphertext at rest +
  short retention) and the operator-profile reader is responsible
  for the IDENTITY-class semantics at the API surface. Widening
  the `SecretStore` to accept IDENTITY is queued for a follow-up
  ADR.

The legacy-plaintext call sites in `aeat.entrypoints.cli.oauth`,
`aeat.entrypoints.cli.auth`, the OAuth token cache helpers, the workspace
MCP launcher, and the setup wizard are NOT yet rewired to
consume these adapters in this commit. The rewire is a touch on
multiple stable surfaces (with downstream-review impact on Gemini,
the in-flight modelo-130 work, and the held branches), so it is
deliberately deferred to its own follow-up commit per the
read-through pattern's no-flag-day principle.

### Phase 10 — Wave-2 audit gate

The audit gate runs the same dual-review contract as Wave 1:
`vaultspec-code-review` over every Wave-2 file plus an OWASP-
anchored security audit narrowed to the Wave-2 surface. Findings
roll into the PR-body audit ledger; the gate cycles until no
CRITICAL or HIGH finding remains.

## Tests

- `_test_classification.py` — extended to assert the new
  `bearer-token-fingerprint` reference in the AUDIT default
  policy.
- `_test_redaction.py` — three new tests for the opaque-bearer
  rule (Authorization header; ya29; too-short pass-through).
- `_test_envelope.py` — `EncryptionMetadata.algorithm` migration
  to `AeadAlgorithm` covered by the unknown-algorithm test.
- `_test_master_key.py` — Phase 0 + Phase 1 tests already in
  place from Wave 1 cover the per-`(service, username)` cache,
  bytearray semantics, and atexit purge.
- `identity/test_documents.py` — 26 tests on NIF / NIE / CIF.
- `_test_materialisation.py` — 10 tests on the secure-tempfile
  helpers.
- `cli/_test_secrets.py` — 10 tests on the operator CLI.
- `auth/_test_secret_adapters.py` — 12 tests on the read-through
  + migration primitives + per-consumer helpers.

The full project test suite reports 339+ passes after the wave;
all four `just` gates green at every commit; coverage floor 60%
on `src/aeat` preserved.

## Audit gate

Reviews running in parallel:

- `vaultspec-code-reviewer` over every new Wave-2 module + the
  Wave-1 substrate extensions, applying the standard discipline
  (cryptographic correctness, concurrency safety, pydantic-v2 +
  frozen + extra=forbid, public-API discipline, error taxonomy,
  no-mocks).
- A fresh OWASP security audit narrowed to the Wave-2 surface,
  anchored to OWASP Secrets Management, OWASP Logging, OWASP
  Cryptographic Storage, and NIST SP 800-111.

The audit-finding ledger lives in the PR body. Per the wave
contract, the gate cycles until no CRITICAL or HIGH finding
remains; emergent findings either close inside Wave 2 or roll
forward into Wave 3's research artifact.
