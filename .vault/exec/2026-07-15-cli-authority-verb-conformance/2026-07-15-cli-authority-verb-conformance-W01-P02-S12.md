---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S12'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Retarget the ignore-edge parser from aeat imports to cadrumo imports

## Scope

- `src/cadrumo/tests/test_importlinter_ledger.py`

## Description

- Retarget `_IGNORE_EDGE_RE` source and target prefixes from `aeat` to `cadrumo`.
- Preserve the existing parser, ratchet ceilings, test names, comments, and assertions for their later planned steps.
- Verify the parser through its imported codebase helper and run the focused architecture gates.

## Outcome

The parser now observes 265 configured ignore edges, including 229 edges in the layered contract. Its current layered endpoint inventory is 199 application-to-adapter edges, 78 application source wildcards, and two domain-to-adapter test carveouts; production domain-to-adapter edges remain zero.

`ruff check` passed. The focused ledger module passed all four tests. A fresh uncached Import Linter run analyzed 3,421 files and 16,157 dependencies with all five contracts kept and none broken.

## Notes

The focused module remained green because its pre-reconciliation 840/78/70 ceilings are permissive. Later planned steps own lowering those values and adding explicit non-vacuity assertions; this step did not pre-empt them.
