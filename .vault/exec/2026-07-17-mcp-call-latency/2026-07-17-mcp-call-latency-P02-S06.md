---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S06'
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
     The S06 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Read the shipped content-keyed manual text at runtime and remove the end-user pypdfium2 extraction so no install runs PDF text extraction and ## Scope

- `src/cadrumo/domain/calculations/registry/_validate_evidence.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Read the shipped content-keyed manual text at runtime and remove the end-user pypdfium2 extraction so no install runs PDF text extraction

## Scope

- `src/cadrumo/domain/calculations/registry/_validate_evidence.py`
- `src/cadrumo/domain/calculations/registry/tests/test_registry_reviewability.py`

## Description

Add `hashlib` import and `packaged_data` import from
`cadrumo.core.resources._boundary` to `_validate_evidence.py`.

Add three module-level constants: `_MANUAL_CORPUS_TEXT_DIR`,
`_CORPUS_PATH_PREFIX`, `_SIDECAR_SUFFIX` for the sidecar lookup path
derivation.

Add `_read_manual_pdf_sidecar(corpus_path, source_path) -> str | None`
function that: strips the `"corpus/"` prefix from `corpus_path`, builds a
`Traversable` via `packaged_data("manual_corpus_text", *sidecar_parts)`,
reads it, verifies the sha256 of `source_path`'s bytes against the sidecar's
`source_sha256` field, and returns `normalised_text` on a match, `None` on
any mismatch, parse failure, or missing sidecar.

Update the `manual_pdf` branch of `_source_text` to call
`_read_manual_pdf_sidecar` first.  On a non-`None` result assign
`normalised` directly; on `None` fall back to `_extract_pdf_text_impl` +
`normalise_corpus_text`.  Restructure the `else` branch to assign `normalised`
directly via `normalise_corpus_text(source_path.read_text(...))` (no
intermediate `text` variable) for consistency.

Enroll `_validate_evidence.py` in `_VALIDATOR_MODULE_LINE_BASELINES` at 360
in `test_registry_reviewability.py` because the new helper pushed the file
past the 300-line default cap.

## Outcome

`_source_text` for a `manual_pdf` source now reads the shipped sidecar (built
by `dev/packaging/extract_manual_corpus_text.py`) and verifies its sha256
before using it, eliminating the 18.2 s pypdfium2 first-touch extraction cost
from every end-user process.  Fallback to pypdfium2 is preserved for
development trees where a PDF may differ from the committed sidecar.  All
quality gates green.

## Notes

The sha256 is computed over `source_path.read_bytes()` at lookup time.  In
the common (matching) path this is a single file read of a few-megabyte PDF
— cheaper than pypdfium2 extraction by two orders of magnitude.  For
installed deployments the companion binary is already resolved by the existing
`resolve_companion_binary` call before `_read_manual_pdf_sidecar` is reached,
so the sha256 covers the companion-namespace bytes — same as the sidecar was
generated against.
