---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e4923869c1531f375e89ea5df43862c4697244b7c15d3a94e4703ed480673e05'
step_id: 'S32'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
## Revalidation outcome

Status: **verified and owned; not fully enrolled**.

The prior import blocker is cleared: the application registry census and filing provenance boundary import together. The live filing-grade authority was then recomputed rather than inferred from a separate inventory: **66 filing revisions** expose **9,150 binding declarations**.

## Authority and ownership

The filing-binding gate traverses the validated registry authority, uses the single selector registry and calculation-route disposition table, and reads provenance from the filing boundary. Vaultspec-RAG plus whole-file review of the binding registry, route resolver, source-connectivity authority, filing provenance boundary, and focused test found no parallel selector, resolver, source taxonomy, provenance builder, census, or deferred-owner declaration.

Modelo 193 revision 2024 has its exact `gasto193_contributor` census destination in `rows.gasto193-contributor`. The only deferred source families are:

- Modelo 232 / `2018-y-siguientes` / `related_party_operation` â€” accepted owner S92â€“S95.
- Modelo 360 / `2010-y-siguientes` / `refund_operation` â€” accepted owner S96â€“S99.
- Modelo 193 / `2024` and `2025-y-siguientes` / `gasto193_contributor` â€” accepted owner S104â€“S107.

Each maps uniquely to a bounded source-connectivity census entry and remains deferred, never enrolled.

## Source-window correction and adjacent gate repair

Modelo 353''s 2026 AEAT domiciliation calendar is valid evidence for the December 2025 deadline window, but not generic evidence for the 2008â€“2025 revision. Its redundant top-level revision reference was removed while retaining the exact deadline-window reference and construct closure. The mutation test proves that reattaching it at revision scope is rejected; source-window validation was not weakened or suppressed.

The exact integration gate had two test-only regressions after the M036 census row was prepended. Census replacement now uses the stable `candidate_id`, never a positional index. Its encrypted-payload deletion assertion now expects the repository''s intentional `CalculationRevisionPersistenceError` wrapper and verifies `reason=invalid_payload`, preserving the deletion bite without changing production behavior.

## Verification

- `uv run pytest -m integration src/cadrumo/application/registry/tests/test_source_connectivity_authority.py -q` â€” 22 passed.
- `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_filing_grade_binding_resolution.py -q` â€” 5 passed.
- `uv run pytest src/cadrumo/domain/calculations/registry/tests/test_modelo_353_registry.py -q` â€” 23 passed.
- `uv run ruff check src/cadrumo/application/registry/tests/test_source_connectivity_authority.py src/cadrumo/domain/calculations/registry/tests/test_modelo_353_registry.py` â€” passed.
- The direct live-authority census reports 66 filing revisions and 9,150 binding declarations.

## Independent review request

This is a closure of the S32 verification obligation only. Enrollment of the explicitly deferred families remains owned by S92â€“S107. Request a fresh independent review of the scoped data correction, regression tests, no-redeclaration evidence, and this verified/owned boundary.

