---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:57241ec18f26beca9c8b9df99156c68f8fa345d0d913b23ee9f443d54711ae3f'
step_id: 'S07'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

# Declare the M100 imputation-year-days value as a registry parameter on the M100 revisions in the registry authoring tree so it rides the loader and compiler

## Scope

- `src/aeat/_data/registry/aeat/modelos/100`

## Description

- Declare `renta-2024-imputacion-inmobiliaria-year-days` as an integer days parameter on the Modelo 100 2024 Art. 85 parameter bundle.
- Declare `renta-2025-imputacion-inmobiliaria-year-days` as an integer days parameter on the Modelo 100 2025 Art. 85 parameter bundle.
- Ground both parameters on the same Art. 85 manual source family as the existing imputed-real-estate rate parameters.

## Outcome

- The M100-only registry loader accepted the updated Modelo 100 authoring tree and confirmed both new parameter ids are present.
- Existing Art. 85 pytest could not be used as a clean S07 gate because full authority loading currently fails on unrelated Modelo 131 2025 internal-only casilla WIP before any M100 calculation executes.

## Notes

- Verification log: `_scratch-codex/w2_s07_m100_direct_load.log`.
- Blocked broader log: `_scratch-codex/w2_s07_m100_art85_pytest.log`.
