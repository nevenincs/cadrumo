---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S38'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update the extras clean-install probe to Cadrumo names

## Scope

- `dev/packaging/smoke_extras.py`

## Description

- Retarget the aggregate extras install requirement and installed imports from the former product identity to `cadrumo`.
- Invoke the installed `cadrumo` console script and assert its canonical version banner.
- Strip inherited `CADRUMO_*` settings from every installed-product runtime probe child and provide isolated temporary storage and SQLite settings.
- Harden the shared installed-data child probe with the same isolated environment boundary discovered in S37.
- Build the real wheel, install `cadrumo[all]` with pip in a fresh stdlib virtual environment, and exercise all capability-gated imports.

## Outcome

The aggregate extras clean-install probe now installs `cadrumo[all]` from the
built `cadrumo-0.1.1-py3-none-any.whl`, imports the canonical `cadrumo` package,
preserves the external dependency package imports, and starts the installed
`cadrumo` script. The real fresh-environment probe passed and wrote its smoke
manifest.

## Notes

- `uv run --no-sync ruff check dev/packaging/smoke_core.py dev/packaging/smoke_extras.py` passed.
- `uv run --no-sync python -m dev.packaging.smoke_extras --skip-export-checks --work-dir <temporary-directory>` passed in 78.2 seconds within the 120-second budget.
- The focused residue search found no former distribution, import, script, version-banner, wheel-glob, or internal executable-helper expectation in the extras probe.
- Broad suites were not rerun; the parent requested closure after the bounded real-install probe.
