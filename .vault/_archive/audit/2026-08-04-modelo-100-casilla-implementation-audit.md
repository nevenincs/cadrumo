---
tags:
  - '#audit'
  - '#modelo-100-casilla'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:6e73c56f8223e30e6f5c00fb2954eaf56d22193c6dd1bfad2a0801113e463f76'
related:
  - "[[2026-05-27-schema-hardening-m100-revision-drift-research]]"
  - "[[2026-04-21-casilla-schema-completeness-adr]]"
---
# \`modelo-100-casilla\` audit: \`Modelo 100 casilla implementation audit\`

## Scope

This audit records the pre-implementation assessment of Modelo 100 casilla definitions and wiring across revisions 2020â€“2025. The comparison source was the validated registry snapshot for each annual \`0A\` revision, not directory counts or completeness manifests.

## Findings

### Modelo 100 casilla implementation audit | high | Formula-driven casillas are inconsistently declared

Verdict: the suspected inconsistency is confirmed. There are genuine formula-driven casillas whose schema declaration remains \`manual\` or \`informational\`. The validator and runtime currently accept contradictory declarations.

The audit was grounded with \`vaultspec-rag\` using \`.vault/adr/2026-04-21-casilla-schema-completeness-adr.md\`, \`.vault/research/2026-05-27-schema-hardening-m100-revision-drift-research.md\`, and \`.vault/audit/2026-05-07-renta-scope-audit-audit.md\`. Counts were remeasured from \`bundled_authority().validate_modelo("100").snapshot(..., period="0A").revision\`.

### Modelo 100 casilla implementation audit | high | Exhaustive inventory shows non-monotonic wiring coverage

| Revision | Casillas | Manual | Bound | Computed | Informational | Formula definitions | Bindings | Declared wired |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 1,531 | 1,378 | 2 | 151 | 0 | 153 | 9 | 153 / 9.99% |
| 2021 | 1,693 | 1,535 | 2 | 152 | 4 | 155 | 9 | 154 / 9.10% |
| 2022 | 1,852 | 1,678 | 2 | 168 | 4 | 171 | 9 | 170 / 9.18% |
| 2023 | 1,929 | 1,754 | 2 | 169 | 4 | 172 | 9 | 171 / 8.86% |
| 2024 | 2,093 | 1,859 | 49 | 181 | 4 | 187 | 65 | 230 / 10.99% |
| 2025 | 2,239 | 1,977 | 49 | 211 | 2 | 215 | 64 | 260 / 11.61% |

Total: 11,337 revision-casilla records and 2,258 distinct casilla IDs.

Declared wired means \`bound + computed\`. The runtime actually has 153, 155, 171, 172, 187, and 215 formula targets respectively, so the declared schema understates the runtime calculation surface by 2â€“4 casillas per revision.

### Modelo 100 casilla implementation audit | high | Twenty-one formula targets violate the declaration contract

| Revision | Target declared incorrectly |
|---|---|
| 2020 | \`0529\`, \`0531\` â†’ manual |
| 2021 | \`0224\` â†’ informational; \`0529\`, \`0531\` â†’ manual |
| 2022 | \`0224\` â†’ informational; \`0529\`, \`0531\` â†’ manual |
| 2023 | \`0224\` â†’ informational; \`0529\`, \`0531\` â†’ manual |
| 2024 | \`0224\` â†’ informational; \`0245\`, \`0246\`, \`0247\`, \`0531\`, \`0613\` â†’ manual |
| 2025 | \`0245\`, \`0246\`, \`0247\`, \`1548\` â†’ manual |

These are 21 formula definitions whose target casilla is not \`computed\`.

Examples:

- 2024 \`0224\` is explicitly informational, while a formula targets it.
- 2025 \`0224\`, \`0529\`, and \`0531\` are correctly marked computed, demonstrating that the declaration was repaired there.
- 2024/2025 \`0245â€“0247\` have profile-derived selector formulas but default to manual because their casilla fragments omit \`input_kind\` and \`formula\`.
- 2025 \`1548\` has no computed declaration, yet formula \`0293\` targets it.
- The 2025 casilla fragment for \`1548\` contains no \`input_kind\` or \`formula\`, so it defaults to manual.

The schema defaults \`input_kind\` to manual and \`formula\` to \`None\` in \`src/cadrumo/domain/calculations/registry/_schema_surfaces.py\`. Its validators enforce â€œcomputed must have formulaâ€� and â€œbound must have binding,â€� but do not enforce the reverse relationship: formula target â‡’ computed casilla. The record-section validator only checks that formula targets exist and expressions are referentially valid in \`src/cadrumo/domain/calculations/registry/_validate_record_sections.py\`.

The runtime nevertheless builds a formula map from every formula target and records formula provenance in \`src/cadrumo/domain/calculations/registry/_formula_runtime.py\`. Initial-value handling also rejects caller inputs for every formula target, even when its declared kind is manual or informational, in \`src/cadrumo/domain/calculations/registry/_formula_initial_values.py\`.

### Modelo 100 casilla implementation audit | medium | Adjacent revisions have substantial structural drift

| Pair | Shared IDs | Added | Removed | Semantic drift | Input-kind drift | Wiring drift |
|---|---:|---:|---:|---:|---:|---:|
| 2020â†’2021 | 1,500 | 193 | 31 | 425 | 5 | 154 |
| 2021â†’2022 | 1,689 | 163 | 4 | 478 | 1 | 155 |
| 2022â†’2023 | 1,836 | 93 | 16 | 402 | 0 | 170 |
| 2023â†’2024 | 1,915 | 178 | 14 | 477 | 29 | 200 |
| 2024â†’2025 | 2,083 | 156 | 10 | 686 | 31 | 259 |

Semantic drift covers label, section, data type, and semantic role. Wiring drift covers formula, binding, and alternate bindings.

For 2024â†’2025 specifically:

- \`legal_refs\` changed for 1,972 shared IDs.
- \`source_refs\` changed for all 2,083 shared IDs, largely because annual source references are revision-specific.
- 31 repeated IDs changed \`input_kind\`.
- Two changes are regressions requiring explicit review: \`0150\` computedâ†’manual and \`1481\` boundâ†’manual.
- 27 changes are manualâ†’computed, and \`1577\` changed informationalâ†’bound.

The raw drift numbers must not all be treated as defects: annual Modelo 100 forms are legally distinct, and source citation churn is expected. Structural wiring drift should be reviewed separately from provenance drift.

### Modelo 100 casilla implementation audit | high | Coverage is non-monotonic by section

| Section | 2024 total / wired | 2025 total / wired |
|---|---:|---:|
| \`rendimientos_actividades_economicas\` | 4 / 0 | 59 / 26 |
| \`resultados\` | 1,282 / 135 | 1,343 / 120 |
| \`toma_datos_ampliada\` | 777 / 65 | 687 / 53 |
| \`rendimientos_capital_inmobiliario\` | â€” | 26 / 5 |
| \`rendimientos_capital_mobiliario\` | â€” | 26 / 8 |
| \`rendimientos_trabajo\` | â€” | 26 / 7 |
| \`resultado_declaracion\` | â€” | 27 / 6 |
| \`retenciones_ingresos_cuenta_pagos_fraccionados\` | â€” | 15 / 5 |

2025 improves overall declared wiring by 30 casillas, but loses 15 wired casillas in \`resultados\` and 12 in \`toma_datos_ampliada\`. Newer revisions can therefore be broader overall while being weaker on inherited surfaces.

Bindings also changed sharply:

- 2020â€“2023: 9 binding records each, only 2 bound casillas.
- 2024: 65 binding records, 49 bound casillas.
- 2025: 64 binding records, 49 bound casillas.

Many profile bindings feed formulas directly rather than appearing as \`bound\` casillas, so binding-record counts and bound-casilla counts must remain separate metrics.

### Modelo 100 casilla implementation audit | medium | Existing tests do not enforce reverse formula parity

The official grounding is present: \`test_modelo_100_registry.py\` verifies the 2020â€“2025 revisions against the official record-design manifest, dictionaries, input dictionaries, and \`0A\` periods. Source-tier checks are in \`test_modelo_100_source_tiering.py\`.

Passing evidence at audit time:

- Modelo 100 registry tests: 8 passed.
- Drift/source tests: 56 passed.
- Real calculation behavior tests: 30 passed.
- Cross-dependency contract tests: 15 passed.

These tests validate loading, source grounding, referential integrity, and selected calculations. They do not enforce formula-target/casilla-kind parity; that is the uncovered defect.

## Recommendations

1. Add a reverse schema invariant: every formula target must be \`computed\` and must reference the same formula ID from its casilla declaration.
2. Decide whether \`0245â€“0247\` are calculated selectors or user inputs; do not leave them as implicit manual defaults.
3. Review the 21 mismatch rows and the 31 input-kind changes, prioritizing \`0224\`, \`0529\`, \`0531\`, \`0613\`, \`1481\`, \`1548\`, and \`0150\`.
4. Add a generated per-revision audit report separating casilla inventory, declared wiring, formula targets, direct binding inputs, source/provenance drift, and semantic/wiring drift.
5. Keep annual legal/source drift non-failing unless the revisions overlap legally; fail only true contract contradictions.

## Verification boundary

This document captures the audit state before the subsequent implementation edits. The original audit worktree was read-only with respect to Modelo 100; unrelated shared-worktree WIP was preserved.
