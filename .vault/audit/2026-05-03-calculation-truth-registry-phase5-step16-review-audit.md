---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step16-exec]]'
---

# `calculation-truth-registry` Code Review

Review result:

- No findings.
- Detection no longer branches on `modelo == "100"` or defines
  `_modelo_100_revision`.
- Revision detection is now limited to Orden HAC parsing or the generic
  `{ejercicio}.01` sentinel, with extractor dispatch still fail-closed pending
  validated registry snapshots.
- The stale `2021.legacy` schema example was removed.

Verification reviewed:

- ruff passed on the touched detection/schema/deletion-gate files.
- full ty passed.
- Focused pytest passed with 35 passed.

Residual risk:

- Remaining Modelo 100 mentions in detection comments explain why the first two
  pages are scanned for `Ejercicio`; they do not encode revision mapping or
  dispatch authority.
