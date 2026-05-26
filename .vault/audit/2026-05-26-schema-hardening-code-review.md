---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-26'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `schema-hardening` Code Review

<!-- Persistent log of audit findings appended below. -->

REVIEW-2026-05-26-001 | INFO | P06.S16 reference-section split review passes

Reviewed the P06.S16 diff for the registry reference-validator split. No LOW,
MEDIUM, HIGH, or CRITICAL issues were found.

The change keeps `_check_all_id_references` as the snapshot entrypoint and
moves construct, dependency-classification, algorithm, export-layout, and
binding-selector section walkers into `_validate_reference_sections.py`. The
delegation order, checker calls, lazy binding-selector import, diagnostic
prefixes, and accumulated failure behavior are preserved.

Verification reviewed:

- Ruff passed for the touched Python modules.
- Referential-integrity tests passed.
- Selector-shape plus referential-integrity tests passed together.
- Vault plan status and plan convention checks passed.

Residual risk:

- The primary commit risk is staging omission for the new helper module; the
  final commit must stage `_validate_reference_sections.py` with the import
  change.

REVIEW-2026-05-26-002 | MEDIUM | P06.S17 fragment inventory test missed omitted revision sources

Initial review found that the committed-corpus fragment inventory assertion
derived expectations only from already-discovered revision sources. That would
not catch a regression where discovery omitted an entire `revisions/<id>/`
directory or `revisions/<id>.toml` file.

The test was corrected to derive the expected TOML inventory independently from
the filesystem under each directory-mode `revisions` directory and compare it
to the union of discovered `fragment_paths`. Re-review marked the finding
resolved.

Verification reviewed:

- Ruff passed for `test_loader_directory_mode.py`.
- `test_loader_directory_mode.py` passed with 23 tests.
