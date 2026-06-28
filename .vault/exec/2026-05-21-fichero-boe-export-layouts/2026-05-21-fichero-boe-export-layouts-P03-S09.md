---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S09'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S09`

Re-derived the Modelo 303 DR-spec data from the corpus XLSX workbook into
registry-TOML form.

## Source

XLSX: `src/aeat/_data/corpus/aeat_official/disenos_registro/modelo_303/files/04-303-ejercicio-2024-a-partir-de-periodos-09-y-3t-y-siguientes-actualizado-29-11-24-381-kb-x.xlsx`

2022 reference for DP30302 descriptions (absent in 2024 edition):
`02-303-ejercicio-2022-y-siguientes-actualizado-27-12-2021-332-kb-xlsx.xlsx`

## Findings

Eight segments with byte counts confirmed from DR:
- DP30300: 328 bytes (rows 1-13 data + row 15 closing tag handled separately)
- DP30301: 1581 bytes (rows 1-88)
- DP30302: 1706 bytes (rows 1-91); descriptions absent in 2024 edition, recovered from 2022
- DP30303: 1017 bytes (rows 1-38)
- DP30304: 998 bytes (rows 1-43)
- DP30305: 1523 bytes (rows 1-72)
- DP303DID: 823 bytes (rows 1-13); page identifier "DID00" is type An (not Num)
- Closing tag: 18 bytes (computed)
- Total: 7994 bytes

Special findings:
- DP30301 contains new 2024 casillas 150-158, 165-170 (rate tiers added 2024-11-29)
- DP303DID page identifier "DID00" is An type in DR, must be kind="literal"
- DP30302 descriptions all "C" in 2024 XLSX; 2022 edition has RS activity descriptions

Generator scripts: `.vault-scratch/gen_303_casillas.py`, `.vault-scratch/gen_303_export_layouts.py`

Commit: `c744459f4`
