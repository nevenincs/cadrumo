---
tags:
  - '#audit'
  - '#core-authority-cutover'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:891df9cb099694ad56b25cc3c86dfae8dcc524fa4d3767ec602599ee4f6fc0f9'
related: []
---

# `core-authority-cutover` audit: `Public core authority hard cutover review`

## Scope

Audited the hard cutover in commit `8f59d0dfb3a` for the two canonical core
authorities: `src/cadrumo/core/credentials.py` and
`src/cadrumo/core/directory_scan.py`. The review checked the accepted
import-centralization decision, moved-definition identity, facade absence,
static consumer census, dynamic-import remnants, documentation targets, and
the scoped quality/test gates.

## Findings

No findings. The exact census covers 6,214 Python files and reports 405 direct
public-module import statements, zero legacy or wrong-module imports, and one
definition for each of the 13 relocated symbols. Both former private files are
absent, the core namespace has no relocated bindings, and no dynamic or
documentation references to the former private module paths remain outside
historical VaultSpec records. Scoped Ruff, compileall, and the 50-test focused
suite pass; core test collection completes with 1,582 collected tests and two
explicit deselections.

### docs-consumer | low | Documentation configuration retained a facade import

The project-wide follow-up census found one documentation-build consumer in
`docs/conf.py` that was outside the initial `src`, `dev`, and `packaging` scan.
It now imports directly from `cadrumo.core.directory_scan`, and the fixed-point
gate includes `docs` so this class of omission is caught. The corrected tree
has 6,216 Python files and 406 direct public-module import statements with no
legacy or wrong-module imports; the follow-up Ruff check and three-test gate
pass.

## Recommendations

No follow-up recommendation is required for this cutover. An independent
reviewer should confirm the committed import rewrites before the branch is
considered fully accepted; the broad repository Ruff result remains a
non-gating concurrent/pre-existing baseline with 712 findings.
