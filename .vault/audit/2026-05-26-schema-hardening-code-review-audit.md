---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` Code Review


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

REVIEW-2026-05-26-003 | INFO | P06.S18 loader genericity audit passes

Reviewed the loader fragment-support audit. No LOW, MEDIUM, HIGH, or CRITICAL
issues were found.

The loader continues to describe generic source layouts using `ModeloSource`,
`ModeloRevisionSource`, `single_file`, `directory`, `revision_file`, and
`fragment_directory`. The audit found no per-modelo branches for M100, M200,
M303, M349, or other modelo ids.

Verification reviewed:

- Text search over `_loader.py` found only generic `modelo_id` bookkeeping and
  fragment-layout code.
- Runtime discovery reported M100 and M200 through fragment-directory sources,
  M131 through revision-file sources, and M130 through single-file source
  layout.
- S17's loader-directory tests cover filesystem-vs-discovery fragment
  inventory drift.

REVIEW-2026-05-26-004 | INFO | P06.S19 fragmentation target evidence passes

Reviewed the next-target evidence for modelo fragmentation. No LOW, MEDIUM,
HIGH, or CRITICAL issues were found.

The evidence selects M131 because it has the largest remaining tracked TOML
file and four revision-file revisions, with the 2026 revision only four lines
below the current fragment line cap. M100, M200, and M303 are already
fragment-directory layouts; M130 is large but single-revision.

Verification reviewed:

- Evidence was derived from tracked TOML paths via `git ls-files`.
- No registry TOML files were modified.
- The next implementation target is framed as generic directory fragmentation,
  not a per-modelo loader definition.
