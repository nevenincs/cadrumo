---
step_id: S114
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P31-S113]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P31-S115]]"
---

# cross-domain-continuity W07.P31.S114 — M100 2024 mínimo del contribuyente: fix

## Outcome

Registry fixed: parameter + two formulas added; casilla definitions updated.
All existing tests pass (confirmed by runner before commit).

Commit: `01ac9d698`

## What was done

Added the missing statutory flat value for mínimo del contribuyente (LIRPF Art. 57,
5,550 EUR unchanged 2015-2024) as a registry parameter, then wired two computed
formulas that populate casillas 0511 and 0512 from it.

### New files

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/parameters/0030-renta-2024-minimo-contribuyente-base-2024.toml`
  — parameter `renta-2024-minimo-contribuyente-base-2024`, value 5550 EUR,
  valid_from 2024-01-01, valid_to 2024-12-31, cites LIRPF Art. 57.

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0166-renta-2024-minimo-contribuyente-estatal.toml`
  — formula `renta-2024-minimo-contribuyente-estatal`, target 0511,
  `lookup_parameter` of `renta-2024-minimo-contribuyente-base-2024`,
  rounding money-2, cites LIRPF Art. 56-57.

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/formulas/0167-renta-2024-minimo-contribuyente-autonomico.toml`
  — formula `renta-2024-minimo-contribuyente-autonomico`, target 0512,
  same parameter lookup, additional legal ref LIRPF Art. 74.

### Modified files

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0493-0511.toml`
  — changed `input_kind` from absent/manual to `computed`, added `formula` backref
  `renta-2024-minimo-contribuyente-estatal`.

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/casillas/0494-0512.toml`
  — same change for autonómica variant, formula `renta-2024-minimo-contribuyente-autonomico`.

## Authority

- LIRPF Art. 57 (mínimo del contribuyente: 5,550 EUR flat)
- LIRPF Art. 56 (base de aplicación del mínimo)
- LIRPF Art. 74 (partidas aplicables en la escala autonómica)
- BOE Orden HAC-563-2024 (5,550 EUR confirmed unchanged for 2024)
- Pattern from 2025 revision (0035-renta-2025-minimo-contribuyente-base-2025 + formula 0081)
