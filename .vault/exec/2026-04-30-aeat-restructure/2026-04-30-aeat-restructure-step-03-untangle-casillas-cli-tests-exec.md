---
tags:
  - "#exec"
  - "#aeat-restructure"
date: 2026-05-01
modified: '2026-05-01'
related:
  - "[[2026-04-30-aeat-restructure-adr]]"
  - "[[2026-04-30-aeat-restructure-plan]]"
  - "[[2026-04-30-aeat-restructure-step-03-untangle-formulas-public-surface-exec]]"
---

# 2026-04-30-aeat-restructure step-03 untangle casillas/cli tests

## status

Step 3 PR 3 of N — resolves layered violation 1 (audit 18). The two casillas test files that exercise the CLI surface relocate from the `casillas/` domain subpackage to the `cli/` entrypoint subpackage where they belong.

## scope

- `git mv src/aeat/domain/casillas/_test_cli.py src/aeat/entrypoints/cli/_test_casillas.py`
- `git mv src/aeat/domain/casillas/test_live_cli.py src/aeat/entrypoints/cli/test_live_casillas.py`
- Update relative imports inside the moved files (parent shifted from `..cli.X` to `.X`).

## rationale

In the new layout, `casillas/` becomes `domain/casillas/` and `cli/` becomes `entrypoints/cli/`. A domain-side test that imports from the entrypoint package is a layered violation (`domain/` MUST NOT import from `entrypoints/`). Relocating the test files puts them in the package whose surface they actually test, so the future import-linter contract finds zero violations on day one.

## verification

- `pytest --collect-only`: 6796/6820 tests collect; zero collection errors.
- `pytest --collect-only src/aeat/entrypoints/cli/_test_casillas.py src/aeat/entrypoints/cli/test_live_casillas.py` reports the moved test files at their new home; no orphans at the old paths.
- `grep -rn "casillas/test_live_cli\|casillas/_test_cli"` — zero references to the old paths in the repo.

## findings (FIX / FILE / STRIKE)

None additional — the move + 2 import-line tweaks is the entire untangle.

## next step

Step 3 PR 4 — `filing._review` → `aeat.domain.financial.transactions._repository` (audit 5; final substantive Step 3 untangle). After that lands, Step 3 covers 4 of 7 violations directly; the remainders (`profile.assets`/`profile.inventory` private bypasses) are already covered by Step 3 PR 2's formulas-public-surface promotion.
