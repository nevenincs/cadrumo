---
tags:
  - '#plan'
  - '#module-test-coverage'
date: '2026-06-01'
modified: '2026-06-01'
tier: L1
related:
  - "[[2026-05-31-coverage-canonicalisation-audit]]"
  - "[[2026-06-01-envelope-conformance-gate-adr]]"
  - "[[2026-06-01-metastate-zero-tolerance-adr]]"
  - '[[2026-06-04-module-test-coverage-adr]]'
  - '[[2026-06-04-module-test-coverage-research]]'
---

# `module-test-coverage` plan

Close the coverage-canonicalisation audit findings: retire the
`COVERAGE_GAPS` allowlist in favour of an AST import-graph helper,
and reach every production module from a test via either pairing,
transitive import, or rationale-carrying `_EXEMPTIONS` entry.

## Steps

- [x] `S01` - land the AST import-graph helper alongside the legacy filename pairing check; `src/aeat/test_every_module_has_test_coverage.py` (commit `6173f349b`).
- [x] `S02` - close the four genuinely uncovered modules surfaced by the new helper; production modules missing test reachability (commit `df4b537c0`).
- [x] `S03` - author fixture-generator smoke tests; `tests/fixtures/borrador/test_generate.py`, `tests/fixtures/financial/n26/test_generate.py`, `tests/fixtures/justificantes/test_generate.py`, and `tests/fixtures/pdf_corpus/l3_synthetic/_generators/`.
- [x] `S04` - cover attachment service helpers against real storage; `src/aeat/domain/attachments/test_service.py`.
- [x] `S05` - delete the deprecated docstring stub; `src/aeat/domain/attachments/_repository.py`.
- [x] `S06` - retire the coverage allowlist and legacy filename pairing check; `src/aeat/test_every_module_has_test_coverage.py` (commit `f36a82118`).
- [x] `S07` - drop the orphan API documentation stub; `docs/api/aeat.domain.attachments._repository.rst` (commit `e17d830ee`).
- [x] `S08` - append closure note; `2026-05-31-coverage-canonicalisation-audit` (commit `b64a4b563`).

## Verification

Plan complete. Gate runs unconditionally with no allowlist;
`_EXEMPTIONS` is a closed set of nine entries each carrying inline
durable rationale per the `metastate-zero-tolerance-adr`. Symmetric
no-allowlist principle ratified in
`envelope-conformance-gate-adr` for the parallel CLI ↔ schema
registry surface.
