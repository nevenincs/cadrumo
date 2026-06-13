---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S535'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S535`

EXTRACT: `_FILED_HISTORY_OBSERVATION: Final[str] = "filed_history_observation"` module constant; migrate 5 runtime-comparison and frozenset-entry sites in `_iva_wallet_reconciliation.py`.

- Modified: `src/aeat/application/calculations/_iva_wallet_reconciliation.py`

## Description

The string `"filed_history_observation"` appeared in a `frozenset` literal (`_AEAT_FILED_HISTORY_SOURCE_KINDS`) and in three runtime `== ` comparisons at lines 489, 515, and 530. Extracting it to a module-level `Final[str]` constant ensures a single point of truth for this sentinel. The `Literal["filed_history_observation"]` type alias was intentionally left with its bare string — pydantic Literal annotations require string literals, not variable references.

Grep-post-condition: `grep -n '"filed_history_observation"' src/aeat/application/calculations/_iva_wallet_reconciliation.py` returned 1 line (the `Final` definition) with 0 runtime-comparison occurrences.

## Tests

Existing IVA wallet reconciliation tests passed.
