---
tags:
  - '#plan'
  - '#module-test-coverage'
date: '2026-06-01'
tier: L1
related:
  - "[[2026-05-31-coverage-canonicalisation-audit]]"
  - "[[2026-06-01-envelope-conformance-gate-adr]]"
  - "[[2026-06-01-metastate-zero-tolerance-adr]]"
---

# `module-test-coverage` plan

Close the coverage-canonicalisation audit findings: retire the
`COVERAGE_GAPS` allowlist in favour of an AST import-graph helper,
and reach every production module from a test via either pairing,
transitive import, or rationale-carrying `_EXEMPTIONS` entry.

## Steps

- [x] `S01` - land the AST import-graph helper alongside the legacy
  filename pairing check; `src/aeat/test_every_module_has_test_coverage.py`.
  Landed in commit `6173f349b`.
- [x] `S02` - close the four genuinely-uncovered modules surfaced by the
  new helper. Landed in commit `df4b537c0`.
- [x] `S03` - author smoke tests for the three fixture-generator
  modules (`tests/fixtures/borrador/test_generate.py`,
  `tests/fixtures/financial/n26/test_generate.py`,
  `tests/fixtures/justificantes/test_generate.py`) plus four
  L3-synthetic generator smoke tests under
  `tests/fixtures/pdf_corpus/l3_synthetic/_generators/`.
- [x] `S04` - author `src/aeat/domain/attachments/test_service.py`
  covering the three service helpers against a real
  `AttachmentStore` and `isolated_runtime_profile`.
- [x] `S05` - delete the deprecated `src/aeat/domain/attachments/_repository.py`
  docstring stub; zero importers verified.
- [x] `S06` - retire the 66-entry `COVERAGE_GAPS` allowlist, the
  legacy `_has_paired_test` filename pairing check, and the two
  paired legacy tests. Canonical gate becomes
  `test_every_production_module_is_reachable_from_a_test`;
  `_EXEMPTIONS` retained with 9 narrow rationale-carrying entries
  (browser-only dependency, `_lazy()` Typer subcommand, `python -m`
  entry point, CLI integration shim). Landed in commit `f36a82118`.
- [x] `S07` - drop the orphan `docs/api/aeat.domain.attachments._repository.rst`
  stub after the corresponding production module was removed.
  Landed in commit `e17d830ee`.
- [x] `S08` - append closure note to
  `2026-05-31-coverage-canonicalisation-audit`. Landed in commit
  `b64a4b563`.

## Verification

Plan complete. Gate runs unconditionally with no allowlist;
`_EXEMPTIONS` is a closed set of nine entries each carrying inline
durable rationale per the `metastate-zero-tolerance-adr`. Symmetric
no-allowlist principle ratified in
`envelope-conformance-gate-adr` for the parallel CLI ↔ schema
registry surface.
