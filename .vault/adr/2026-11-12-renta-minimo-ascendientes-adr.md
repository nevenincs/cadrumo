---
tags:
  - '#adr'
  - '#renta-minimo-ascendientes'
date: '2026-11-12'
modified: '2026-11-12'
body_schema: 'body-v2'
body_hash: 'sha256:7d11795bb44b25fd1c9d9a5e66b2d2d7f181bf4d6f85f822cf740462ab2d8ec4'
related:
  - "[[2026-11-02-desktop-renta-renta-family-canonical-adr]]"
  - "[[2026-07-04-autonomic-deduccion-framework-adr]]"
  - '[[2026-11-12-renta-minimo-ascendientes-reference]]'
---

# `renta-minimo-ascendientes` adr: `Ascendant row facts for the minimo por ascendientes and the disability minimum` | (**status:** `accepted`)

## Problem Statement

The minimo por ascendientes (LIRPF art. 59) and the disability minimum for an ascendant (art. 60.2) depend on facts about each ascendant that the profile does not hold on feature/tui: annual income excluding exempt income, whether the ascendant files a return of their own and with what income (art. 61 norma 2ª), and the disability grade with the assistance and judicial circumstances. The 2022 Modelo 100 binding reads `renta_family.ascendiente.{n}.discapacidad_clave` for the XML column PCTMINASDLG (`src/cadrumo/_data/registry/aeat/modelos/100/revisions/2022/bindings/0001-declarations.toml:541`), a leaf the schema does not declare, which `2026-11-02-desktop-renta-renta-family-canonical-adr` records as having no canonical leaf. Applying either minimum without these facts can only lower the tax, so an unstated deciding fact must block. The S50 unit adds row leaves for part of this (`src/cadrumo/application/user_profile/ascendant_rows.py:79` on lane/calc-renta); persisted leaves need a recorded decision before they land.

## Considerations

- Art. 59.1: 1.150 euros for each ascendant over 65 or with a disability, who lives with the taxpayer and has no annual income, excluding exempt income, above 8.000 euros (`src/cadrumo/_data/corpus/normatives/html/ley-35-2006-art-59.html.extracted.md`).
- Art. 61 norma 2ª: no minimum when the ascendant files a return with income above 1.800 euros; norma 3ª: circumstances are those at devengo; norma 5ª: cohabitation for at least half the period (`ley-35-2006-art-61.html.extracted.md`).
- Art. 60.2 and the Manual Renta 2025 part 1 lines 42486 to 42500: 3.000 euros for a grade of 33 % to under 65 %, 9.000 euros from 65 %, and 3.000 more for assistance of third persons or reduced mobility, or a grade of 65 % or more.
- The official export key PCTMINASDLG takes 1 (33 to under 65 %), 2 (the same with assistance or reduced mobility), 3 (65 % or more) and 4 (judicial incapacitation), per the 2025 XSD `03-100-esquema-xsd-ejercicio-2025-...xsd:1510` and dictionary `01-100-diccionario-...-2025-...properties:42`. The key is a function of the grade and two circumstances; it is not an independent fact.
- `src/cadrumo/domain/user_profile/schema_migration.py:1-5`: each schema bump that changes what a stored value means carries its own transition.
- PRIME 15:16 and 15:19 rulings; the operator rule that surfaces render served facts only.

## Considered options

- Store the official key as entered (the current binding's assumption): rejected. It duplicates the grade, can contradict it, and cannot drive art. 60.2 amounts without decoding.
- Store grade only: rejected. Keys 2 and 4 and the art. 60.2 assistance increment need circumstances the grade does not carry.
- Store the grade with two circumstance leaves and derive the key: chosen.
- A separate income leaf for the own return: rejected. Art. 61 norma 2ª compares the income the ascendant declares, which is the same annual income excluding exempt income that art. 59.1 reads; one leaf serves both.

## Constraints

- Each deciding fact is three-state: absent is unstated, never false or zero. A row that omits a fact that decides entitlement withholds the minimum, which stays unresolved and blocks verification and export, with a typed note naming the row and leaf and a door to the ascendant edit.
- Amounts, thresholds (8.000, 1.800, 33 %, 65 %, ages) and key values come from the registry for the edition, never from code.
- The export key is derived at calculation; it is never stored or typed by the operator.
- Ascendant rows hold private data: served only through the profile-bound read, never logged.
- Accepted by PRIME on 2026-11-12 at 15:30 under the operator's ADR delegation, approved by the operator at 13:27, with these binding conditions:
  1. `convivientes` is a deciding three-state fact for the art. 61 norma 1ª prorrateo among taxpayers entitled to the same ascendant.
  2. Cohabitation for at least half the tax period (art. 61 norma 5ª; up to the death date when the ascendant dies), with internment in a specialised centre counting as cohabitation (art. 59.1), is a deciding three-state leaf or a cited derivation; unstated, it blocks.
  3. Judicial incapacity counts as a grade of 65 % or more for the art. 60 amounts (art. 60.3) and governs over a lower stated grade.
  4. Age, the art. 59.2 over-75 increment and every circumstance are taken at devengo (art. 61 norma 3ª), or at the death date for an ascendant who died in the period (art. 61 norma 4ª).
  5. The profile schema change takes the next version free at landing.

## Implementation

We will declare these leaves on `renta_family.ascendiente.{n}`, besides `nif`, `apellidos_nombre`, `birth_date`, `fallecimiento` and `convivientes`:

- `rentas_anuales`: annual income excluding exempt income, a non-negative euro amount (art. 59.1; also the income of art. 61 norma 2ª).
- `declaracion_propia`: whether the ascendant files a return of their own (art. 61 norma 2ª); with `true`, `rentas_anuales` above the registry limit removes the minimum.
- `discapacidad`: the statutory disability grade as a whole percentage, 0 for none (art. 60).
- `discapacidad_asistencia`: whether the ascendant needs assistance of third persons or has reduced mobility (art. 60.2 increment; key 2).
- `incapacidad_judicial`: whether a judicial resolution of the civil jurisdiction declares the incapacity or establishes representative guardianship, which the export reports as key 4.

The PCTMINASDLG binding reads a derived selector that maps grade and circumstances to the key through a registry vocabulary for the edition; `discapacidad_clave` is retired as a stored leaf. The minimo por ascendientes aggregates of S50 (`renta_family.ascendientes_minimos_aggregate` and `_autonomico`) are the derived consumers of art. 59. The art. 60.2 disability minimum for ascendants is not derived by this decision: while it is not computed, a row whose stated grade reaches the registry threshold blocks that minimum as not computed rather than leaving it silent.

Schema: the change takes the next profile schema version after feature/tui at the time it lands (PRIME 15:19: LIFECYCLE's Modelo 202 election takes 10, so this takes 11). The bump is required by the schema's own rule because a stored `discapacidad_clave` changes meaning: its migration clears that value with a history event and a typed cleared path asking for the grade and the two circumstances, since keys 1 and 2 cannot be converted into a grade. The other leaves are additive: an existing row without them reads as unstated.

## Rationale

One stored fact per legal circumstance keeps the minimum, the disability minimum and the export key consistent, and lets each derive from law-dated registry data. The key is derived because the XSD defines it from the grade and two circumstances; storing it would allow a return whose key and minimum disagree.

## Consequences

- Benefits: the ascendant minimum is computed from stated facts and blocks when a deciding fact is unstated; the export key cannot contradict the grade.
- Costs: existing rows must be completed before the minimum resolves; a stored key is cleared and asked again; the art. 60.2 ascendant disability minimum stays an explicit blocking gap until its own unit.
- Reconsider if an official design starts to carry the grade itself or a key value not derivable from these facts.
