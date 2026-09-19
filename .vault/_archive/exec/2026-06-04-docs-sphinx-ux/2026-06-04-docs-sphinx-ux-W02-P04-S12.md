---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:43b0a07774bcfcd441f4ac7e2633bfce84f5a96c43d837b68ddc2944cc854d77'
step_id: 'S12'
related:
  - "[[2026-06-04-docs-sphinx-ux-plan]]"
---

# separate operator CLI routes from schema registry detail

## Scope

- `src/aeat/entrypoints/cli/_doc_reference.py`

## Description

Verified the route separation shipped under the accepted
`2026-06-14-docs-tooling-separation-adr` rather than at the scoped path (`src/aeat/...`
never existed post-rename). `dev/docs/cli_reference.py` walks the live Click tree and
renders per-family RST pages under `docs/cli/`, with `docs/cli/index.rst` routing to an
operator-CLI family grid plus separate `automation.rst` (exit codes, TTY/JSON contract)
and `schemas.rst` (output-schema registry) pages, keeping operator-CLI routes distinct
from schema/registry detail.

## Outcome

Step closed as already-satisfied. No new commit required; this record documents the
verification only. The stale scope path is not rewritten on this step per adjudication
(only `S23`'s scope path was in scope for rewrite); the real implementation site is
`dev/docs/cli_reference.py`.

## Notes

Read `dev/docs/cli_reference.py` and confirmed neither `src/aeat/...` nor
`src/cadrumo/entrypoints/cli/_doc_reference.py` exist at HEAD.
