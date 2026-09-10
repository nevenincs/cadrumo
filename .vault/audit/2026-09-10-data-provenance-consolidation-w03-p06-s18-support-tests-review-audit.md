---
tags:
  - '#audit'
  - '#data-provenance-consolidation'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:afe3bf345a163a339cd4fab60dd0185ef8435bad236a1b046ee5bd4c2ce8f673'
related:
  - "[[2026-09-10-data-provenance-consolidation-plan]]"
---

# `data-provenance-consolidation` audit: `w03 p06 s18 support tests review`

## Scope

Reviewed the S18 removal of projection-specific support fixtures and assertions, and the catalog-backed temporary-corpus detector coverage retained after S17.

## Findings

### stale-catalogue-detector | medium | The retained missing-identity assertion does not exercise the synchronizer path

`test_an_artefact_without_an_official_catalog_identity_is_refused` compiles a catalogue, mutates the manifest afterwards, and passes that deliberately stale object to `_authority_failures`. The production `check` path recompiles the catalogue from the same manifest immediately before invoking that helper, so the stated missing-identity failure cannot occur through the exercised production flow. Keep an isolated detector that drives `check` and proves a catalog-backed identity failure reachable through its current API, or remove this helper-only assertion if no such production state exists.

## Recommendations

- Keep catalog identity defect tests on the production `check` path. The unreachable helper-only assertion was removed during this review cycle; the isolated unclassified-payload and conflicting-identity tests continue to execute `check` directly.
