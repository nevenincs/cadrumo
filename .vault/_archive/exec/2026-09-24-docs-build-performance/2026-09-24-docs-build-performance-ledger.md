---
tags:
  - '#exec'
  - '#docs-build-performance'
date: '2026-09-24'
modified: '2026-09-25'
body_schema: 'body-v2'
body_hash: 'sha256:5cee54f82e145ff18e0c1df1e5c5c2ba02223d761a0754a28d38c2c2585b1815'
related:
  - "[[2026-09-24-docs-build-performance-plan]]"
---

# `docs-build-performance` ledger

## Changes

- `S01` `A` `dev/docs/navigation.py`
- `S01` `A` `dev/docs/tests/test_navigation.py`
- `S01` `M` `docs/conf.py`
- `S01` `verify:` `pytest dev/docs/tests/test_navigation.py` -> `pass`
- `S02` `M` `dev/deploy/docs_static_site.py`
- `S02` `M` `worker/docs-site.mjs`
- `S02` `M` `worker/docs-site.test.mjs`
- `S02` `M` `dev/deploy/tests/test_docs_static_site.py`
- `S02` `M` `dev/deploy/tests/test_docs_delivery.py`
- `S02` `M` `docs/conf.py`
- `S02` `M` `RELEASING.md`
- `S02` `verify:` `node --test worker/docs-site.test.mjs` -> `pass`
- `S03` `M` `dev/docs/sequences/runner.py`
- `S03` `A` `dev/docs/sequences/verdict_cache.py`
- `S03` `A` `dev/docs/sequences/tests/test_verdict_cache.py`
- `S03` `M` `dev/docs/sequence_build_gate.py`
- `S03` `A` `dev/docs/pagefind_service.py`
- `S03` `M` `dev/docs/pagefind_index.py`
- `S03` `M` `dev/docs/pagefind_inject.py`
- `S03` `M` `dev/quality/metadata/import_load_targets.json`
- `S03` `verify:` `pytest dev/docs/sequences/tests` -> `pass`

## Notes

- `S03` Also removed the Pagefind client's per-response sleep: the search pass over every root fell from over 29 min to 101 s.
