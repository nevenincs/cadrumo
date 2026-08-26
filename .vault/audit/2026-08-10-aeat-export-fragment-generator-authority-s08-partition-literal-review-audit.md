---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:781b82682cb12ef0bd1eed32a85cd17879aa9f1a699f671f5143d96670c5e1f1'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-s08-independent-review-audit]]"
---
# `aeat-export-fragment-generator-authority` audit: `S08 partition and literal review`

## Scope

Independent formal review of the owned `W02.P03.S08` delta in `dev/registry/_export_tree.py`, `dev/registry/tests/test_export_tree.py`, and the `ENCODING_ALIAS_MAP` facade promotion in `src/cadrumo/domain/calculations/registry/__init__.py`. The review covered deterministic greedy same-record partitioning from actual `rtoml` bytes, repository reviewability limits, filename stability, complete logical preflight before writes, source-order and exactly-once field emission, strict loader equality, exact official literal-byte authority and refusal, public import boundaries, no-shim discipline, and exclusion of the deferred S32 render-profile and provenance-profile integration.

Focused evidence was green for the 22 renderer tests, scoped Ruff check and format, scoped BasedPyright, the facade `__all__` hygiene test, direct public import of `ENCODING_ALIAS_MAP`, and `git diff --check`. The complete import-hygiene file did not finish within 124 seconds, so only the focused facade gate is claimed for the initial review.

## Findings

### s08-partition-stability | medium | The first fragment filename changes when a record grows past one part

`_record_relative_path` emits an unnumbered filename when `part_count == 1`, but emits `-part-001` for the same first fragment once the record crosses the partition limit. Therefore a source record growing from one reviewable fragment to two renames its existing fragment even when the original leading fields and their serialized bytes are unchanged. The new stability test proves that later-record filenames survive a preceding record's repartitioning, but it does not compare the same record's one-part filename with its first filename after growth. This violates the stable record/part filename requirement and creates avoidable generated-tree churn; it does not alter loaded field semantics.

Remediation re-review: closed. `_record_relative_path` now always emits `-part-{part:03d}`, including `part-001` for a one-part record. The real-filesystem test directly proves that the compact record's first filename equals the oversized multipart record's first filename, that the following record filename is unchanged, that every part remains under 1,400 lines and 520 characters per line, and that the loader result is strictly equal to the rendered layout with all 245 source-ordered fields emitted exactly once. The only additional check-suite changes are the two matching hardcoded generated filenames in `dev/registry/tests/test_generated_tree_check.py`. Independent post-fix verification completed with 36 exporter/check tests passing, scoped Ruff check and format clean, scoped BasedPyright at zero errors, warnings, and notes, and scoped `git diff --check` clean. The broader reported snapshot also completed 142 development-registry unit tests with 24 configured deselections, 38 focused loader, facade, and reviewability tests, and the full import-hygiene run with 35 passes plus 6 failures outside the S08 files. No HIGH or MEDIUM finding remains in this review scope.

## Recommendations

- Make the first-fragment naming invariant across the one-part to multi-part transition, either by numbering every record fragment from `part-001` or by retaining the unsuffixed base filename as part one and numbering only additional parts. Extend the real-filesystem test to compare that filename before and after appending enough fields to force a second part, while preserving the existing later-record stability and strict loader-equality assertions.

Remediation status: satisfied by invariant `part-001` naming and the direct compact-to-oversized stability assertion; no further S08 action is required from this audit.
