---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-wave3-step2-exec]]'
---



# `calculation-truth-registry-wave3-step2` Code Review

No blocking findings.

Reviewed scope:

- `src/aeat/application/filing/test_filing.py`, limited to the new Modelo 115
  registry-backed build and approval assertions.
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`, limited
  to the Modelo 115 filing-boundary tracking row.
- `.vault/exec/2026-05-03-calculation-truth-registry/2026-05-05-calculation-truth-registry-wave3-step2.md`.

Checks performed:

- The new Modelo 115 tests call the committed runtime registry provider and
  public filing APIs instead of defining local casilla schemas or formulas.
- The asserted computed casillas exercise registry calculation behaviour and
  formula trace output for casillas 03 and 05.
- Approval verifies that the public approval path preserves a registry
  schema/formula fingerprint.
- The plan keeps the live sanitized fixture and live filed-data rows open
  because no Modelo 115 live artefact is currently available.
- The reviewed code/test scope does not introduce local-schema fixtures,
  fallback authorities, soft validation modes, or past-state comparison tests.

Verification reviewed:

- `uv run ruff check src\aeat\application\filing\test_filing.py`
- `uv run ty check src\aeat\application\filing\test_filing.py`
- `uv run pytest src\aeat\application\filing\test_filing.py -q`
- `uv run pytest src\aeat\application\filing\test_filing.py src\aeat\application\filing\test_export.py src\aeat\domain\calculations\registry\test_committed_registry.py -q`
- `git diff --check -- src\aeat\application\filing\test_filing.py .vault\plan\2026-05-03-calculation-truth-registry-rebuild-plan.md .vault\exec\2026-05-03-calculation-truth-registry\2026-05-05-calculation-truth-registry-wave3-step2.md`
- Static sanitization search over the same reviewed scope.
