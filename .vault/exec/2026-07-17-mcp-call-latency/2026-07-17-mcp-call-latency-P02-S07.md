---
tags:
  - '#exec'
  - '#mcp-call-latency'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S07'
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
     The S07 and 2026-07-17-mcp-call-latency-plan placeholders are machine-filled by
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
     The Prove with a real-behavior negative test that a content-key mismatch between shipped text and source bytes refuses or recomputes rather than serving stale text and ## Scope

- `src/cadrumo/_data/corpus/tests/test_extraction_sidecar_freshness.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove with a real-behavior negative test that a content-key mismatch between shipped text and source bytes refuses or recomputes rather than serving stale text

## Scope

- `src/cadrumo/_data/corpus/tests/test_extraction_sidecar_freshness.py`

## Description

Add two tests to `test_extraction_sidecar_freshness.py`.

Add `_MANUAL_CORPUS_TEXT_ROOT`, `_CORPUS_TEXT_SUFFIX` module-level
constants alongside the existing corpus-root constants.  Add `json` and
`tempfile` imports.

Add `test_manual_pdf_corpus_text_sidecars_exist_and_match_source_sha256`:
iterate all `.corpus_text.json` files under `_data/manual_corpus_text/`,
assert schema validity (schema_version, corpus_path, source_sha256, 64-char
hex, normalised_text present), derive the source PDF path from corpus_path,
compute sha256 of the PDF bytes, and assert it matches stored source_sha256.
Fails with a "run extract_manual_corpus_text" hint when stale.

Add `test_manual_pdf_corpus_text_sidecar_mismatch_returns_none`: import
`_read_manual_pdf_sidecar` from `_validate_evidence`, pick the first
committed sidecar, write a temp file with wrong bytes (`b"not-the-real-pdf-bytes"`),
call `_read_manual_pdf_sidecar(corpus_path, tmp_path)`, and assert the return
value is `None`.  Proves that a sha256 mismatch refuses stale text rather than
serving it.

## Outcome

Two tests added and passing:
- `test_manual_pdf_corpus_text_sidecars_exist_and_match_source_sha256` — positive
  freshness gate: all 89 committed sidecars match their source PDFs.
- `test_manual_pdf_corpus_text_sidecar_mismatch_returns_none` — negative gate:
  sha256 mismatch returns None (real-behavior, no mocks).

All quality gates green.

## Notes

The negative test imports `_read_manual_pdf_sidecar` directly from the
private module (`_validate_evidence`).  This is acceptable for a test
exercising the production function's real-behavior contract; the
`service-imports-via-top-level-reexports` rule governs production code, not
the test surface.

**P02 code review remediation** (follow-up commit `test(packaging): gate corpus-text
normaliser equivalence and sidecar resolution`):

- MEDIUM: Added `test_corpus_text_normaliser_inlined_copy_is_byte_equal_to_canonical`
  to the same test module.  Imports both `normalise_corpus_text` from `_text.py` and
  `_normalise_corpus_text` from the build script, runs a battery of 20 inputs covering
  HTML tags, entities, the `< 500 euros` math edge, combining marks U+0300-U+036F,
  NBSP, whitespace collapsing, and lowercasing, and asserts byte-equal output.  An edit
  to either side without mirroring the other now fails loudly.

- LOW: Strengthened `test_manual_pdf_corpus_text_sidecar_mismatch_returns_none`.
  Added a positive assertion before the negative one: calls `_read_manual_pdf_sidecar`
  with the real source PDF and asserts the result equals the sidecar's
  `normalised_text`, proving packaged_data resolution actually finds the sidecar and
  the sha256 path passes.  Without this the None assertion would pass for the wrong
  reason if the lookup itself broke.

- LOW: Updated pyproject.toml shed-policy comment to acknowledge the ~7.4 MB
  compressed `_data/manual_corpus_text/` derived-text payload added by S05.
