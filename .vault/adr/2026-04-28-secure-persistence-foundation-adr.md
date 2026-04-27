---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/adr/ location)
# Feature tag (replace secure-persistence-foundation with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#adr'
  - '#secure-persistence-foundation'
# ISO date format (e.g., 2026-02-06)
date: '2026-04-28'
# Related documents as quoted wiki-links
# (e.g., "[[2026-02-04-feature-research]]")
related:
  - "[[2026-04-28-secure-persistence-foundation-research]]"
  - "[[2026-04-27-secure-persistence-foundation-adr]]"
  - "[[2026-04-27-secure-persistence-foundation-exec]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `secure-persistence-foundation` wave-2 adr | (**status:** `accepted`)

## Problem statement

Wave 1 shipped the substrate. Wave 2 is the canary-consumer wave: it
must demonstrate the substrate works end-to-end by migrating the
project's plaintext credential surface to the secret store, action
the deferred MEDIUM/LOW findings from Wave-1's audit gate, and add
the operator-facing primitives (the `aeat secrets` CLI, the
NIF check-letter validator, the materialisation helper for
path-shaped consumers, and a tighter bearer-token redaction pattern)
that consumer migrations need.

## Considerations

Architectural drivers:

- The substrate's public API is `aeat.storage` only. Adapters consume
  the public surface; no module-internal access.
- Migrating from a plaintext-on-disk file to the secret store cannot
  be a flag-day cutover — the operator's existing credentials must
  continue to work. Adapters take a **read-through** approach: prefer
  the secret store, fall back to the legacy file with a one-shot
  deprecation log, and ship a one-shot migration helper that reads
  the legacy file and writes the secret store.
- Path-shaped consumers (Google's `service_account.Credentials.from_service_account_file`,
  any future Playwright `storage_state` usage) need a path on disk.
  The substrate writes ciphertext; the materialisation helper bridges
  the gap with a short-lived `0o600` tempfile context.
- The `aeat secrets` CLI is the operator-facing surface for
  inspecting / managing the store. It uses the existing CLI
  contract: `--json` flag (post-#399), trilingual error envelopes
  (post-#398), Typer `CliRunner`-tested.
- The NIF/NIE/CIF validator is a stand-alone primitive under
  `aeat.identity`. It is a prerequisite for the redaction-rule
  tightening (the substrate's `nif-hash` rule today over-matches and
  under-matches; tightening it requires a real validator). Lives
  outside `aeat.storage` because identity validation is a domain
  concern, not a persistence concern.
- The opaque-bearer-token redaction rule extends `aeat.storage._redaction`'s
  default registry. A new strategy is not required — `FINGERPRINT`
  is already defined; only the pattern is new.

## Constraints

- Python 3.13+, Windows-supported. No new runtime dependencies.
- Consumer test discipline: `CliRunner` for CLI tests; real on-disk
  persistence under `tmp_path`; real cryptography (no mocks).
- No Alembic migration in Wave 2 (the secret store is JSON-backed by
  Wave-1 design).
- The branch stays `feature/216-bank-import-persistence`; per-wave
  merges do not happen.
- Coverage floor 60% on `src/aeat` preserved.

## Implementation

### Phase 0 — trivial LOW findings (doc + rename only)

Action vs-L-1, vs-L-2, vs-L-5, vs-L-7, vs-L-8, vs-L-9, sec-L-1,
sec-L-6, sec-L-8: docstring additions, the duplicate
`_HKDF_CONTEXT_LOOKUP` rename to domain-prefixed names, the
`EncryptionMetadata` algorithm enum (close vs-L-8), and the lock-
helper retry-semantic note. No behaviour change; tests are added
where the documentation introduces a new public-surface contract.

### Phase 1 — MEDIUM findings

Action vs-M-1, vs-M-3, vs-M-4, vs-M-6, vs-M-7, sec-M-1, sec-M-2,
sec-M-3, sec-M-4, sec-M-5. Concretely:

- vs-M-1: normalise `_cached_master_key` keys via
  `Path.resolve()`.
- vs-M-3: rewrite `SecretStore._write_index` through `tempfile +
  os.replace` for atomic durability under crash.
- vs-M-4: route `EncryptedBlobStore.iter_manifests` through
  `load_envelope` so classification gating runs at iteration time.
- vs-M-6: add per-step debug logging in `_apply_migrators`; record
  the attempted migrator chain in the trailing
  `EnvelopeVersionError`.
- vs-M-7: cache HKDF-derived sub-keys on the instance for
  `HashedLookup` and `SecretStore`, keyed by the master-key bytes
  identity.
- sec-M-1: convert master-key + passphrase caches to `bytearray`
  with an `atexit` purge hook.
- sec-M-2: reorder `EncryptedBlobStore.delete` to remove payload
  before manifest, treating manifest-delete failure as the only
  fatal surface.
- sec-M-3: narrow `contextlib.suppress(Exception)` calls in
  `_secret_store.py` to typed tuples plus a WARNING log on
  unexpected branches.
- sec-M-4: emit a one-shot INFO log when `HashedLookup.compute`
  receives a plaintext shorter than 12 bytes.
- sec-M-5: assert the migrator chain is monotonic in
  `_apply_migrators`; raise `EnvelopeVersionError` on a non-
  monotonic step.

### Phase 2 — `materialise_secret` helpers

Add `aeat.storage.materialise_secret(key)` as a context manager
yielding a `Path` to a short-lived secure tempfile; the file lands
under the OS tempdir, is created with mode `0o600` (POSIX) via the
existing `_write_bytes_secure` helper, and is unlinked on context
exit. Add `aeat.storage.export_to_temp_path(key, *, prefix)` returning
a `(path, cleanup)` tuple for callers that need the path beyond a
single `with` block. Both consult the active secret store via
`aeat.storage.get_secret_store()` (also new in Wave 2; lazy factory
keyed by settings).

### Phase 3 — `aeat.identity` NIF/NIE/CIF validator

New module `aeat.identity._documents` with `IdentityDocument` enum
(`NIF` / `NIE` / `CIF`), the canonical check-letter table, and a
`validate_identity(value: str) -> IdentityDocument`. Public surface:
`aeat.identity.{validate_identity, IdentityDocument, IdentityError}`.
The new `IdentityError(AeatError)` registers an `ErrorCode`
(`INTEGRITY_IDENTITY_DOCUMENT`).

The substrate's `nif-hash` redaction rule's pattern stays
permissive (over-redaction is the safer failure mode); the new
validator is consumed by domain code that needs a strict yes/no.

### Phase 4 — opaque-bearer-token redaction

Add a new default rule `bearer-token-fingerprint` that matches the
non-JWT shape `(?i)(?:authorization:\s*)?bearer\s+[A-Za-z0-9._~+/=-]{20,}`
plus Google-style `ya29\.[A-Za-z0-9_-]{60,}`. Strategy is
`FINGERPRINT`. The default policy table for `SECRET`, `SESSION`,
`AUDIT`, and `DIAGNOSTIC` is extended to reference the new rule by
name.

### Phase 5 — `aeat secrets` CLI

New CLI namespace `aeat.cli.secrets` with four subcommands:

- `aeat secrets list [--json]` — dump every persisted lookup
  digest (plaintext keys are intentionally unrecoverable).
- `aeat secrets put <key> [--from-file PATH | --from-stdin]
  [--classification SECRET|SESSION] [--expires-in DURATION]` —
  persist a new secret. Operator supplies the natural key; the
  command writes through the active secret store.
- `aeat secrets rm <key>` — delete the record under `<key>`.
- `aeat secrets rotate <key> [--from-file PATH | --from-stdin]
  [--expires-in DURATION]` — replace the value while preserving
  classification + metadata.

The CLI inherits the post-#398 error decorator and the post-#399
`--json` schema registry. Tests use `CliRunner`; no plaintext
secrets in test fixtures (use `secrets.token_bytes` to generate).

### Phase 6 — `env/oauth-client.json` migration

New module `aeat.auth._secret_adapters` with
`load_google_oauth_client() -> dict[str, str]` that:

1. Tries `secret_store.get("aeat:google:oauth-client")` first.
2. On `SecretNotFoundError`, reads the legacy
   `env/oauth-client.json`, logs a one-shot INFO deprecation
   notice, and returns the parsed JSON.
3. Provides a sibling `migrate_google_oauth_client_to_secret_store()`
   that reads the legacy file, writes the secret store, and (with
   operator confirmation) deletes the legacy file.

The existing `aeat.cli.oauth` and `aeat.cli.auth` writers are
updated to write to the secret store directly when it is
available; they retain the legacy-file-write path behind a
deprecation log so existing automation still works.

### Phase 7 — `env/service-account.json` + workspace MCP migration

Same pattern as Phase 6, two consumers:
`aeat:google:service-account` and `aeat:mcp:workspace-credentials`.
The service-account JSON's path-shaped consumption (Google client
libraries) is handled via `materialise_secret`.

### Phase 8 — `aeat_token_dir / google_oauth_token.json` migration

The OAuth token cache is rotated more frequently than the
client/service-account credentials, so it gets its own
phase-isolated migration. Adapter consumed by
`aeat.auth.__init__`'s OAuth helpers; the cache key is
`aeat:google:oauth-token:<account>` so multi-account future work
slots in cleanly.

### Phase 9 — `env/.env` Cl@ve identity migration

Cl@ve identity values (NIF, fecha de validez del DNI) move to
`aeat:operator:profile` as IDENTITY-class records. The remainder
of `env/.env` (operational config, non-secret resource IDs) stays
in plaintext. The setup wizard is updated to write identity values
via the secret store.

### Phase 10 — Wave-2 audit gate

Identical contract to Wave 1: `vaultspec-code-review` + fresh OWASP
security audit. Cycle until no CRITICAL or HIGH finding remains;
emergent findings either close in Wave 2 or roll into Wave 3
research.

## Rationale

Phase ordering puts the deferred-finding cleanup first (Phases 0-1)
because every consumer migration depends on a clean substrate. The
materialisation helper (Phase 2) and the identity validator
(Phase 3) precede the operator CLI (Phase 5) because the CLI's
classification + validation behaviour relies on them. The
canary-consumer migrations (Phases 6-9) run last, in dependency
order, so each migration can land independently behind its own
green test suite.

The read-through adapter pattern is non-negotiable: a flag-day
cutover would brick existing operator installations. Read-through
plus a one-shot deprecation log gives the operator a smooth
upgrade path — they continue working, see the deprecation, and run
the migration helper at their convenience.

The classification choices map to the audit's recommendations:
SECRET for all credentials and refresh tokens; IDENTITY for
operator NIF / fecha; the new bearer-token redaction rule extends
the existing default policy table without breaking back-compat
because the rule list is keyed by stable rule names.

## Consequences

Positive:

- Every CRITICAL plaintext-credential location identified by the
  upstream audit has a **ciphertext-at-rest migration path** by the
  end of Wave 2: the substrate primitive (`SecretStore`), the
  read-through adapter (`load_secret_or_legacy`), and the migration
  helpers (`migrate_*_to_secret_store`) all ship under
  `aeat.auth._secret_adapters`. Operators run the migration helpers
  once per credential; the adapters then prefer the ciphertext store
  on every subsequent read. **The actual call-site rewires in
  `aeat.auth.__init__`, `aeat.cli.oauth`, and `aeat.cli.auth` are
  deliberately deferred** because each call site has a different
  test surface and a different deprecation cadence; the rewires
  land as a follow-up commit (Wave 2.1) or piggyback on the per-
  domain consumer migrations in Waves 3+.
- Operators get a typed CLI surface for inspecting and managing
  their secret store.
- The deferred Wave-1 findings are exhausted in Phases 0-1, leaving
  the substrate audit-clean as a baseline for downstream waves.
- The `materialise_secret` helper is a reusable primitive that
  Wave 4 (filing/submission) and Wave 5 (observability) can
  consume directly.

Negative:

- The legacy plaintext files must remain readable for several
  release cycles to support operators who upgrade incrementally.
  Wave 2 ships the deprecation log; a future ADR will set the
  removal milestone.
- The opaque-bearer redaction rule has heuristic patterns; over-
  redaction in user-supplied free text is possible. Tested via the
  existing redaction test suite; widened where false positives are
  observed in practice.
- The `aeat.identity` module adds a new public subpackage. Future
  domain code should consume it for any NIF parse / validate path
  rather than reinventing the algorithm.

Neutral:

- No new runtime dependencies.
- Wave 2 does not introduce any Alembic migration; the SQLite
  schema is unchanged.

## Out of scope

- Playwright `storage_state` migration (Wave 4 or later).
- `.aeat/live-submit-audit.log` relocation (Wave 4).
- Financial domain (Wave 3).
- Argon2id / SQLCipher / master-key rotation / per-profile keyring
  service identifiers (separate ADRs; deferred from Wave 1).
