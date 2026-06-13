---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S10'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P03.S10`

Re-resolved the Modelo 303 segment-scoped casilla-number reuse so each
fichero-BOE field disambiguates to a distinct registry casilla.

## Resolution

The M303 form reuses conceptual casilla numbers across segments (e.g. casilla
154 appears as a tipo-% field in DP30301, casilla 65 as a ratio in DP30303).
Resolution approach:

- Each casilla is assigned a unique registry `id` equal to its DR casilla number
  (e.g. `"154"`, `"65"`). The `number` field also holds the casilla number.
- Export fields in different records reference different casilla IDs — no two
  export fields share the same casilla_id unless they both serve the same
  physical form field.
- Tipo-% fields that are DR constants (e.g. "02100" for 21%) use `kind="literal"`
  rather than a casilla reference, so no ambiguous casilla binding exists.
- Variable tipo-% fields (casillas 154, 17, 169) are referenced as casilla ids
  with `data_type="money"`.
- The 89 new casilla definitions cover all numbered DR fields without collision.

## New casilla definitions added

93 new numbered casillas added to 303.toml covering:
- New 2024 rate tiers: 150-155, 156-158, 165-170
- DP30301 devengado: 01-27 (including tipo-% casillas)
- DP30301 deducible: 28-45
- DP30302 RS: 47-58
- DP30303 resultado/informativo: 59, 60, 62-66, 68, 70-71, 74-77, 108-111, 120, 122-124

Commit: `c744459f4`
