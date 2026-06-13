---
tags:
  - '#research'
  - '#secure-persistence-foundation'
date: '2026-04-30'
modified: '2026-04-30'
related:
  - "[[2026-04-30-secure-persistence-foundation-upstream-reconciliation-audit]]"
  - "[[2026-04-27-security-storage-audit-audit]]"
---



# `secure-persistence-foundation` wave-11 research — corpus integrity manifest

## Question

The substrate's default policy table marks
`SensitivityClass.CORPUS` as plaintext-acceptable at rest, on the
condition that "integrity (SHA-256) MUST still be tracked". Today the
project's two CORPUS-class on-disk roots
(`aeat_casillas_root`, `aeat_manuals_root`) have inconsistent
integrity coverage:

- Manuals tracks per-record SHA-256 via `FetchedManualPart` in
  `src/aeat/domain/manuals/_schema.py:296`. Each fetched PDF carries a
  64-char hex digest, content length, fetched timestamp, and
  source URL.
- Casillas catalogue files at
  `corpus/casillas/<modelo>/<period>.json` have NO file-level
  integrity record. The file is loaded via
  `src/aeat/domain/casillas/catalogue.py:110:load_casillas` which only
  validates the pydantic shape; a corrupted or tampered casilla
  table parses as long as the JSON shape is valid.

The CORPUS-class invariant requires a directory-level manifest that
covers every file under the corpus root with a SHA-256 + size + last-
verified-at timestamp, plus a self-attesting `manifest_sha256` so
tampering with the manifest itself is detectable.

## Findings

### Per-record integrity in `manuals/`

The manual fetcher writes a `manifest.json` next to each
`source.pdf` containing one `FetchedManualPart` record. That covers
the fetched-bytes integrity for the PDF blob but not:

- The structured-record JSON files (Sections, Rules) that downstream
  code consumes via `aeat.domain.manuals.load_manual`. These are the
  product of an extraction pipeline; their integrity today rests on
  the pydantic schema parse and on the `manuals_review_required`
  flag.
- Cross-file consistency (no manifest exists that says "this corpus
  has 47 manuals at these paths with these hashes").

### No integrity in `casillas/`

`corpus/casillas/<modelo>/<period>.json` files are loaded through
`load_casillas` with no checksum gate. A bit-flip in one of the
hand-curated casilla tables would parse without error and silently
flow through every downstream consumer (the filing builder, the
review queue's casilla lookup, etc.) until a casilla-id mismatch
trips elsewhere.

### Other corpus-shaped roots

The codebase has a few additional CORPUS-class roots worth covering
under the same manifest contract:

- `aeat_normatives_root` — BOE / sede normative texts catalogue.
- `aeat_vat_catalogue_root` — VAT-rate corpus.
- `aeat_schema_cache_dir` — extracted modelo schemas (CACHE class
  per the policy table; integrity tracking is a should-have rather
  than a CORPUS-class must-have).

The first two should land in the same manifest contract; the
`schema_cache_dir` is a cache (can be regenerated from BOE) so it
is intentionally out of scope.

### Substrate primitives that already exist

- `aeat.adapters.persistence.storage.derive_key` / `encrypt_record` are not relevant
  here — corpus material is plaintext at rest.
- `hashlib.sha256` is the project's stable digest primitive (used
  by `aeat.domain.financial.transactions.derive_transaction_id`,
  `aeat.domain.justificante`'s `source_pdf_sha256`, etc.).
- `aeat.core.paths.resolve_record_json_path` is the existing path-
  containment validator — relevant when an operator passes a
  corpus name on the CLI.

## Recommended scope

1. **Substrate**: a single `aeat.adapters.persistence.storage._corpus_manifest` module
   defining `CorpusEntry`, `CorpusManifest`, and helpers
   `build_corpus_manifest(corpus_root)`,
   `verify_corpus_manifest(corpus_root, manifest)`,
   `save_corpus_manifest(manifest, target)`,
   `load_corpus_manifest(target)`. Manifest is plaintext JSON
   (corpus material is plaintext at rest).
2. **CLI**: `aeat security verify-corpus --corpus <name>
   [--regenerate]` covering `casillas`, `manuals`, `normatives`,
   `vat`. `--regenerate` rewrites the manifest after walk; the
   default is verify-only with a non-zero exit on any drift.
3. **Tests**: build → verify happy path; tampered-file mismatch;
   missing-file mismatch; new-file (untracked) mismatch;
   manifest-self-tamper detection; manifest-version-too-new gate.

## Out of scope

- Schema-cache integrity (CACHE class; can be regenerated).
- LLM cache integrity (CACHE class; ditto).
- Encrypted corpus blobs (corpora are plaintext at rest by design).
- Auto-fetch / auto-repair on drift (the verify command reports;
  the operator decides whether to re-extract or restore).
