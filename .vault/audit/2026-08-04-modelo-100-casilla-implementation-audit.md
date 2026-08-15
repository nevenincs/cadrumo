---
tags:
  - '#audit'
  - '#modelo-100-casilla'
date: '2026-08-04'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:21d3a86337d6fef0070c51a4678579b5891e826dafda86005947886260aa00df'
related: []
---

# "modelo-100-casilla" audit: "Modelo 100 casilla implementation audit closure"

## Scope

This is a developer- and auditor-facing Reference audit for Cadrumo's Modelo 100
registry. Cadrumo is the local Spanish-tax calculation and export application;
Modelo 100 is the annual Spanish personal-income-tax return surface; a casilla is
one declared form field. The audit covers the validated annual "0A" snapshots for
Modelo 100 revisions 2020 through 2025.

The risk under test is a contract split: the runtime can calculate a casilla from a
formula or receive it through a typed binding while the casilla declaration says
"manual" or "informational". That split can reject a legitimate caller input,
hide a calculated value from schema consumers, or make a later revision appear
more complete than it is.

Grounding used VaultSpec RAG over:

- ".vault/adr/2026-04-21-casilla-schema-completeness-adr.md".
- ".vault/research/2026-05-27-schema-hardening-m100-revision-drift-research.md".
- ".vault/audit/2026-05-07-renta-scope-audit-audit.md".
- ".vault/audit/2026-07-03-y-siguientes-verification-audit.md".
- ".vault/exec/2026-05-26-cross-domain-continuity/2026-05-26-cross-domain-continuity-W09-P41-S298.md".

The live authority for the inventory was the bundled registry loaded through
"bundled_authority().validate_modelo('100')" and snapshotted at period "0A".
The closure pass changed the 21 previously contradictory Modelo 100 casilla
declarations, added the generic reverse formula invariant for every modelo, and
added the missing 2025 legal-reference manifest member.

### Wiring vocabulary

- "manual": the filed value is supplied upstream; no registry formula claims to
  produce it.
- "bound": the value arrives through a declared profile, prior-filing, or
  cross-model binding.
- "computed": a registry formula produces the value.
- "informational": the row is descriptive metadata, not a formula output.
- A "formula target" is the casilla named by a formula's
  "target_casilla_id".
- A "back-reference" is the casilla's "formula" field naming that same formula.
  The contract is bidirectional: formula -> casilla and casilla -> formula.
- A "relation-prefill" is a typed cross-model source, such as Modelo 131
  casilla "01" folded into an annual Modelo 100 binding. It is not the same
  thing as a formula target.
- "Declared wiring" is "computed + bound" casillas. Formula-definition count
  and binding-record count remain separate measurements.
- "0A" is the annual period used for this audit; it is not a claim that every
  form section is annual-only.
- "Coverage parity" means comparable implementation breadth between revisions. It
  is separate from the schema contract: a manual upstream surface can be valid
  even when a neighboring year contains a deeper model.

Operational Modelo 100 usage is documented in "docs/how-to/modelo-100.md". The
registry field conventions are described in "docs/reference/registry-legal-api.md".
Disputed evidence or a failed verification should be reported to the
"nevenincs/cadrumo" issue tracker with the tax year, casilla/formula/binding ID,
exact command, and output; do not include taxpayer data.

## Findings

### Modelo 100 casilla implementation closure | high | Reverse schema parity is now enforced across all modelos

The original suspicion was confirmed: 21 formula targets in Modelo 100 revisions
2020-2025 had a target casilla declared as "manual" or "informational". The
affected rows were:

| Revision | Repaired target rows |
|---|---|
| 2020 | "0529", "0531" |
| 2021 | "0224", "0529", "0531" |
| 2022 | "0224", "0529", "0531" |
| 2023 | "0224", "0529", "0531" |
| 2024 | "0224", "0245", "0246", "0247", "0531", "0613" |
| 2025 | "0245", "0246", "0247", "1548" |

Every repaired target now has "input_kind = computed" and a matching
"formula = <formula-id>" declaration.

The validator in
"src/cadrumo/domain/calculations/registry/_validate_formulas.py" now rejects
both directions of the contract:

1. A formula target that does not exist, is not "computed", or is declared with a
   different formula ID.
2. A computed casilla whose formula ID does not resolve back to the formula
   target.

The revision validator passes the casilla index into this check through
"src/cadrumo/domain/calculations/registry/_validate_revision_sections.py". The
negative contract tests prove that validation fails when a real loaded target is
mutated to "manual" and when its back-reference is removed. These are real
Pydantic registry objects; the tests do not use mocks, fakes, stubs, patches,
skips, or copied calculation logic.

The invariant is not Modelo 100-specific. The direct authority validation
covered 73 loaded modelos, and the all-modelo invariant test traverses every
revision in that loaded registry.

### Modelo 100 casilla implementation closure | high | Post-remediation inventory is internally consistent

The following is the remeasured inventory after the 21 declaration repairs.
"Declared wired" is "bound + computed"; "formula definitions" is the number of
formula records, not a claim about direct profile bindings.

| Revision | Casillas | Manual | Bound | Computed | Informational | Formula definitions | Bindings | Declared wired |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2020 | 1,531 | 1,376 | 2 | 153 | 0 | 153 | 9 | 155 |
| 2021 | 1,693 | 1,533 | 2 | 155 | 3 | 155 | 9 | 157 |
| 2022 | 1,852 | 1,676 | 2 | 171 | 3 | 171 | 9 | 173 |
| 2023 | 1,929 | 1,752 | 2 | 172 | 3 | 172 | 9 | 174 |
| 2024 | 2,093 | 1,854 | 49 | 187 | 3 | 187 | 65 | 236 |
| 2025 | 2,239 | 1,973 | 49 | 215 | 2 | 215 | 64 | 264 |

The inventory contains 11,337 revision-casilla records and 2,258 distinct
casilla IDs. Formula definitions and formula targets now match the computed
casilla count in every revision. The 2024 and 2025 binding records remain
substantially larger than in 2020-2023 because many profile and cross-model
inputs feed formulas without becoming bound casillas themselves.

### Modelo 100 casilla implementation closure | medium | Adjacent revisions remain structurally non-monotonic

The post-remediation adjacent-revision comparison uses these fixed fields:

- "Semantic drift": label, section, data type, or semantic role changed.
- "Input-kind drift": "manual", "bound", "computed", or "informational" changed.
- "Wiring drift": formula, binding, or alternate-binding metadata changed.
- Added and removed counts are ID-set differences, not semantic equivalence.

| Pair | Shared IDs | Added | Removed | Semantic drift | Input-kind drift | Wiring drift |
|---|---:|---:|---:|---:|---:|---:|
| 2020 -> 2021 | 1,500 | 193 | 31 | 425 | 4 | 156 |
| 2021 -> 2022 | 1,689 | 163 | 4 | 478 | 1 | 158 |
| 2022 -> 2023 | 1,836 | 93 | 16 | 402 | 0 | 173 |
| 2023 -> 2024 | 1,915 | 178 | 14 | 477 | 32 | 206 |
| 2024 -> 2025 | 2,083 | 156 | 10 | 686 | 31 | 264 |

For 2024 -> 2025, source references changed for all 2,083 shared IDs and legal
references changed for 1,972. Those are expected annual provenance changes
unless the legal windows overlap. The 31 input-kind changes break down as:

- 27 "manual -> computed" rows with a real 2025 formula declaration.
- Two formula-backed 2024 rows, "0150" and "0613", become 2025 manual surfaces.
- "1481" changes from a 2024 relation-bound surface to 2025 manual.
- "1577" changes from informational to a relation-bound M184 handoff.

This is why the raw divergence count must not be reported as a defect count.
The schema contradiction count is now zero; the coverage and annual-form
differences remain visible.

### Modelo 100 casilla implementation closure | high | Coverage breadth is broader in 2025 but not monotonic

At the top-level section boundary, wired means "computed + bound":

| Section | 2024 total / wired | 2025 total / wired |
|---|---:|---:|
| "datos_identificativos" | 30 / 30 | 30 / 30 |
| "rendimientos_actividades_economicas" | 4 / 1 | 59 / 26 |
| "rendimientos_capital_inmobiliario" | - | 26 / 5 |
| "rendimientos_capital_mobiliario" | - | 26 / 8 |
| "rendimientos_trabajo" | - | 26 / 7 |
| "resultado_declaracion" | - | 27 / 6 |
| "resultados" | 1,282 / 140 | 1,343 / 123 |
| "retenciones_ingresos_cuenta_pagos_fraccionados" | - | 15 / 5 |
| "toma_datos_ampliada" | 777 / 65 | 687 / 54 |

2025 adds substantial new income and result surfaces and increases total
declared wiring from 236 to 264, but it loses 17 wired rows in the inherited
"resultados" surface and 11 in "toma_datos_ampliada". The original concern that
a newer revision can be broader overall while weaker on inherited surfaces is
therefore confirmed.

### Modelo 100 casilla implementation closure | high | The three focus rows have different closure statuses

| Casilla | 2024 implementation | 2025 implementation | Status |
|---|---|---|---|
| "0150" | "computed", formula "renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2" | Manual default; no 2025 formula target | No schema contradiction. Deferred 2025 rental-reduction calculation parity; do not fabricate a producer. |
| "0613" | "computed", formula "renta-2024-incremento-guarderia-0613" | Manual default; no 2025 formula target | No schema contradiction. The profile method "incremento_guarderia_0613" explicitly supports only filing year 2024 and returns zero for other years; 2025 needs an official-source and profile-input extension before being computed. |
| "1481" | "bound" through "renta-2024-modelo-131-rendimiento-neto-modulos" | Manual default; no 2025 M131 net-modules relation/binding | The 2024 handoff is intentional cross-model relation-prefill, not a formula defect. 2025 parity is a deferred cross-model coverage item, not a formula-target contradiction. |

The "1481" decision corrects an older simplified description that treated the
filed casilla as manual in every year. The legal filed surface can remain
taxpayer/upstream supplied while the registry's 2024 calculation path receives
a typed M131 relation-prefill. The 2024 binding and relation are explicit in
"revisions/2024/bindings/0012-renta-2024-modelo-131-rendimiento-neto-modulos.toml"
and
"revisions/2024/relations/0008-renta-2024-rel-131-rendimiento-neto-modulos.toml".
No equivalent 2025 relation is present.

The 2024 "0613" formula is grounded in the real profile oracle
"src/cadrumo/domain/contribuyente/family.py", whose supported fields and method
are explicitly 2024-only. Rebinding 2025 without adding and grounding the
corresponding profile inputs would create a false computed declaration.

The 2024 "0150" formula has real operator-selected rental-reduction behavior
covered by the existing worked-example test. The 2025 result chain consumes
"0150" as an upstream value but has no 2025 producer. Keeping it manual is
honest partial coverage; silently copying the 2024 formula would be an
unsupported annual-law assumption.

These three rows therefore close the audit's review obligation by disposition,
not by pretending that 2025 coverage is complete.

### Modelo 100 casilla implementation closure | medium | 2025 legal-reference closure is complete

The calculation closure for 2025 required
"orden-hac-1347-2024:anexo-i-instruccion-2-3", already used by the 2025
objective-estimation formula and verification expectations. It was missing from
"revisions/2025/completeness-manifest.toml". Adding that manifest member closed
both completeness assertions without changing the grounded formula.

## Recommendations

### Closed at schema-audit scope

- Keep the generic reverse invariant in the load-boundary validator. It protects
  every modelo, not only Modelo 100.
- Keep both negative tests: a non-computed formula target and a missing
  formula back-reference must fail validation.
- Keep formula-definition, computed-target, bound-casilla, and binding-record
  counts separate in future reports.
- Treat annual source/legal churn as measured divergence, not as a failure unless
  an overlapping revision contract is contradicted.
- Retain the 2025 legal manifest reference and its closure tests.

### Deferred coverage parity

The following are explicit follow-up work, not silent findings:

- Decide and ground the 2025 rental-reduction producer for "0150".
- Extend the 2025 guardería profile inputs and legal source before making "0613"
  computed.
- Decide whether to carry the 2024 M131 objective-net relation-prefill into 2025
  for "1481", with a cross-model ADR/implementation and live behavior proof.
- Add a generated per-revision report surface if operators need this inventory
  outside the audit record; this document is the current measured report and
  the registry diff service remains the machine-readable comparison surface.

## Verification boundary

The closure evidence is:

- Focused schema, validator, legal-reference, and completeness lane:
  110 passed.
- The two previously failing legal-closure tests: 2 passed.
- Full registry test suite:
  3,491 passed, 2 warnings, in 149.91 seconds. The warnings are OpenPyXL
  conditional-formatting warnings from record-design tests.
- Direct authority validation: "validated_modelos 73".
- Ruff check: all checks passed.
- Ruff format check: 3 files already formatted.
- Basedpyright over the changed production validator files: 0 errors, 0 warnings,
  0 notes.
- VaultSpec Core targeted check: 0 errors and 1 non-blocking feature-index warning;
  frontmatter, Markdown, links, body-links, body-sections, and encoding checks are clean.

The full repository test suite, external AEAT probes, and a new 2025 coverage
implementation were not part of this closure pass. Therefore the precise final
verdict is:

**Modelo 100 schema and formula-wiring audit: closed.**
**Modelo 100 all-year implementation parity: not complete; three explicitly
bounded 2025 coverage follow-ups remain.**
