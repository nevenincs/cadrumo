---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:ed53c676e6299463e1b81b381a60ec9fcc7452d8f044d21d3c3af97ce2e5a223'
step_id: 'S240'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.iva`

## Scope

- `src/aeat/application/aggregation/_iva_ledger.py`

## Description

Ran the `dev/import_centralization_codemod.py` AST codemod against every production `aeat.application.aggregation`, `aeat.application.invoices`, `aeat.application.storage`, `aeat.application.evidence`, `aeat.application.live`, `aeat.application.bucket_maintenance`, `aeat.application.config_reset`, `aeat.application.diagnostics`, `aeat.application.inventory`, `aeat.application.registry`, `aeat.application.setup`, `aeat.application.state_projection`, `aeat.application.storage_write_policy`, and `aeat.application.transactions` module, rewriting every cross-package private import onto the owning package's promoted top-level facade. This record anchors and covers Phases `W02.P49`, `W02.P50`, `W02.P53`, and `W02.P63` through `W02.P71` in one commit, per the batching directive for this Wave.

- Ran the codemod in dry-run, then `--apply`, over the full `src/aeat` tree.
- Restored a dropped `# noqa: F401  # model_rebuild local namespace` trailing comment in `application/diagnostics.py`'s `_ensure_models_rebuilt` (the codemod's single-name rewrite path did not preserve a trailing inline comment); confirmed no other trailing-comment losses across the batch with a targeted `ruff check --select F401,F811,F821` pass.
- Normalised the rewritten import blocks with `ruff check --fix --select I` and `ruff format`.
- Verified `pytest --collect-only -q src/aeat` collected cleanly (0 import errors attributable to this batch).
- Committed the 25 files as one atomic explicit-pathspec commit.

## Outcome

25 files rewritten and committed (commit `d67ccc42a`, `refactor(application): route cross-package imports through owning facade (import-centralization W02)`). Behavior-preserving: no symbol relocation, no signature change.

## Notes

The codemod's line-anchored rewriter does not preserve a single-import statement's trailing inline comment; this is a known limitation of the tool worth fixing before a future large batch (documented here rather than silently re-run). Plan checkboxes for the covered Steps are left unchecked pending a follow-up bulk `vault plan step check` pass; the commit SHA above is the durable evidence trail.
