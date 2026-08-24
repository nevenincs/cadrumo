---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:189863ea2c32928ae2be002627c07f7456c8b127aa0e57b1665ff82bf7931dc9'
step_id: 'S21'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Rewrite ValidatedRegistryAuthority.deadline_windows to project canonical owners through select_revision with deterministic qualifier-aware ordering and no deduplication

## Scope

- `src/cadrumo/domain/calculations/registry/_authority.py`

## Description

- Reuse `select_revision` to select each deadline row's law-governing revision from its canonical `Period` coordinate.
- Exclude non-owning historical copies while preserving every authored row beneath the selected revision.
- Extend deterministic ordering with the existing typed resultado and official tipo-renta qualifier values.
- Confirm through Vaultspec RAG that no second revision selector, qualifier vocabulary, deadline resolver, or deduplication path was introduced.

## Outcome

`ValidatedRegistryAuthority.deadline_windows` now projects only canonically owned rows and returns the selected revision as provenance. Cold authorities still fail validation before projection when ownership is invalid; a fingerprint-certified warm authority cannot leak stale cross-revision copies. Ruff passed. The focused M210 deadline test passed; the real bundled authority test remains blocked at fixture setup by the known pre-repair M184, M303, and M322 corpus validation failures outside this step.

## Notes

No production deduplication, set collapse, alternate resolver, period parser, or qualifier-code list was added. Fleet multiplicity coverage belongs to the following plan step.
