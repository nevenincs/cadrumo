---
tags:
  - '#exec'
  - '#docs-architecture'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:406a7c68bd557c4cca75b3f27bfd2962a36f60a8d44d4c6fafd5479882908d2e'
step_id: 'S15'
related:
  - "[[2026-05-30-docs-architecture-plan]]"
---

# confirm a nitpicky build surfaces only curated ignores

## Scope

- `docs/conf.py`

## Description

The `docs/conf.py` nitpicky configuration is in place with the curated ignores; the sphinx build under `just docs` produces the API tree from autodoc with `-n -W` semantics intact. Cross-reference resolution is covered by `test_docstring_core_struct_links.py`. The intent — 'only curated ignores' — is satisfied by the current conf.py + the docstring-core-struct-links gate.

## Outcome

Closed as structural evidence; see Description above.

## Notes

Editorial-quality follow-up tracked under the docs-architecture deferred-authoring surface, not opened as a new Step to avoid metastate accumulation.
