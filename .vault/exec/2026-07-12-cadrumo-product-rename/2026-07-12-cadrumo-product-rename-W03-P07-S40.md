---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S40'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update the split-companion install probe and wheel globs

## Scope

- `dev/packaging/smoke_split_install.py`

## Description

- Retarget the slim distribution, companion project directories, wheel globs, archive prefixes, runtime imports, script invocation, and install hint to Cadrumo.
- Preserve `aeat_official` only as the authority-owned official corpus partition.
- Strip inherited `CADRUMO_*` settings from every installed-product runtime child and provide isolated temporary storage and SQLite settings.
- Build the real root, manuals, and official wheels and install them into a fresh stdlib virtual environment under a bounded command budget.

## Outcome

The split-install lane now expects the `cadrumo` runtime wheel and the
`cadrumo-data-manuals` and `cadrumo-data-official` companion wheels from their
canonical project directories. Both companions join the `cadrumo_data` namespace,
while the slim-wheel leak check targets `cadrumo/_data/corpus` and runtime probes
import `cadrumo` and invoke the installed `cadrumo` script. No former namespace,
distribution, or script fallback remains.

## Notes

- Ruff, formatting, former-identity residue, and scoped diff checks passed.
- S35 independently passed all five real-wheel partition tests for the same manuals and official companion projects, including byte membership, disjoint/exhaustive ownership, shared namespace, version parity, and file-cap checks.
- The real split-install command built from a pristine `HEAD` archive and ran in a fresh stdlib environment, but the outer 124-second command budget expired before the tool returned completion output. This is recorded as incomplete end-to-end acceptance evidence, not a passing run.
- The parent requested no repeat or broad rerun after the bounded result.
