---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/research/ location)
# Feature tag (replace secure-persistence-foundation with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#research'
  - '#secure-persistence-foundation'
# ISO date format (e.g., 2026-02-06)
date: '2026-04-28'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-plan]]")
related:
  - "[[2026-04-27-secure-persistence-foundation-exec]]"
  - "[[2026-04-27-secure-persistence-foundation-adr]]"
  - "[[2026-04-27-secure-persistence-foundation-research]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-persistence-foundation` wave-2 research

## Origin

Wave 1 of the long-lived secure-persistence-foundation feature shipped
the substrate (research → ADR → plan → 12 implementation phases →
audit gate). The audit gate exhausted four HIGH findings (master-key
file permissions, passphrase env-var hygiene, keyring no-op-backend
detection, per-service cache) and closed. The substrate is in place;
no domain consumer has yet migrated.

This Wave-2 research artifact opens the next phase of the long-lived
PR. Its job is to produce the architecture for migrating the project's
**plaintext secret persistence surface** to the substrate's secret
store, and to action the inherited MEDIUM / LOW findings from the
Wave-1 audit gate that were rolled forward.

The wave's success criterion: every CRITICAL plaintext-credential
location identified by the upstream 2026-04-27 security storage audit
is migrated to the secret store, and the original plaintext file is
either replaced by a thin adapter that reads from the store or is
removed outright.

## Wave-2 candidate consumer surface

The 2026-04-27 audit identified the following plaintext credential
files as the CRITICAL leak surface. Each is a Wave-2 migration
candidate:

- `env/oauth-client.json` — Google OAuth client credentials (client
  ID + client secret). Currently written by `aeat oauth-client` and
  `aeat auth` flows; consumed by `aeat.auth.__init__` and
  `aeat.cli.bootstrap`. Migration target: SECRET-class record under
  the natural key `aeat:google:oauth-client`. Adapter: a thin
  read-through helper in `aeat.auth.__init__` that consults the secret
  store first, falls back to the legacy file with a deprecation log.
- `env/service-account.json` — Google service-account private key
  JSON. Same shape as above; natural key
  `aeat:google:service-account`.
- `aeat_token_dir / google_oauth_token.json` — OAuth refresh +
  access tokens. Currently atomic-written by `aeat.auth.__init__`.
  Migration target: SECRET-class records under
  `aeat:google:oauth-token:<account>`; the account discriminator
  permits multi-account future support without re-architecting.
- `env/.env` — Cl@ve identity values (NIF, fecha de validez del DNI,
  Google resource IDs). Identity-bearing rather than secret-bearing in
  the strict sense; the audit graded this HIGH-3. Migration target:
  IDENTITY-class records under `aeat:operator:profile`. The non-
  secret fields (resource IDs) remain in the env file because they are
  legitimately operational config, not identity material.
- `env/workspace-mcp-credentials` — workspace MCP credential cache.
  SECRET-class; natural key `aeat:mcp:workspace-credentials`.

Playwright `storage_state` and the `.meta.json` sidecars under the
token directory are session-bearing rather than long-lived secret;
session-persistence-review-audit (2026-04-17) hardened their handling
already (TTL, certificate-thumbprint binding, eager invalidation on
probe failure, Windows ACL hardening). Migrating them to the secret
store as SESSION-class records is structurally trivial but operationally
disruptive (Playwright wants a path, not bytes). **Defer to Wave 4 or
later** so the canary wave can demonstrate end-to-end success on the
five consumers above without coupling to the Playwright file-format
contract.

## Standing constraints inherited from Wave 1

- The substrate's public API is `aeat.storage` only. Consumer adapters
  import from the public surface; no direct module-internal access.
- Every adapter respects the secret store's retention policy: SECRET
  records MUST carry an `expires_at` (the audit's recommendation —
  use a generous default, e.g. 90 days, with explicit rotation hooks
  in subsequent waves).
- The substrate's classification primitive governs the adapter's
  classification choice; Wave-2 consumer migrations adopt the
  defaults except where a per-record override is justified in writing.
- No new error classes unless a consumer truly needs one; reuse the
  substrate's existing registered codes.
- Tests use real cryptography, real on-disk persistence under
  `tmp_path`, real SQLAlchemy in-memory engines, real
  `multiprocessing.spawn` for cross-process tests. No mocks.
- The trilingual error-message contract continues to apply.
- `.aeat/live-submit-audit.log` relocation is **deferred to Wave 4**
  (filing/submission wave) because the live-submit audit emits
  context that is filing-domain-shaped; co-locating the relocation
  with the filing-state migration is cleaner than orphaning it in the
  secret-canary wave.

## Inherited audit-finding backlog

The Wave-1 audit gate deferred the following MEDIUM and LOW findings
into Wave-2 research input. Each is tagged with its origin (the
vaultspec-code-reviewer pass = `vs-*`; the OWASP security-audit pass
= `sec-*`).

### MEDIUM (Wave-2 in scope)

- vs-M-1: `Path` setting subscript collision risk for the
  `_cached_master_key` dict — normalise paths via `.resolve()` before
  caching.
- vs-M-2: read-back-after-set verification on the keyring backend
  (already partially closed in commit `0629d0c` via the round-trip
  read; tighten to byte-equality assertion documentation pass).
- vs-M-3: secret-store index file is not atomic. Mirror
  `save_envelope`'s tempfile + `os.replace` pattern.
- vs-M-4: `iter_manifests` skips classification gate. Either route
  through `load_envelope` or document the inventory-only intent
  explicitly.
- vs-M-5: `decrypt_record` error category clarity. Cosmetic
  documentation pass.
- vs-M-6: `_apply_migrators` skip-on-mismatch ergonomics. Add a
  per-step debug log + diagnostic context to the trailing
  `EnvelopeVersionError`.
- vs-M-7: HKDF sub-key caching. The substrate currently re-derives
  per call; cache on the instance to save scrypt + HKDF cycles in hot
  paths.
- vs-M-8: doc-only — `safe_subpath` docstring should mention the
  `.` segment rejection inherited from `_paths.py`.
- sec-M-1: bytearray-based key zeroisation + atexit hook. Move
  caches to mutable buffers and provide a `purge()` classmethod.
- sec-M-2: blob delete ordering. Delete payload first, then
  manifest; treat the manifest delete failure as the only fatal
  surface.
- sec-M-3: narrow `contextlib.suppress(Exception)` calls in
  `_secret_store.py` to a typed tuple plus a WARNING log on any
  unexpected branch.
- sec-M-4: HashedLookup low-entropy plaintext warning at bind time
  for plaintexts shorter than ~12 bytes.
- sec-M-5: envelope migrator-chain monotonic-version assertion.
- sec-M-6: passphrase normalisation cosmetic — `\r\n` strip is
  closed in commit `0629d0c`; document the behaviour.

### LOW (Wave-2 opportunistic)

- vs-L-1: `EncryptedBlob.ciphertext` `min_length=GCM_TAG_SIZE`
  documents empty plaintext; add a docstring note.
- vs-L-2: `BlobManifest.content_type` non-validation — document.
- vs-L-3: regex pre-compilation in `_redaction._apply_one` via
  `functools.lru_cache`.
- vs-L-4: recursive `redact()` for structured payloads (dict / list).
- vs-L-5: rename duplicated `_HKDF_CONTEXT_LOOKUP` constants to
  domain-prefixed names for grep clarity.
- vs-L-6: secret-store delete blob-cleanup logging.
- vs-L-7: lock helper retry-semantic docstring update.
- vs-L-8: encryption metadata algorithm enum.
- vs-L-9: typed encryption-present payload placeholder.
- vs-L-10: cross-process lock test timeout widening.
- sec-L-1: ciphertext min-length docstring note.
- sec-L-2: blob-manifest `model_validator` triad pin.
- sec-L-3: NIF / NIE / CIF regex tightening; check-letter validator
  under `aeat.identity` (separate from audit redaction).
- sec-L-4: opaque OAuth bearer-token redaction pattern.
- sec-L-5: trailing-punctuation handling on URL host-only redaction.
- sec-L-6: Windows lock advisory-vs-mandatory documentation.
- sec-L-7: fsync sweep across atomic-write call sites.
- sec-L-8: `PathContainmentError` MRO doc note.

### INFO (rolled forward, no Wave-2 action required)

- vs-INFO-1..3 and sec-INFO-1..5 are reference notes; no code
  change. They land in subsequent ADRs as appropriate.

## Tech-stack survey for Wave-2 consumer migration

The migration adapter pattern needs to handle two cases:

1. **Bytes-shaped consumers** — modules that accept the secret as a
   bytestring (most OAuth-token consumers). The adapter is trivial:
   `secret_store.get(key).value`.
2. **Path-shaped consumers** — modules that demand a path on disk
   (Google auth's `service_account.Credentials.from_service_account_file`,
   Playwright's `storage_state` parameter). The adapter materialises a
   short-lived secure tempfile (POSIX 0o600, deleted on context exit),
   yields its path to the consumer, and unlinks on completion.

For the path-shaped case, a context-managed helper
`secret_store.materialise_secret(key)` that yields a `Path` and unlinks
on exit is the cleanest contract. The tempfile lives under the OS
tempdir; on POSIX it gets `0o600` mode bits via the same
`_write_bytes_secure` helper from Wave 1. On Windows, `icacls.exe`
hardening (already in use for the Playwright session-state files) is
the analogue.

Alternative: `secret_store.export_to_temp_path(key, *, prefix)` that
returns the path and an explicit `cleanup()` callable, avoiding the
context-manager overhead for callers that need the path beyond a
single `with` block.

Decision deferred to the Wave-2 ADR.

## Wave-2 plan shape (preview)

The Wave-2 plan will run in roughly the following phase order:

- Phase 0: action the trivial Wave-1 LOW findings (vs-L-1, vs-L-2,
  vs-L-5, vs-L-7, vs-L-8, vs-L-9, sec-L-1, sec-L-6, sec-L-8 — all
  documentation or constant renames).
- Phase 1: action the Wave-1 MEDIUM findings (vs-M-1, vs-M-3, vs-M-4,
  vs-M-5, vs-M-6, vs-M-7, vs-M-8, sec-M-1, sec-M-2, sec-M-3, sec-M-4,
  sec-M-5).
- Phase 2: secret-store materialisation helpers
  (`materialise_secret` context manager + `export_to_temp_path`).
- Phase 3: NIF-class regex tightening + check-letter validator
  (sec-L-3) under `aeat.identity` — this is a stand-alone
  prerequisite for downstream waves that consume identity validation.
- Phase 4: opaque-bearer-token redaction pattern (sec-L-4).
- Phase 5: `aeat secrets` CLI surface (`list`, `put`, `rm`,
  `rotate`) with the trilingual error-envelope contract; tested via
  `CliRunner`.
- Phase 6: migrate `env/oauth-client.json` to the secret store under
  `aeat:google:oauth-client`. Adapter pattern: read-through with
  legacy-file fallback + deprecation log. Migration helper for the
  one-shot move.
- Phase 7: migrate `env/service-account.json` and
  `env/workspace-mcp-credentials` (same pattern).
- Phase 8: migrate `aeat_token_dir / google_oauth_token.json` to
  SECRET-class records keyed by `aeat:google:oauth-token:<account>`.
  Adapter consumed by `aeat.auth.__init__`'s OAuth token cache helpers.
- Phase 9: migrate `env/.env` Cl@ve identity values to IDENTITY-class
  records under `aeat:operator:profile`. The remainder of `env/.env`
  remains operational plaintext.
- Phase 10: substrate-level smoke + Wave-2 audit gate
  (`vaultspec-code-review` + fresh OWASP security audit).

## Out of scope for Wave 2

- Playwright `storage_state` migration (Wave 4 or later, coupled to
  Playwright file-format contract).
- `.aeat/live-submit-audit.log` relocation (Wave 4, coupled to filing
  state).
- Financial domain (Wave 3).
- Argon2id KDF migration (separate ADR; the deferred decision from
  Wave 1).
- SQLCipher revisit (separate ADR; deferred from Wave 1).
- Master-key rotation flow (separate ADR; deferred from Wave 1).
- Per-profile keyring service identifiers (separate ADR; deferred
  from Wave 1).

## Open audit-finding inventory at Wave-2 entry

Identical to the Wave-1 audit-gate-deferred backlog above. The
Wave-2 ADR will commit to a phase ordering and re-classify any items
that turn out to be load-bearing for the canary consumer migrations.
