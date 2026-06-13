---
step_id: S246
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P31-S114]]"
  - "[[2026-05-26-cross-domain-continuity-W07-P31-S115]]"
---

# cross-domain-continuity W07.P31.S246-S249 — Mínimo supplement parameters + regression tests

## Steps covered

S246 (Art. 57.2/57.3 age supplements), S247 (Art. 58 descendant supplements),
S248 (Art. 59 ascendant supplements), S249 (regression tests).

Commits: `6306f5c76` (registry), `d7b25e4a9` (tests).

## Architectural finding

The task brief assumed the formula DSL could consume `renta_taxpayer.birth_date`
binding to compute age and derive supplement amounts. This is architecturally
impossible: the formula engine has no `date_diff` or `age_at` op; numeric
`binding_values` accept only `Decimal`; date-typed profile bindings cannot
flow into arithmetic expressions.

The 2025 revision confirms the correct pattern: casillas 0513 (mínimo por
descendientes), 0515 (mínimo por ascendientes), and 0517 (mínimo por
discapacidad) remain `input_kind = manual` in 2025. Operators/UI supply the
statutory supplement amounts directly, as on the physical AEAT form.

## What was done

### S246-S248 — Parameter declarations (registry authority anchors)

Added 9 new statutory parameter files to
`src/aeat/_data/registry/aeat/modelos/100/revisions/2024/parameters/`:

| Parameter ID | Value | Authority |
|---|---|---|
| `renta-2024-minimo-contribuyente-edad-65-74-2024` | 1,150 EUR | LIRPF Art. 57.2 |
| `renta-2024-minimo-contribuyente-edad-75-2024` | 1,400 EUR | LIRPF Art. 57.3 |
| `renta-2024-minimo-descendientes-primer-hijo-2024` | 2,400 EUR | LIRPF Art. 58 |
| `renta-2024-minimo-descendientes-segundo-hijo-2024` | 2,700 EUR | LIRPF Art. 58 |
| `renta-2024-minimo-descendientes-tercer-hijo-2024` | 4,000 EUR | LIRPF Art. 58 |
| `renta-2024-minimo-descendientes-cuarto-y-siguientes-2024` | 4,500 EUR | LIRPF Art. 58 |
| `renta-2024-minimo-descendientes-menor-tres-anos-2024` | 3,000 EUR | LIRPF Art. 58 |
| `renta-2024-minimo-ascendientes-mayor-65-2024` | 1,150 EUR | LIRPF Art. 59 |
| `renta-2024-minimo-ascendientes-mayor-75-2024` | 1,400 EUR | LIRPF Art. 59 |

Also added:
- Legal catalogue entries for `ley-35-2006:art-58` and `ley-35-2006:art-59`
  in `src/aeat/_data/registry/aeat/legal/irpf.toml`
- Corpus HTML excerpts at `src/aeat/_data/corpus/normatives/html/ley-35-2006-art-58.html`
  and `ley-35-2006-art-59.html`

### S249 — Regression tests

Three supplement scenarios added to
`src/aeat/domain/calculations/registry/test_modelo_100_tarifa_real.py`:

| Scenario | Supplement input | Expected cuota estatal |
|---|---|---|
| Pere age 70 (Art. 57.2) | 0513=1,150 | 3,763.25 EUR |
| 2 descendants, 1 under 3 (Art. 58) | 0513=8,100 | 3,073.00 EUR |
| Ascendant over 75 (Art. 59) | 0515=2,550 | 3,630.25 EUR |

All expected values derived from published LIRPF 2024 escala estatal tables.
7/7 tests pass.
