---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: 2026-05-26
modified: '2026-05-26'
step_id: "task-28"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-adr]]"
---

# declaracion-extraction-architecture task-28 — M303 2021-2022 template-revision extraction profile

## Outcome

Commit `6960ff174` delivers a new `2023-y-siguientes` M303 registry revision (year_from=2023)
carrying the original 12-casilla extraction profile, and bounds the existing `2009-y-siguientes`
revision at year_to=2022 with a 4-casilla old-template profile. All 15/15 M303 corpus PDFs now
pass their respective coverage gates: 7 new 2021-2022 round-trip tests green, 8 existing 2023-2024
tests unaffected.

## Registry layout post-migration

```
303/
  manifest.toml
  revisions/
    2009-y-siguientes/          year_from=2009, year_to=2022
      casillas/0001-casillas.toml
      export/000{1,2,3}-export-layout.toml
      extraction_profiles/0001-modelo-303-declaracion-pdf.toml   ← 4 casillas
      revision.toml
    2023-y-siguientes/          year_from=2023, year_to=open
      casillas/0001-casillas.toml
      export/000{1,2,3}-export-layout.toml
      extraction_profiles/0001-modelo-303-declaracion-pdf.toml   ← 12 casillas
      revision.toml
```

## Schema support finding

The registry schema DOES support multiple template-revisions for different year ranges via the
`ModeloRevision.period_selector` (`year_from`/`year_to`). `select_revision` in `_temporal.py`
selects exactly one revision per `(modelo, filing_year, period)` tuple. Period-selector overlap
is validated by `validate_revision_windows`. The M123 precedent (`2019-2023` + `2024-y-siguientes`)
was followed exactly.

No schema changes were required.

## 2021-2022 vs 2023+ layout differences

The 2021-2022 M303 printed form differs from 2023+ in the results section (page 3):

| Feature | 2021-2022 | 2023+ |
|---------|-----------|-------|
| Formula brackets | `( [27] - [45] )` | `(27 - 45)` |
| Result values (64, 66, 69, 71) | Isolated bare lines, no label adjacent | Label+value on same line |
| Box 27 label line | Ends with bare box number `27` in some specimens | Ends with `27 1.000,00` |
| Box 110 (cuotas pendientes) | No value adjacent to label | `110 1.000,00` adjacent |

In 2021-3T through 2022-4T the sanitiser places all amounts on completely isolated lines
(`1.000,00` alone), making named-label and numeric-casilla strategies both fail for
casillas 64, 66, 69, 71, 110, 78, 87.

## Slug → printed-box mapping for old-template targets

| Slug | Box | Printed label (matched) | Notes |
|------|-----|------------------------|-------|
| `27` | 27 | `Total cuota devengada` | Value adjacent in 2021-2T/3T/4T/2022-2T; bare box number `27` in 2022-1T/3T/4T |
| `29` | 29 | `Por cuotas soportadas en operaciones interiores corrientes` | Value always adjacent |
| `45` | 45 | `Total a deducir` | Value always adjacent |
| `iva.resultado-regimen-general` | 46 | `Resultado r[eé]gimen general \([\[\s]*27[\]\s]*-[\[\s]*45[\]\s]*\)` | Pattern matches both bracket notations |

## Round-trip count

7/7 new 2021-2022 PDFs pass. 8/8 existing 2023-2024 PDFs continue to pass. 15/15 total.

## All-26-modelos valid

Registry validation: 26 modelos valid (the pre-existing M100/M190 relation error for
`renta-2025-rel-190-retenciones-anuales` is unrelated to this task and pre-dates it).

## Semantic role cardinality fix

`iva_compensacion_pendiente_anteriores` and `iva_compensacion_pendiente_posteriores` were
`intentional_singleton` in `2009-y-siguientes`. Adding `2023-y-siguientes` with the same casillas
triggered the cardinality validator. Both casillas updated to `semantic_role_cardinality = "shared"`
(the default) in both revision casilla files; the now-invalid `semantic_role_cardinality_reason`
fields were removed.
