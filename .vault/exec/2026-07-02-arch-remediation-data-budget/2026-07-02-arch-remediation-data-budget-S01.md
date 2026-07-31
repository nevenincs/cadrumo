---
tags:
  - '#exec'
  - '#arch-remediation-data-budget'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:82088dfebabad3be95b8829d2680bb21564f4ba18a808db1feff6a9f5d0dfab0'
step_id: 'S01'
related:
  - "[[2026-07-02-arch-remediation-data-budget-plan]]"
---

# Add hatchling wheel excludes for src/aeat/**/tests/** and src/aeat/tests/** so no test module or fixture ships in the installed wheel

## Scope

- `pyproject.toml`

## Description

- Add hatchling wheel excludes for `src/aeat/tests/**` and `src/aeat/**/tests/**` in `[tool.hatch.build.targets.wheel]`.
- Add a `py.typed` PEP 561 marker (absent before) and include it plus the BIP-39 wordlist and `external_constants.toml` in the wheel.

## Outcome

Test payload is shed from the installed wheel; `py.typed` now marks the package typed. Verified no production module imports `aeat.tests` at module load (the one production-space reference imports the harness function-locally, test-invoked only).

## Notes

The project shipped no `py.typed` marker despite the ADR listing it as required functional payload; added the empty marker so the ADR constraint holds. No external consumers, so zero distribution risk.
