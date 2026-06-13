---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
---



# `calculation-truth-registry` `Phase 2` `Step 17`

Cleaned the older filing CLI surface and tests so they no longer rely on
placeholder profile identity or a baked-in successful Modelo 130 path.

- Modified: `src/aeat/entrypoints/cli/filing/__init__.py`
- Modified: `src/aeat/entrypoints/cli/filing/test_filing_cli.py`

## Description

The filing build command now requires an explicit `--profile-tax-id` when no
profile file is configured. It no longer creates a default taxpayer identity,
default display name, or profile-level modelo applicability tuple. Configured
profile files remain supported through the existing encrypted profile loader.

The declaración import path no longer has a Modelo-specific tax-residence branch.
Declaration PDF import now remains an observed-document parse plus verification
flow; model-specific requirements belong to registry-backed verification and
profile validation.

The filing CLI tests now derive the positive build modelo from the committed
registry, and the justificante import test records the current fail-closed
behaviour for a PDF whose modelo requires calculation inputs the PDF does not
provide. Tests no longer assert success for a hardcoded Modelo 130 path that the
registry cannot calculate without dependent historical data.

## Tests

- `uv run pytest src\aeat\entrypoints\cli\filing\test_filing_cli.py -q`
- `uv run ruff check src\aeat\entrypoints\cli\filing\__init__.py src\aeat\entrypoints\cli\filing\test_filing_cli.py`
- `uv run ty check src\aeat\entrypoints\cli\filing\__init__.py src\aeat\entrypoints\cli\filing\test_filing_cli.py`
- `uv run pytest src\aeat\entrypoints\cli\filing\test_filing_cli.py::TestFilingCLI::test_complementaria_submit_command_is_absent -q`
