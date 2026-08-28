---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:0cb162561419f948d1406b13daddb474c3a7e756147a96cacdc20272cf3401d0'
step_id: 'S11'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Derive the ledger public-module set from the package instead of a hand-listed tuple that went stale when a peer relocation published two modules

## Scope

- `src/cadrumo/application/ledger/tests/`

## Changes

- `M` `src/cadrumo/application/ledger/tests/test_public_definition_identity.py`
- `verify:` `pytest src/cadrumo/application/ledger/tests/test_public_definition_identity.py` -> `pass`
