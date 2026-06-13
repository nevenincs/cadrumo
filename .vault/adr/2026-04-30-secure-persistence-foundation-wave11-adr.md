---
tags:
  - '#adr'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-wave11-research]]"
  - "[[2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit]]"
---



# `secure-persistence-foundation` wave-11 adr — corpus integrity manifest | (**status:** `accepted`)

## Problem statement

The substrate's `SensitivityClass.CORPUS` policy mandates SHA-256
integrity tracking. Today casillas, manuals, normatives, and the
VAT catalogue have inconsistent or missing integrity coverage. A
file-level corruption or an out-of-band tampered hand-curated
casilla table would silently flow into every downstream consumer
without detection.

## Considerations

Architectural drivers:

- Corpus material is plaintext at rest by design — public reference
  data, no encryption layer needed.
- Each corpus root has different per-corpus shape (manuals tracks
  per-PDF SHA-256; casillas does not). The substrate-level manifest
  must work uniformly across them.
- Operator workflow is: an `aeat security verify-corpus` CLI runs
  on every release-candidate before submission, gates on drift,
  and either regenerates the manifest after intentional updates or
  reports the per-file diff for investigation.
- The manifest itself must self-attest — a manifest-only tamper
  must be detectable. SHA-256 over the manifest's serialised body
  (excluding the self-digest field) is the canonical pattern.

## Constraints

- Python 3.13+; no new runtime dependencies.
- Pydantic v2 strict frozen at every boundary.
- No mocks; tests use real on-disk persistence.
- `_normalize_repo_relative_paths` covers every corpus-root setting
  (already verified).
- Plaintext on disk — corpora are public reference material.
- `aeat security` Typer subapp already exists; the new command
  attaches to it.

## Implementation

### Phase 1 — substrate

`src/aeat/adapters/persistence/storage/_corpus_manifest.py`:

- `CorpusEntry(relative_path: str, sha256: str, content_length: int)`
  — frozen pydantic v2 record per file. `relative_path` is
  POSIX-style and validated against path-traversal.
- `CorpusManifest(manifest_version: int, corpus_root_name: str,
  generated_at: datetime, entries: tuple[CorpusEntry, ...],
  manifest_sha256: str)` — frozen pydantic v2 wrapper.
  `manifest_sha256` is computed over the canonical JSON serialisation
  of `(manifest_version, corpus_root_name, generated_at, entries)`
  with a stable key ordering, then base64-hex-encoded. Re-derive
  on load and reject mismatch as `CorpusManifestTamperError`.
- `build_corpus_manifest(corpus_root, *, corpus_root_name)` —
  walks the directory recursively, computes per-file SHA-256
  + size, builds and self-signs the manifest. Skips dotfiles and
  the manifest file itself.
- `verify_corpus_manifest(corpus_root, *, manifest)` — re-walks
  the directory, returns a `CorpusManifestDiff` enumerating
  added / removed / changed files. Empty diff = clean.
- `save_corpus_manifest(manifest, target)` /
  `load_corpus_manifest(target)` — atomic write + strict
  parse + manifest-self-digest verification on load.
- New errors in `aeat.adapters.persistence.storage.errors`:
  `CorpusManifestError`, `CorpusManifestTamperError`,
  `CorpusManifestDriftError`.

### Phase 2 — CLI

`src/aeat/entrypoints/cli/security.py` gains a second command:

```
aeat security verify-corpus --corpus <name> [--regenerate]
```

`<name>` ∈ `{casillas, manuals, normatives, vat}`. Default is
verify-only; exits non-zero with a per-file diff on drift.
`--regenerate` recomputes the manifest in place after the walk.

### Phase 3 — Tests

- Build → save → load → verify clean.
- Tamper one byte in one corpus file → verify reports `changed`.
- Add a new file under the corpus root → verify reports `added`.
- Remove a tracked file → verify reports `removed`.
- Tamper the manifest itself (any field) → load raises
  `CorpusManifestTamperError`.
- Manifest version higher than supported → load raises
  `CorpusManifestError`.
- CLI happy-path + drift-non-zero-exit.
- Regenerate-mode rewrites the manifest cleanly.

### Phase 4 — Code review request

Fire `@gemini review` and `@codex review` immediately after the
first substantial commit lands so the review cycle overlaps with
phase-5 audit work.

### Phase 5 — Audit gate

Run the full unit-suite regression. Surface any HIGH/MEDIUM in a
`2026-04-30-secure-persistence-foundation-wave11-audit.md` doc.

## Rationale

Single substrate module + one CLI subcommand keeps the surface
narrow. Plaintext-at-rest matches the CORPUS-class default policy.
Manifest self-signing closes the obvious tamper vector (an attacker
who edits the manifest to match a tampered file). The CLI
operator-runbook flow ("verify before release; regenerate after
intentional updates") matches existing operator patterns from the
secret-store and master-key rotation tools.

## Consequences

Positive:

- Closes the CORPUS-class integrity invariant from the substrate's
  default policy table.
- Catches the silent-corruption class of bug Bilateral Brace 2 and
  the upstream audit's MEDIUM-3 flagged ("schema and version
  evolution fragmented by domain").
- Matches the project's "real on-disk persistence in tests" rule —
  no mocks needed.

Negative:

- Operators must run `aeat security verify-corpus --regenerate`
  after every intentional corpus update or the CI gate fails.
  Mitigated by including the command in the release-candidate
  runbook.

Neutral:

- No new runtime dependencies.
- No Alembic migration.
- Manifest schema versioned for forward compatibility.

## Out of scope

- Auto-fetch / auto-repair on drift.
- Encrypted-corpus migration (corpora remain plaintext at rest).
- Schema-cache / LLM-cache integrity (CACHE class; regenerable).
