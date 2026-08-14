---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d84b9224a0e7064fdd6300b79ef1f934612ad61ac60665d7c7ca238d5a3d1554'
step_id: 'S69'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Adjudicate root conftest and explicit-import support factories and remove substitute owners

## Scope

- `conftest.py`
- `src/cadrumo/tests`

## Description

- Inventory root conftest and every explicit-import fixture/support owner in the central
  harness.
- Compare repeated names and bodies against import timing, scope, lifecycle, authority,
  data shape, visibility, and current consumers.
- Retain owners whose superficially similar implementation encodes a distinct contract.

## Outcome

Root conftest declares no fixtures. The central harness has four explicit-import fixture
objects with one canonical definition each: the two LLM secure-runtime fixtures,
`isolated_storage_root`, and `isolated_cli_backend`. Their apparent body/name neighbors
differ by bucket identity, activation, yielded value, root geometry, or visibility.

The root storage-root formula remains intentionally stdlib-only because it must execute
before importing any Cadrumo test support. Locale managers, registry CLI support,
`portal_path`, and committed justificante caching also retain distinct scope, authority,
or process-lifetime contracts. No substitute owner was found, so no code deletion was
authorized. Independent review confirmed the adjudication.

## Notes

The live census reported 642 fixtures and 28 root/central records; the checked manifest
remains stale for the following drift step. Forty-four relevant collection items
resolved, and representative encrypted-runtime and portal behavior passed. Semantic RAG
was unavailable, so exact census and source discovery supplied the fallback evidence.
