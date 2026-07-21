---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S12'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Relocate the filing runtime repository behind its domain port in one atomic commit, deleting its pinned domain-to-adapters runtime_repository entry

## Scope

- `src/aeat/domain/filing/_runtime_repository.py`

## Description

- Move `resolve_filing_repository_bucket_id` and `secure_objects_for_filing_bucket`
  from the domain module into a new persistence-adapter sibling module,
  mirroring the modelos ports-inversion precedent for the equivalent
  runtime-helper relocation.
- Fix up both sibling repository adapters (draft and amendment) to import
  the runtime helpers from the new adapter-local sibling module instead of
  the domain-resident interim path each carried since its own relocation
  step; this closes the sole Family-1 cross-package private import the
  import-hygiene scan reported after the two prior steps.
- Delete the domain module entirely; the storage factory's import becomes a
  normal same-layer adapter-to-adapter module-level import, no longer
  deferred.
- Relocate the corresponding test file to the persistence-adapter test
  package, reclassify its pytest marker from the domain marker to the
  persistence-adapter marker, and route its imports through the public
  domain and storage facades rather than private submodules.
- Update a cross-reference in a distinct application-layer runtime-helper
  module's docstring to point at the new adapter home.
- Delete the stale domain-to-adapters pinned entry and the two stale
  domain-test ignore entries for the relocated test file from the
  import-linter ledger; retire the now-empty lazy-import allowlist bucket
  entry for the deleted module (the classification itself stays declared,
  now with zero entries); lower the total allowlist edge ceiling by one
  since this step is a net removal.
- Regenerate the apidocs stubs: add the new adapter stub, remove the stale
  domain module stub.

## Outcome

Commit `a43d1b0054` lands the relocation as one atomic, explicit-pathspec
commit of 12 files. This closes Phase W03.P08: all three filing repositories
(draft, amendment, and their shared runtime helpers) now live behind domain
ports in the persistence adapter, with zero production domain-to-adapters
pinned entries remaining for the filing surface. A full-tree
`pytest --collect-only` run reproduces clean (11992 tests, zero errors). The
domain/filing, application/filing, storage rotation, attached-repository
matrix, ephemeral-key-hygiene, review, custody-store-matrix, and the
relocated runtime-helper test suites pass (336 tests). The import-hygiene
scan reports zero Family-1 non-test cross-package private imports, closing
the deliberate interim edge the two sibling repository steps left open.

## Notes

None.
