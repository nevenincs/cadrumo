---
tags:
  - '#exec'
  - '#core-authority'
step_id: S80
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W09.P24.S80 - domain-to-application edge removal

## Outcome

Identified all 7 domain-to-application import edges (MIGRATE-005, RELOC-029).

**Fixed (1 edge):**
- `domain/profile/conftest.py:13` — removed `from aeat.application.wizard import _compiler`. The conftest imported the application compiler as a side-effect to pre-register PROFILE_KEYS. This was redundant: `domain/profile/_keys._build_profile_keys()` is the ADR-named lazy cycle-breaker that performs the same registration on first access. 176 domain/profile tests continue to pass.

**Protect-list (1 edge — no action):**
- `domain/profile/_keys.py:137` — lazy `from ...application.wizard._compiler import compile_profile_keys` inside `_build_profile_keys()`. Explicitly named ADR protect-list: "two lazy `__getattr__` cycle-breakers in domain.transactions and domain.profile."

**BLOCKED by W08 (5 edges — W08 currently owns application/):**
- `domain/calculations/registry/test_detail_record_modelo_coverage.py:18` — imports `application.storage.calc_sheets.collect_row_sets`; test belongs in application/.
- `domain/calculations/registry/test_cross_boundary_roundtrip.py:439` — lazy import of `application.workflow._models` types; test belongs in application/.
- `domain/calculations/registry/test_referential_integrity.py:792` — lazy import of `application.diagnostics.build_config_repair_report`; test belongs in application/.
- `domain/invoices/test_reconciliation.py:12` — module-level `aeat.application.invoices` import; test belongs in application/.
- `domain/modelos/test_work_unit.py:25` — module-level `aeat.application.modelo` imports; test belongs in application/.

## Commit

`0a45d6895` — refactor(domain): W09.P24.S80 - remove application import from domain/profile/conftest.py

## Files touched

- `src/aeat/domain/profile/conftest.py` — removed upward application import

## Verification

176 domain/profile tests pass. Edge count: 1 fixed, 1 protect-list, 5 blocked.
