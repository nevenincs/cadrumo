---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S05'
related:
  - "[[2026-07-17-mcp-call-latency-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace mcp-call-latency with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S05 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Extract the eleven bundled AEAT manual PDFs to normalised text once at build time and commit content-keyed sidecars hashed on source bytes, extending the existing extraction-sidecar pipeline and ## Scope

- `dev/docs/preprocess/_html.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extract the eleven bundled AEAT manual PDFs to normalised text once at build time and commit content-keyed sidecars hashed on source bytes, extending the existing extraction-sidecar pipeline

## Scope

- `dev/packaging/extract_manual_corpus_text.py` (new)
- `src/cadrumo/_data/manual_corpus_text/` (89 new `.corpus_text.json` sidecar files)

## Description

Implement `dev/packaging/extract_manual_corpus_text.py` as a stdlib-only build module
that recursively finds every PDF under `src/cadrumo/_data/corpus/`, extracts text via
pypdfium2 using the same page-iteration logic as `_extract_pdf_text_impl`, normalises
it with an inlined copy of `normalise_corpus_text` (avoids triggering the cadrumo
package import chain and pydantic settings initialisation), and writes a
content-keyed JSON sidecar at
`src/cadrumo/_data/manual_corpus_text/<path-relative-to-corpus>.corpus_text.json`.

Content key is sha256 of the source PDF bytes — survives installation across
environments where size and mtime change.  Sidecar schema: `schema_version`,
`corpus_path` (`corpus/<relative-posix>`), `source_sha256`, `normalised_text`.

Add `--check` mode that exits non-zero when any sidecar is stale or missing without
writing, suitable for a CI freshness gate.

Run the extractor; generate 89 sidecars covering all corpus PDFs (the 11
`manual_pdf`-kind registry references plus instruction PDFs, normatives PDFs, and
AEAT forms).

Pass all quality gates: ruff check, ruff format, ty check, and
`test_registry_reviewability.py`.

## Outcome

`dev/packaging/extract_manual_corpus_text.py` ships as a runnable module
(`python -m dev.packaging.extract_manual_corpus_text [--check]`).  89 sidecar files
committed under `src/cadrumo/_data/manual_corpus_text/`, each embedding the sha256 of
its source PDF.  The inline normalisation function is byte-identical to the production
`normalise_corpus_text` in `_text.py`.  All gates green.

## Notes

The build script intentionally does not import from the `cadrumo` package namespace.
Importing `normalise_corpus_text` from `cadrumo.domain.calculations.registry._text`
would trigger `cadrumo/__init__.py` → pydantic `Settings()` initialisation → a
`FormerProductStateError` when an `aeat.db` legacy database exists in the environment.
The inline copy sidesteps this; a comment in the file mandates keeping it in sync with
`_text.py` when the normalisation logic changes.
