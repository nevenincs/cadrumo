---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
step_id: 'S157'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W01.P06.S157`

Audit the `_legacy_iva_wallet_decision_key` bridge in `_observations_repository.py`. Grep result: zero cleartext key hits across all `_data/` fixture directories. The function is retained because `load_decision` actively calls it as a read-fallback on line 263; it is not dead code — it is a live migration bridge. Added a Wave 2 cleanup docstring note.

- Modified: `src/aeat/application/calculations/_observations_repository.py`

## Description

Grep count for cleartext `iva-wallet-decision:<NIF>` key patterns across `src/aeat/_data/`: 0 matches. The bridge itself has 2 source references (definition + call site in `load_decision`). Because the call site is live production code that falls back to the cleartext key when the hashed-key lookup returns None, the bridge cannot be deleted without confirming all persisted records have been migrated in production environments. A Wave 2 cleanup note was added to the docstring per the plan spec.

## Tests

S158 covers the bridge behavior. Commit SHA: 74f07401b.
