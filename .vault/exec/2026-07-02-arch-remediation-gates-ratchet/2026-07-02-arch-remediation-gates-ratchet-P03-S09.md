---
tags:
  - '#exec'
  - '#arch-remediation-gates-ratchet'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:10f7c84a59825264eec9a60e9ddd772da082f2e9c5229203c5a2937e6446b995'
step_id: 'S09'
related:
  - '[[2026-07-02-arch-remediation-gates-ratchet-plan]]'
---

# Add pinned-module existence gate

## Scope

- `src/aeat/tests/test_importlinter_ledger.py`

## Description

- Added a structural test that parses every `.importlinter` ignore edge and resolves both source and target modules under `src`.
- Wildcard modules resolve to their concrete package prefix before the filesystem check.

## Outcome

The focused ratchet test passes and reports no missing pinned modules.

## Notes

The test imports `REPO_ROOT` from the repository test inventory helper and does not mirror production business logic.
