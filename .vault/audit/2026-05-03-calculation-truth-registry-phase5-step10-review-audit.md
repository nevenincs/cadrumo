---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step10-exec]]'
---

# `calculation-truth-registry` Code Review

Review result:

- Initial review found two issues:
  - The declaration CLI still projected invoice values into Modelo 303 casillas
    in `_aggregate_filing_inputs`.
  - `CategoryProfile` still accepted stale `casilla_mappings` payloads as
    ignored extra data.
- Fixes applied:
  - Removed the Modelo 303 invoice-to-casilla projection from
    `src/aeat/entrypoints/cli/_common.py`.
  - Set `CategoryProfile` to `extra="forbid"` and added a stale-payload
    rejection test.
  - Added deletion-gate coverage for the declaration CLI projection path.
- Follow-up review result: no findings.

Verification reviewed:

- ruff passed on the focused touched paths.
- ty passed on the focused touched paths.
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\domain\categories tests\import_contract\application\aggregation\test_aggregation.py src\aeat\application\workflow src\aeat\entrypoints\cli\financial`
  passed with 134 tests.

Residual risk:

- Financial aggregation and declaration input derivation are now intentionally
  fail-closed or empty until the registry-backed filing-input implementation
  lands.
