---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

# Phase 5 Step 16 Execution

Removed model-specific declaration revision detection:

- Deleted the Modelo 100-specific revision branch from declaration template
  detection.
- Removed `_modelo_100_revision`.
- Removed the stale `2021.legacy` revision example from the template schema
  documentation.
- Added deletion gates proving detection no longer branches on `modelo == "100"`
  or defines the legacy helper.

Rationale:

- Per-model layout/revision mapping is legal corpus structure. Detection may
  extract identity from the PDF, but it must not mint model-specific legacy
  revision tags from Python rules.

Verification:

- `uv run --no-sync ruff check src\aeat\adapters\inbound\declaracion\_detect.py src\aeat\adapters\inbound\declaracion\_schema.py tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check`
- `uv run --no-sync pytest src\aeat\adapters\inbound\declaracion tests\import_contract\test_registry_deletion_gates.py`

Result: ruff passed, full ty passed, and the focused pytest slice passed with
35 passed.

Residual risk:

- Detection still scans the first two pages because some legacy PDFs place the
  `Ejercicio` stamp on page 2. That is detection robustness, not model-specific
  revision dispatch.
