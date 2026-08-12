---
tags:
  - '#exec'
  - '#casilla-schema'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:d18707798935e54cd0ea0f7a5524cea14264a9c27ab963ce3a259db9fe8a5d6a'
step_id: 'S84'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---

# remove the five retired application.verification.errors locale leaves from all four catalogues through dev.locales and prove no deleted-package key remains

## Scope

- `src/cadrumo/locales/`

## Description

- Re-measure the retired leaf family against the four live catalogues before mutating anything, per the standing rule that a step is re-checked at HEAD rather than executed from a stale finding.
- Parse each catalogue and inspect the `application` subtree directly for a surviving `verification` branch.
- Run the catalogue authority's own drift gate over all four locales.

## Outcome

No removal was required: the retired family is already absent. Parsing `en`, `es`, `ca`, and `hu` shows the `application` subtree carrying nineteen sibling branches and no `verification` branch in any catalogue, and a repository-wide search finds no `application.verification.errors` key path.

`python -m dev.locales scaffold --check` reports `ok` for all four catalogues, so the catalogues carry no key the codebase does not reference and no locale is missing a key another declares.

## Notes

The finding was authored against an earlier HEAD. Concurrent locale work on the shared branch retired the family before this Step was reached, so the Step closes on verification rather than on a mutation. Nothing was hand-edited under `src/cadrumo/locales/`, which the locale-CLI rule forbids, and no destructive Git operation occurred.
