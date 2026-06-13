---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `Wave 2` `Modelo 111 reconciliation totals`

Closed the Modelo 111 registry-to-reconciliation linkage for payable totals.

- Modified: `registry/aeat/modelos/111.toml`
- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/application/filing/runtime.py`
- Modified: `src/aeat/application/filing/reconciliation/_reconcile.py`
- Modified: `src/aeat/adapters/inbound/justificante/_extract.py`
- Modified: `src/aeat/domain/deadlines/_engine.py`
- Modified: `src/aeat/domain/deadlines/_models.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Modified: `src/aeat/application/filing/reconciliation/test_reconcile.py`
- Modified: `src/aeat/domain/deadlines/test_engine.py`
- Modified: `src/aeat/entrypoints/cli/deadlines/test_cli.py`
- Modified: `src/aeat/entrypoints/cli/filing/test_filing_cli.py`
- Modified: `src/aeat/adapters/outbound/aeat/sede/test_declarations.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

Added a registry-declared `reconciliation_totals` mapping on verification
expectations so application reconciliation can derive payable or refundable
totals from the active modelo snapshot rather than from Python-side
modelo-specific branching.

Modelo 111 now declares casilla 30 as the payable reconciliation total. The
runtime filing subview exposes that mapping, and reconciliation uses it to
compare AEAT receipt totals against the computed draft value. The validator
fails when a declared reconciliation total points to an unknown casilla or to a
casilla outside the verified computed set.

Modelo 111 application links now include review and workflow surfaces, closing
the remaining export, filing, approval, review, reconciliation, and workflow
linkage row in the Wave 2 ledger.

The justificante parser comments were also sanitized to remove capture-date
and development-observation language while preserving the actual parser
contract for observed AEAT receipt layouts.

The deadline engine now supports registry-declared `any` applicability
conditions. Modelo 111 uses those conditions for employee and professional
withholding payer profiles, so deadline applicability is not encoded in Python
comments or old CLI expectations.

The generic filing CLI smoke helper now selects a calculable modelo from the
active registry provider instead of naming Modelo 111 as a convenient default.

The live redacted submitted-file fixture for Modelo 111 is now checked against
the registry extraction profile rather than against a hardcoded casilla count:
the parser must observe exactly the target casillas declared by the committed
Modelo 111 registry snapshot, and computed casillas 28 and 30 must recalculate
from that observed payload.

The final Modelo 111 authority scan found no non-test runtime Python branch
that can populate Modelo 111 filing-grade values outside the registry. The
remaining Modelo 111 references are registry and official corpus authority,
portal navigation metadata, sanitized read-only AEAT artefacts, receipt/parser
shape tests, registry behaviour tests, and Modelo 100 official corpus rows
where `111` is an official Modelo 100 code rather than a Modelo 111 authority.

## Tests

- `uv run pytest src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\application\filing\reconciliation\test_reconcile.py -q` passed.
- `uv run pytest src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_export.py src\aeat\application\filing\reconciliation\test_reconcile.py -q` passed.
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json` passed with `"verified": true`.
- `uv run ruff check` passed for the touched Python files.
- `uv run ty check` passed for the touched Python files.
- `uv run pytest src\aeat\adapters\inbound\justificante\test_extract_modelos.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\reconciliation\test_reconcile.py -q` passed.
- `rg -n "Captured live|2026-04-25|2026-04-24|hard_cut|migration|transient|ADR|wave|phase"` returned no matches for the touched runtime parser and registry/application modules.
- `uv run pytest src\aeat\domain\deadlines\test_engine.py src\aeat\domain\deadlines\test_models.py src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py -q` passed.
- `uv run pytest src\aeat\entrypoints\cli\deadlines\test_cli.py src\aeat\domain\deadlines\test_engine.py src\aeat\domain\calculations\registry\test_registry_schema.py -q` passed.
- `uv run pytest src\aeat\entrypoints\cli\filing\test_filing_cli.py -q` passed.
- `uv run pytest src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\domain\calculations\registry\test_workbook_parity.py src\aeat\domain\portals\test_metadata.py -q` passed.
- `rg -n "modelo = \"111\"|modelo=\"111\"|modelo_id == \"111\"|modelo_id = \"111\"|\[\"111" src tests --glob '!src/aeat/domain/portals/**' --glob '!**/test_*' --glob '!**/*test*.py'` returned no matches.
- `uv run pytest src\aeat\domain\calculations\registry\test_registry_schema.py src\aeat\domain\calculations\registry\test_committed_registry.py src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_export.py src\aeat\application\filing\reconciliation\test_reconcile.py src\aeat\adapters\inbound\justificante\test_extract_modelos.py src\aeat\domain\deadlines\test_engine.py src\aeat\domain\deadlines\test_models.py src\aeat\entrypoints\cli\deadlines\test_cli.py src\aeat\entrypoints\cli\filing\test_filing_cli.py src\aeat\adapters\outbound\aeat\sede\test_declarations.py src\aeat\adapters\inbound\declaracion\test_parser_boundary.py src\aeat\domain\calculations\registry\test_workbook_parity.py src\aeat\domain\portals\test_metadata.py -q` passed with 198 tests.
- `uv run aeat app registry verify --registry-root registry\aeat --source-root . --json` passed with `"verified": true` for modelos 111 and 130.
- `uv run ruff check` passed for the touched runtime and test files.
- `uv run ty check` passed for the touched runtime and test files.
- `git diff --check` passed for the scoped files, with CRLF normalization warnings only.
- `uv run python -m compileall -q src\aeat\domain\portals\_entries` initially found malformed portal i18n conversion syntax in Modelo 037, 180, 190, and 193 portal entries; those syntax errors were repaired without changing portal semantics.
- `uv run pytest src\aeat\domain\portals\test_cli.py src\aeat\domain\portals\test_modelo_cross_reference.py src\aeat\domain\portals\test_registry.py src\aeat\domain\portals\test_smoke.py -q` passed with 36 tests after the syntax repairs.
- `just test` now collects and runs the project test suite, but the full project gate remains open: 2,837 passed, 4 skipped, 127 failed, 16 deselected. The remaining failures are outside the Modelo 111 registry slice and cluster around the active locale/i18n conversion, usage-ratio category eligibility, normatives translated-string expectations, auth/setup wording expectations, and marker integrity.
