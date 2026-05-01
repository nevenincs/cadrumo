---
tags:
  - '#exec'
  - '#modelo-347-calc-verify'
date: '2026-05-01'
related:
  - '[[2026-05-01-modelo-347-calc-verify-plan]]'
  - '[[2026-05-01-modelo-347-calc-verify-review]]'
---

# `modelo-347-calc-verify` `implementation` summary

Modelo 347 Tier-S declaration-import verification now covers 2024, 2025, and 2026.

- Created: `src/aeat/domain/modelos/m347/`
- Created: `src/aeat/application/verification/_verify_summary.py`
- Modified: `src/aeat/adapters/inbound/declaracion/`
- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `tests/integration/test_kent_workflows.py`
- Modified: `docs/coverage/modelos.md`
- Modified: `docs/coverage/kent-capabilities.md`

## Description

The implementation adds a strict `Modelo347RecordLine`, per-year schema manifests, 2024/2025/2026 extractor registration, per-counterparty detail-row extraction, and Tier-S resumen parity verification. `aeat filing import --from-declaracion` now emits `VERIFIED` for clean M347 parity and `NEEDS_REVIEW` with Kent-readable deltas when printed resumen totals disagree with the extracted detail rows.

No live-submit path was added. Modelo 347 remains an information return with no formula ruleset and no BOE-export claim in this PR.

## Tests

Passed:

- `uv run --no-sync ruff check ...`
- `uv run --no-sync pytest src/aeat/domain/modelos/m347/test_records.py src/aeat/application/verification/test_verify_summary.py src/aeat/adapters/inbound/declaracion/test_quarterly_extractors.py::TestModelo347V2025Extractor src/aeat/adapters/inbound/declaracion/test_quarterly_extractors.py::TestRegistryKnowsNewExtractors tests/integration/test_kent_workflows.py::TestKentImportsModelo347Declaracion -q`
- `just test-cov` with total coverage 83%

Not completed:

- `mypy` command is unavailable in this environment.
- `just lint-imports` is blocked by pre-existing stale ignored imports and broad architecture-contract violations outside this M347 diff.
