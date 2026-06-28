---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-schema-hardening-verification-ledger-audit]]"
---

# M100 AEIP Family Audit

## Scope

Read-only investigation of all M100 casillas in section `resultados.anexo_a_res.deducciones_inversion_empresarial_res` across revisions 2020-2025 whose label contains a quoted AEIP event name followed by `: Aplicado en esta declaracion`. These are the AEIP (Acontecimientos de Excepcional Interes Publico) sponsorship-deduction casillas mis-classified by a label-truncation bug during the original role assignment pass.

Source files: `src/aeat/_data/registry/aeat/modelos/100/revisions/*/casillas/*.toml`

## Finding

### What the family is

Every casilla in this family records the **euro amount of an AEIP event-sponsorship deduction applied in the current filing** (the "Aplicado en esta declaracion" slot in Anexo A.6 of Modelo 100). The label pattern is invariably:

```
"<event name>": Aplicado en esta declaracion
```

A small minority use an embedded-quote form:

```
<outer label> "<sub-programme name>": Aplicado en esta declaracion
```

This is seen on ID 1712 (Habitos Saludables ... Aprender a cuidarnos) and ID 1693 (Celebracion del Summit MADBLUE) — functionally identical; the quoted string is the registered AEIP programme name.

**There are no sub-variants.** Every casilla represents the same concept: the monetary amount of an AEIP deduction applied in the declaration. There is no pendiente sub-type within this family; carry-forward amounts do not appear in this sub-section.

### Family size

- Total event-family casillas: **315** across 6 revisions
- Already carrying `irpf_anexo_a_aeip_aplicado_flag`: **142**
- Carrying wrong roles: **173**

### Wrong role distribution

| current_role | count | verdict |
|---|---|---|
| `irpf_deduccion_incentivos_inversion_empresarial_estatal` | 157 | WRONG — event casilla mis-assigned |
| `irpf_anexo_a_aeip_aplicado_flag` | 142 | rename target — drop _flag suffix |
| `irpf_anexo_c_exceso_eeficiencia_pendiente_fin` | 5 | WRONG — event casilla mis-assigned |
| `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio` | 4 | WRONG — event casilla mis-assigned |
| `irpf_anexo_c_exceso_eeficiencia_aplicado` | 3 | WRONG — event casilla mis-assigned |
| `irpf_deduccion_contribuciones_empresariales_prevision_social_aplicado` | 2 | WRONG — event casilla mis-assigned |
| `irpf_anexo_b_carry_forward_remaining` | 1 | WRONG — event casilla mis-assigned |
| `irpf_anexo_a_rib_pendiente_materializar` | 1 | WRONG — event casilla mis-assigned |

## Canonical role decision

**The correct semantic role for every event-family casilla is `irpf_anexo_a_aeip_aplicado`** (without the `_flag` suffix).

Justification:

- **The `_flag` suffix is factually wrong.** A flag signals a boolean or indicator field. Every one of these 315 casillas carries a euro money amount (the deduction applied), not a boolean indicator. The name `irpf_anexo_a_aeip_aplicado_flag` was assigned by the buggy pass that truncated labels to the opening quote character; the `_flag` portion reflects a classification error, not the AEAT field type.

- **The label is authoritative.** Every casilla uses the construction `"<AEIP registered programme name>": Aplicado en esta declaracion` drawn from the AEAT official source dictionary and XSD. AEAT Anexo A.6 is titled Regimen especial de apoyo a los acontecimientos de excepcional interes publico; the Aplicado en esta declaracion column is the current-year applied deduction amount per named event under `ley-35-2006:art-68.2` and LIS art-36 / art-39. Legal refs are identical across all 315 casillas.

- **No split required.** All 315 casillas say Aplicado; none say Pendiente. A single canonical role covers the entire family.

- **The existing `irpf_anexo_a_aeip_aplicado_flag` role must be renamed** to `irpf_anexo_a_aeip_aplicado`. Its 137 non-event members require separate reclassification — they are generic LIS-chapter deduction sub-totals and Canarias/Baleares entries that happen to share the old role name.

## Role assignments

All 315 event casillas should carry `irpf_anexo_a_aeip_aplicado`.

| id | revision | current_role | correct_role | label_snippet |
|---|---|---|---|---|
| 0700 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | VIII Centenario de la Catedral de Burgos 2021 |
| 0706 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Andalucía Valderrama Masters 2022/2024 |
| 0706 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Andalucía Valderrama Masters 2022/2024 |
| 0706 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Andalucía Valderrama Masters 2022/2024 |
| 0706 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Music Lab. El Futuro de la Música |
| 0707 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Bicentenario de la Policia Nacional |
| 0707 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Bicentenario de la Policia Nacional |
| 0707 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Bicentenario de la Policia Nacional |
| 0707 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Bicentenario de la Policia Nacional |
| 0757 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"175 Aniversario de la construcción del Gran Teat |
| 0757 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Gran Premio de España de Fórmula 1 |
| 0757 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Gran Premio de España de Fórmula 1 |
| 0757 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Gran Premio de España de Fórmula 1 |
| 0757 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Primavera Sound, created in Barcelona |
| 0760 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | VIII Centenario de la Universidad de Salamanca |
| 0760 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario Federación Aragonesa de Fútbol |
| 0760 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario Federación Aragonesa de Fútbol |
| 0760 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Año Tàpies. Cien años del nacimiento del artista |
| 0761 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"20 Aniversario de la Reapertura del Gran Teatro  |
| 0761 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Plan 2030 de Apoyo al Deporte de Base |
| 0761 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Plan 2030 de Apoyo al Deporte de Base |
| 0761 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Plan 2030 de Apoyo al Deporte de Base |
| 0761 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Eduardo Chillida 100 años |
| 0762 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Enfermedades Neurodegenerativas 2020. Año Intern |
| 0762 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Universo Mujer III |
| 0762 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Universo Mujer III |
| 0762 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Universo Mujer III |
| 0762 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"VIII Centenario de la Catedral gótica de Toledo, |
| 0764 | 2020 | irpf_deduccion_contribuciones_empresariales_prevision_social_aplicado | irpf_anexo_a_aeip_aplicado | \"España País Invitado de Honor en la Feria del Li |
| 0764 | 2021 | irpf_deduccion_contribuciones_empresariales_prevision_social_aplicado | irpf_anexo_a_aeip_aplicado | \"España País Invitado de Honor en la Feria del Li |
| 0764 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"España País Invitado de Honor en la Feria del Li |
| 0765 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"175 Aniversario de la construcción del Gran Teat |
| 0765 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"175 Aniversario de la construcción del Gran Teat |
| 0765 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"175 Aniversario de la construcción del Gran Teat |
| 0765 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"175 Aniversario de la construcción del Gran Teat |
| 0765 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Año Santo Jacobeo 2027 |
| 0766 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Programa de preparación de los deportistas españ |
| 0766 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Programa de preparación de los deportistas españ |
| 0766 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Programa de preparación de los deportistas españ |
| 0766 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Programa de preparación de los deportistas españ |
| 0766 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Programa de preparación de los deportistas españ |
| 0766 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Centenario de la Generación del 27 |
| 0767 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 4ª Edición de la Barcelona World Race |
| 0767 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 4ª Edición de la Barcelona World Race |
| 0767 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 4ª Edición de la Barcelona World Race |
| 0767 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 4ª Edición de la Barcelona World Race |
| 0767 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Música clásica para todos |
| 0768 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 100 años del fallecimiento de Joaquín Sorolla |
| 0768 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 100 años del fallecimiento de Joaquín Sorolla |
| 0768 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 100 años del fallecimiento de Joaquín Sorolla |
| 0768 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 150.º aniversario del nacimiento de Pau Casals |
| 0769 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Petit Liceu |
| 0773 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 20 Aniversario de Primavera Sound |
| 0773 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 20 Aniversario de Primavera Sound |
| 0773 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 20 Aniversario de Primavera Sound |
| 0776 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"V Centenario de la expedición de la primera vuel |
| 0776 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"V Centenario de la expedición de la primera vuel |
| 0776 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"V Centenario de la expedición de la primera vuel |
| 0779 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Plan de Fomento de la Lectura (2017-2020) |
| 0779 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Centenario del nacimiento de Victoria de los Áng |
| 0779 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Centenario del nacimiento de Victoria de los Áng |
| 0779 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Centenario del nacimiento de Victoria de los Áng |
| 0779 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Fundación Joan Miró 50.º aniversario |
| 0780 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan Decenio Milliarium Montserrat 1025-2025 |
| 0780 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan Decenio Milliarium Montserrat 1025-2025 |
| 0780 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan Decenio Milliarium Montserrat 1025-2025 |
| 0780 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan Decenio Milliarium Montserrat 1025-2025 |
| 0780 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario Gaudí 2026 |
| 0781 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"50 Edición del Festival Internacional de Jazz de |
| 0781 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Conmemoración del 50 aniversario de la muerte de |
| 0781 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Conmemoración del 50 aniversario de la muerte de |
| 0781 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Conmemoración del 50 aniversario de la muerte de |
| 0781 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Quincuagésimo aniversario del Teatre Lliure |
| 0782 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Campeonato Mundial Junior Balonmano Masculino 2019 |
| 0782 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Todos contra el cáncer |
| 0782 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Todos contra el cáncer |
| 0782 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Todos contra el cáncer |
| 0783 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Campeonato Mundial Balonmano Femenino 2021 |
| 0783 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Campeonato Mundial Balonmano Femenino 2021 |
| 0783 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Año de Investigación Santiago Ramón y Cajal 2022 |
| 0783 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Año de Investigación Santiago Ramón y Cajal 2022 |
| 0783 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Año de Investigación Santiago Ramón y Cajal 2022 |
| 0783 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Año de Investigación Santiago Ramón y Cajal 2022 |
| 0784 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Andalucía Valderrama Masters |
| 0784 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Andalucía Valderrama Masters |
| 0784 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Año Jubilar Lebaniego 2023-2024 |
| 0784 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Año Jubilar Lebaniego 2023-2024 |
| 0784 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Año Jubilar Lebaniego 2023-2024 |
| 0784 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Año Jubilar Lebaniego 2023-2024 |
| 0785 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | La Transición: 40 años de Libertad de Expresión |
| 0785 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Mundo Voluntario 2030/35º Aniversario Plataforma |
| 0785 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Mundo Voluntario 2030/35º Aniversario Plataforma |
| 0785 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Vigésimo aniversario del Festival Bilbao BBK Live |
| 0786 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Mobile World Capital |
| 0786 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"7ª Conferencia Mundial sobre Turismo Enológico d |
| 0786 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"7ª Conferencia Mundial sobre Turismo Enológico d |
| 0786 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"7ª Conferencia Mundial sobre Turismo Enológico d |
| 0786 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"75.ª edición del Festival Música y Danza de Gran |
| 0787 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Ceuta y la Legión, 100 años de unión |
| 0787 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Caravaca de la Cruz 2024. Año Jubilar |
| 0787 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Caravaca de la Cruz 2024. Año Jubilar |
| 0787 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Caravaca de la Cruz 2024. Año Jubilar |
| 0787 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Caravaca de la Cruz 2024. Año Jubilar |
| 0788 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Bádminton World Tour |
| 0788 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Bádminton World Tour |
| 0788 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Bicentenario del Ateneo de Madrid |
| 0788 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Bicentenario del Ateneo de Madrid |
| 0788 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Bicentenario del Ateneo de Madrid |
| 0788 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"150.º aniversario del nacimiento de Manuel de Fa |
| 0791 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Nuevas Metas |
| 0791 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Nuevas Metas |
| 0791 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Equestrian Challenge (4ª Edición) |
| 0791 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Equestrian Challenge (4ª Edición) |
| 0791 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Equestrian Challenge (4ª Edición) |
| 0791 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Dansàneu, Festival de Cultures del Pirineu |
| 0793 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Equestrian Challenge (3ª Edición) |
| 0793 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Equestrian Challenge (3ª Edición) |
| 0793 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 200 ANIVERSARIO DEL PASSEIG DE GRÁCIA |
| 0793 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 200 ANIVERSARIO DEL PASSEIG DE GRÁCIA |
| 0793 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 200 ANIVERSARIO DEL PASSEIG DE GRÁCIA |
| 0793 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | San Diego Comic-Con Málaga |
| 0795 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Universo Mujer (II) |
| 0795 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Universo Mujer (II) |
| 0795 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Programa de preparación de los deportistas españ |
| 0796 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Logroño 2021, nuestro V Centenario |
| 0796 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Logroño 2021, nuestro V Centenario |
| 0796 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Reconstucción de la Piscina Histórica cubierta d |
| 0796 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Reconstucción de la Piscina Histórica cubierta d |
| 0796 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Reconstucción de la Piscina Histórica cubierta d |
| 0796 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Universo Mujer IV |
| 0797 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Centenario de Delibes |
| 0797 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Centenario de Delibes |
| 0797 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | ALIMENTARIA 2022 |
| 0797 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | ALIMENTARIA 2022 |
| 0797 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | ALIMENTARIA 2022 |
| 0797 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Gran Premio de España de Motociclismo |
| 0798 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Año Santo Jacobeo 2021 |
| 0798 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Año Santo Jacobeo 2021 |
| 0798 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Año Santo Jacobeo 2021 |
| 0798 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Deporte Inclusivo III |
| 0800 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | VIII Centenario de la Catedral de Burgos 2021 |
| 0800 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | VIII Centenario de la Catedral de Burgos 2021 |
| 0801 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Deporte Inclusivo |
| 0801 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Deporte Inclusivo |
| 0804 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan 2020 de Apoyo al Deporte de Base II |
| 0804 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan 2020 de Apoyo al Deporte de Base II |
| 0805 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | España, Capital del Talento Joven |
| 0806 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Conmemoración del Centenario de la Coronación de |
| 0807 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Traslado de la Imagen de Nuestra Señora del Rocí |
| 0808 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Camino Lebaniego |
| 0808 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Camino Lebaniego |
| 0809 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Expo Dubai 2020 |
| 0809 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Expo Dubai 2020 |
| 0809 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Expo Dubai 2020 |
| 0810 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | AUTOMOBILE BARCELONA 2019 |
| 0810 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | AUTOMOBILE BARCELONA 2019 |
| 0811 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"XXV Aniversario de la Declaración por la UNESCO  |
| 0815 | 2020 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan Berlanga |
| 0815 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan Berlanga |
| 0815 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan Berlanga |
| 0815 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan Berlanga |
| 0817 | 2020 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Plan de Fomento de la ópera en la Calle del Teat |
| 0817 | 2021 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Plan de Fomento de la ópera en la Calle del Teat |
| 0817 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Plan de Fomento de la ópera en la Calle del Teat |
| 0817 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Plan de Fomento de la ópera en la Calle del Teat |
| 0817 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Plan de Fomento de la ópera en la Calle del Teat |
| 0817 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Plan de Fomento de la ópera en la Calle del Teat |
| 1623 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | HOSTELCO 2022 |
| 1623 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | HOSTELCO 2022 |
| 1623 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | HOSTELCO 2022 |
| 1623 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Plan 2030 de Apoyo al Deporte Base II |
| 1627 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Music Lab. El futuro de la música |
| 1627 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Music Lab. El futuro de la música |
| 1627 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Music Lab. El futuro de la música |
| 1627 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Ironman Calella-Barcelona |
| 1628 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Global Mobility Call |
| 1629 | 2022 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | South Summit 2022-2024 |
| 1629 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | South Summit 2022-2024 |
| 1629 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | South Summit 2022-2024 |
| 1629 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Barcelona Mobile World Capital |
| 1630 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Año Santo Jubilar San Isidro Labrador |
| 1630 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Año Santo Jubilar San Isidro Labrador |
| 1689 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Alicante 2021. Salida Vuelta al Mundo a Vela |
| 1689 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Alicante 2021. Salida Vuelta al Mundo a Vela |
| 1689 | 2023 | irpf_anexo_a_rib_pendiente_materializar | irpf_anexo_a_aeip_aplicado | Alicante 2021. Salida Vuelta al Mundo a Vela |
| 1689 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Alicante 2021. Salida Vuelta al Mundo a Vela |
| 1690 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Bicentenarios de la independencia de las Republi |
| 1690 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Bicentenarios de la independencia de las Republi |
| 1690 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Bicentenarios de la independencia de las Republi |
| 1691 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"150 Aniversario de creación de la Academia de Es |
| 1691 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"150 Aniversario de creación de la Academia de Es |
| 1691 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"150 Aniversario de creación de la Academia de Es |
| 1692 | 2021 | irpf_anexo_c_exceso_eeficiencia_pendiente_inicio | irpf_anexo_a_aeip_aplicado | \"125 aniversario de la Asociación de Prensa de Ma |
| 1692 | 2023 | irpf_anexo_c_exceso_eeficiencia_pendiente_inicio | irpf_anexo_a_aeip_aplicado | Torneo Davis Cup Madrid |
| 1693 | 2021 | irpf_anexo_c_exceso_eeficiencia_aplicado | irpf_anexo_a_aeip_aplicado | MADBLUE |
| 1693 | 2022 | irpf_anexo_c_exceso_eeficiencia_aplicado | irpf_anexo_a_aeip_aplicado | MADBLUE |
| 1693 | 2023 | irpf_anexo_c_exceso_eeficiencia_aplicado | irpf_anexo_a_aeip_aplicado | MADBLUE |
| 1694 | 2021 | irpf_anexo_c_exceso_eeficiencia_pendiente_fin | irpf_anexo_a_aeip_aplicado | \"30 Aniversario de la Escuela Superior de Música  |
| 1694 | 2022 | irpf_anexo_c_exceso_eeficiencia_pendiente_fin | irpf_anexo_a_aeip_aplicado | \"30 Aniversario de la Escuela Superior de Música  |
| 1694 | 2023 | irpf_anexo_c_exceso_eeficiencia_pendiente_fin | irpf_anexo_a_aeip_aplicado | \"30 Aniversario de la Escuela Superior de Música  |
| 1695 | 2021 | irpf_anexo_c_exceso_eeficiencia_pendiente_inicio | irpf_anexo_a_aeip_aplicado | Año Santo Guadalupense 2021 |
| 1695 | 2022 | irpf_anexo_c_exceso_eeficiencia_pendiente_inicio | irpf_anexo_a_aeip_aplicado | Año Santo Guadalupense 2021 |
| 1697 | 2021 | irpf_anexo_c_exceso_eeficiencia_pendiente_fin | irpf_anexo_a_aeip_aplicado | Torneo Davis Cup Madrid |
| 1697 | 2022 | irpf_anexo_c_exceso_eeficiencia_pendiente_fin | irpf_anexo_a_aeip_aplicado | Torneo Davis Cup Madrid |
| 1698 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | MADRID HORSE WEEK 21/23 |
| 1698 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | MADRID HORSE WEEK 21/23 |
| 1698 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | MADRID HORSE WEEK 21/23 |
| 1699 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Centenario del Rugby en España y de la Unió Espo |
| 1699 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Centenario del Rugby en España y de la Unió Espo |
| 1699 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Centenario del Rugby en España y de la Unió Espo |
| 1700 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Solheim Cup 2023 |
| 1700 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Solheim Cup 2023 |
| 1700 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Solheim Cup 2023 |
| 1701 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | IX Centenario de la Reconquista de Sigüenza |
| 1701 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | IX Centenario de la Reconquista de Sigüenza |
| 1701 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | IX Centenario de la Reconquista de Sigüenza |
| 1701 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | IX Centenario de la Reconquista de Sigüenza |
| 1702 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Barcelona Mobile World Capital |
| 1702 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Barcelona Mobile World Capital |
| 1702 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Barcelona Mobile World Capital |
| 1703 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Valencia, Capital Mundial del Diseño 2022 / Vale |
| 1703 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Valencia, Capital Mundial del Diseño 2022 / Vale |
| 1703 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Valencia, Capital Mundial del Diseño 2022 / Vale |
| 1704 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Cincuenta aniversario de la Universidad Nacional |
| 1704 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Cincuenta aniversario de la Universidad Nacional |
| 1705 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario de Revista de Occidente |
| 1705 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario de Revista de Occidente |
| 1705 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario de Revista de Occidente |
| 1706 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"50 aniversario del fallecimiento de Clara Campoa |
| 1706 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"50 aniversario del fallecimiento de Clara Campoa |
| 1706 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"50 aniversario del fallecimiento de Clara Campoa |
| 1706 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"50 aniversario del fallecimiento de Clara Campoa |
| 1707 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"V Centenario del fallecimiento de Elio Antonio d |
| 1707 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"V Centenario del fallecimiento de Elio Antonio d |
| 1707 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"V Centenario del fallecimiento de Elio Antonio d |
| 1708 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Nuevas Metas II |
| 1708 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Nuevas Metas II |
| 1708 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Nuevas Metas II |
| 1708 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Nuevas Metas II |
| 1709 | 2021 | irpf_anexo_b_carry_forward_remaining | irpf_anexo_a_aeip_aplicado | \"250 aniversario del Museo Nacional de Ciencias n |
| 1710 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Andalucía Región Europea del Deporte 2021 |
| 1710 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Andalucía Región Europea del Deporte 2021 |
| 1710 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Andalucía Región Europea del Deporte 2021 |
| 1711 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 75 aniversario de la Ópera en Oviedo |
| 1711 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 75 aniversario de la Ópera en Oviedo |
| 1711 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 75 aniversario de la Ópera en Oviedo |
| 1712 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Aprender a cuidarnos |
| 1712 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Aprender a cuidarnos |
| 1712 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Aprender a cuidarnos |
| 1713 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Mundiales Bádminton España |
| 1713 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Mundiales Bádminton España |
| 1713 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Mundiales Bádminton España |
| 1714 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario de la Batalla de Covadonga-Cuadonga |
| 1714 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario de la Batalla de Covadonga-Cuadonga |
| 1714 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario de la Batalla de Covadonga-Cuadonga |
| 1715 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"VII Centenario de la Catedral de Palencia 2021-2 |
| 1715 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"VII Centenario de la Catedral de Palencia 2021-2 |
| 1715 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"VII Centenario de la Catedral de Palencia 2021-2 |
| 1716 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | FITUR especial: recuperación turismo |
| 1716 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | FITUR especial: recuperación turismo |
| 1716 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | FITUR especial: recuperación turismo |
| 1717 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Programa Deporte lnclusivo |
| 1717 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Programa Deporte lnclusivo |
| 1717 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Programa Deporte lnclusivo II |
| 1717 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Programa Deporte lnclusivo II |
| 1718 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Valencia 2020-2021, Año Jubilar. Camino del Sant |
| 1718 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Valencia 2020-2021, Año Jubilar. Camino del Sant |
| 1719 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Enfermedades Neurodegenerativas. Año lnternacion |
| 1719 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"Enfermedades Neurodegenerativas. Año lnternacion |
| 1720 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 50 aniversario del Hospital Sant Joan de Deu |
| 1720 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 50 aniversario del Hospital Sant Joan de Deu |
| 1720 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 50 aniversario del Hospital Sant Joan de Deu |
| 1721 | 2021 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | El tiempo de la libertad, Comuneros V Centenario |
| 1721 | 2022 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | El tiempo de la libertad, Comuneros V Centenario |
| 1944 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Inauguración de la Galería de las Colecciones Re |
| 1944 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Inauguración de la Galería de las Colecciones Re |
| 1944 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Inauguración de la Galería de las Colecciones Re |
| 1945 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario del Hockey 1923-2023 |
| 1945 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Centenario del Hockey 1923-2023 |
| 1946 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | \"60 Aniversario Rally Blendio Princesa de Asturia |
| 1947 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 60 aniversario del Festival Porta Ferrada |
| 1947 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 60 aniversario del Festival Porta Ferrada |
| 1947 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 60 aniversario del Festival Porta Ferrada |
| 1948 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Programa EN PLAN BIEN |
| 1948 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Programa EN PLAN BIEN |
| 1948 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Programa EN PLAN BIEN |
| 1949 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | 125 aniversario del Athletic Club 1898-2023 |
| 1950 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Ryder Cup 2031 |
| 1950 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Ryder Cup 2031 |
| 1950 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Ryder Cup 2031 |
| 1951 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Open Barcelona-Trofeo Conde de Godó |
| 1951 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Open Barcelona-Trofeo Conde de Godó |
| 1951 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Open Barcelona-Trofeo Conde de Godó |
| 1952 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 125 aniversario del Real Club de Tenis Barcelona |
| 1952 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 125 aniversario del Real Club de Tenis Barcelona |
| 1952 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 125 aniversario del Real Club de Tenis Barcelona |
| 1953 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 750 aniversario del Consolat del Mar |
| 1953 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 750 aniversario del Consolat del Mar |
| 1953 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | 750 aniversario del Consolat del Mar |
| 1954 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Congreso de la Unión Internacional de Arquitectos |
| 1954 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Congreso de la Unión Internacional de Arquitectos |
| 1954 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Congreso de la Unión Internacional de Arquitectos |
| 1955 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Festival Internacional Sónar de Música, Creativi |
| 1955 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Festival Internacional Sónar de Música, Creativi |
| 1955 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | \"Festival Internacional Sónar de Música, Creativi |
| 1956 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | XXXVII Copa América Barcelona |
| 1956 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | XXXVII Copa América Barcelona |
| 1956 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | XXXVII Copa América Barcelona |
| 1957 | 2023 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Programa deportivo 'RETO DE' |
| 1957 | 2024 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Programa deportivo 'RETO DE' |
| 1957 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Programa deportivo 'RETO DE' |
| 1958 | 2023 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Celebración de la Bienal Manifesta 15 Barcelona |
| 1958 | 2024 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Celebración de la Bienal Manifesta 15 Barcelona |
| 2060 | 2025 | irpf_deduccion_incentivos_inversion_empresarial_estatal | irpf_anexo_a_aeip_aplicado | Barcelona 2026 Capital Mundial de la Arquitectura |
| 2061 | 2025 | irpf_anexo_a_aeip_aplicado_flag | irpf_anexo_a_aeip_aplicado | Rally Islas Canarias |

## Non-event members to leave untouched

These casillas share one of the 8 affected roles but are NOT AEIP event casillas and must not be touched by an AEIP-targeted fix pass.

### `irpf_anexo_a_aeip_aplicado_flag` (137 non-event members)

| id | revision | label_snippet |
|---|---|---|
| 0706 | 2020 | Importe de los pagos realizados en el ejercicio al promotor o al const |
| 0752 | 2020 | Deducciones acogidas al régimen general de la Ley del Impuesto sobre S |
| 0752 | 2021 | Deducciones acogidas al régimen general de la Ley del Impuesto sobre S |
| 0752 | 2022 | Deducciones acogidas al régimen general de la Ley del Impuesto sobre S |
| 0752 | 2023 | Deducciones acogidas al régimen general de la Ley del Impuesto sobre S |
| 0752 | 2024 | Deducciones acogidas al régimen general de la Ley del Impuesto sobre S |
| 0752 | 2025 | Deducciones acogidas al régimen general de la Ley del Impuesto sobre S |
| 0753 | 2020 | Regímenes especiales de apoyo a acontecimientos de excepcional interés |
| 0753 | 2021 | Regímenes especiales de apoyo a acontecimientos de excepcional interés |
| 0753 | 2022 | Regímenes especiales de apoyo a acontecimientos de excepcional interés |
| 0753 | 2023 | Regímenes especiales de apoyo a acontecimientos de excepcional interés |
| 0753 | 2024 | Regímenes especiales de apoyo a acontecimientos de excepcional interés |
| 0753 | 2025 | Regímenes especiales de apoyo a acontecimientos de excepcional interés |
| 0754 | 2020 | Actividades de investigación y desarrollo e innovación tecnológica (ar |
| 0754 | 2021 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0754 | 2022 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0754 | 2023 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0754 | 2024 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0754 | 2025 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0755 | 2020 | Por inversiones en producciones cinematográficas, series audiovisuales |
| 0755 | 2021 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0755 | 2022 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0755 | 2023 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0755 | 2024 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0755 | 2025 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0756 | 2020 | Creación de empleo para trabajadores con discapacidad (art. 38º de la  |
| 0756 | 2021 | Creación de empleo para trabajadores con discapacidad (art. 38º de la  |
| 0756 | 2022 | Creación de empleo para trabajadores con discapacidad (art. 38º de la  |
| 0756 | 2023 | Creación de empleo para trabajadores con discapacidad (art. 38º de la  |
| 0756 | 2024 | Creación de empleo para trabajadores con discapacidad (art. 38º de la  |
| 0756 | 2025 | Creación de empleo para trabajadores con discapacidad (art. 38 de la L |
| 0758 | 2020 | Por inversión en beneficios (art. 37º del TRLIS, D.T. 24ª LIS) (solo s |
| 0758 | 2021 | Por inversión en beneficios (art. 37º del TRLIS, D.T. 24ª LIS) (solo s |
| 0758 | 2022 | Por inversión en beneficios (art. 37º del TRLIS, D.T. 24ª LIS) (solo s |
| 0758 | 2023 | Por inversión en beneficios (art. 37º del TRLIS, D.T. 24ª LIS) (solo s |
| 0758 | 2024 | Por inversión en beneficios (art. 37º del TRLIS, DT 24ª LIS) (solo si  |
| 0758 | 2025 | Por inversión en beneficios (art. 37 del TRLIS, DT 24ª LIS) (solo si e |
| 0759 | 2020 | Deducción por inversiones en territorios de África Occidental (art.º 2 |
| 0759 | 2021 | Deducción por inversiones en territorios de África Occidental (art.º 2 |
| 0759 | 2022 | Deducción por inversiones en territorios de África Occidental (art.º 2 |
| 0759 | 2023 | Deducción por inversiones en territorios de África Occidental (art.º 2 |
| 0759 | 2024 | Deducción por inversiones en territorios de África Occidental (art. 27 |
| 0759 | 2025 | Por inversiones en territorios de África Occidental (art. 27.1.a) bis  |
| 0769 | 2022 | Por donaciones para paliar los efectos del conflicto de Ucrania sobre  |
| 0837 | 2020 | Inversiones en la adquisición de activos fijos: Aplicado en esta decla |
| 0837 | 2021 | Inversiones en la adquisición de activos fijos: Aplicado en esta decla |
| 0837 | 2022 | Inversiones en la adquisición de activos fijos: Aplicado en esta decla |
| 0837 | 2023 | Inversiones en la adquisición de activos fijos: Aplicado en esta decla |
| 0837 | 2024 | Inversiones en la adquisición de activos fijos: Aplicado en esta decla |
| 0837 | 2025 | Inversiones en la adquisición de activos fijos: Aplicado en esta decla |
| 0838 | 2020 | Restantes modalidades: Aplicado en esta declaración |
| 0838 | 2021 | Restantes modalidades: Aplicado en esta declaración |
| 0838 | 2022 | Restantes modalidades: Aplicado en esta declaración |
| 0838 | 2023 | Restantes modalidades: Aplicado en esta declaración |
| 0838 | 2024 | Restantes modalidades: Aplicado en esta declaración |
| 0838 | 2025 | Restantes modalidades: Aplicado en esta declaración |
| 0839 | 2020 | Actividades de investigación y desarrollo e innovación tecnológica (ar |
| 0839 | 2021 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0839 | 2022 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0839 | 2023 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0839 | 2024 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0839 | 2025 | Por actividades de investigación y desarrollo (art. 35.1 de la LIS): A |
| 0840 | 2020 | Por inversiones en producciones cinematográficas, series audiovisuales |
| 0840 | 2021 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0840 | 2022 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0840 | 2023 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0840 | 2024 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0840 | 2025 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 0841 | 2020 | Creación de empleo para trabajadores con discapacidad (art.º 38 de la  |
| 0841 | 2021 | Creación de empleo para trabajadores con discapacidad (art.º 38 de la  |
| 0841 | 2022 | Creación de empleo para trabajadores con discapacidad (art.º 38 de la  |
| 0841 | 2023 | Creación de empleo para trabajadores con discapacidad (art.º 38 de la  |
| 0841 | 2024 | Creación de empleo para trabajadores con discapacidad (art.º 38 de la  |
| 0841 | 2025 | Creación de empleo para trabajadores con discapacidad (art.º 38 de la  |
| 0842 | 2021 | Por mínimo personal, familiar y por discapacidad para residentes en la |
| 0842 | 2022 | Por mínimo personal, familiar y por discapacidad para residentes en la |
| 0842 | 2023 | Por contribuciones empresariales a sistemas de previsión social (D.A.  |
| 0842 | 2024 | Por contribuciones empresariales a sistemas de previsión social (D.A.  |
| 0842 | 2025 | Por contribuciones empresariales a sistemas de previsión social (D.A.  |
| 0843 | 2020 | Deducción por gastos de propaganda y publicidad (art.º 27.1.b) bis de  |
| 0843 | 2021 | Deducción por gastos de propaganda y publicidad (art.º 27.1.b) bis de  |
| 0843 | 2022 | Deducción por gastos de propaganda y publicidad (art.º 27.1.b) bis de  |
| 0843 | 2023 | Deducción por gastos de propaganda y publicidad (art.º 27.1.b) bis de  |
| 0843 | 2024 | Deducción por gastos de propaganda y publicidad (art. 27.1.b) bis de l |
| 0843 | 2025 | Por gastos de propaganda y publicidad (art. 27.1.b) bis de la Ley 19/1 |
| 0844 | 2020 | Ejercicio 2020. Inversiones en la adquisición de activos fijos: Aplica |
| 0844 | 2021 | Ejercicio 2021. Inversiones en la adquisición de activos fijos: Aplica |
| 0844 | 2022 | Ejercicio 2022. Inversiones en la adquisición de activos fijos: Aplica |
| 0844 | 2023 | Ejercicio 2023. Inversiones en la adquisición de activos fijos: Aplica |
| 0844 | 2024 | Ejercicio 2024. Inversiones en la adquisición de activos fijos: Aplica |
| 0844 | 2025 | Ejercicio 2025. Inversiones en la adquisición de activos fijos: Aplica |
| 1686 | 2021 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1686 | 2022 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1686 | 2023 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1686 | 2024 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1686 | 2025 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1687 | 2021 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1687 | 2022 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1687 | 2023 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1687 | 2024 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1687 | 2025 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1688 | 2021 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1688 | 2022 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1688 | 2023 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1688 | 2024 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1688 | 2025 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1722 | 2022 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 1722 | 2023 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 1722 | 2024 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 1722 | 2025 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 1723 | 2022 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1723 | 2023 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1723 | 2024 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1723 | 2025 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1727 | 2021 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1727 | 2022 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1727 | 2023 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1727 | 2024 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1727 | 2025 | Por actividades de innovación tecnológica (art. 35.2 LIS): Aplicado en |
| 1728 | 2021 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1728 | 2022 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1728 | 2023 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1728 | 2024 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1728 | 2025 | Por inversiones en producciones cinematográficas extranjeras en España |
| 1729 | 2021 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1729 | 2022 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1729 | 2023 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1729 | 2024 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1729 | 2025 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1730 | 2022 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 1730 | 2023 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 1730 | 2024 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 1730 | 2025 | Por inversiones en producciones cinematográficas y series audiovisuale |
| 1731 | 2022 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1731 | 2023 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1731 | 2024 | Por inversiones en producciones de espectáculos en vivo de artes escén |
| 1731 | 2025 | Por inversiones en producciones de espectáculos en vivo de artes escén |

### `irpf_anexo_a_rib_pendiente_materializar` (6 non-event members)

| id | revision | label_snippet |
|---|---|---|
| 1689 | 2025 | Reserva para Inversiones en las Illes Balears 2023: Pendiente de mater |
| 1784 | 2024 | Reserva para Inversiones en las Illes Balears 2023: Pendiente de mater |
| 1784 | 2025 | Reserva para Inversiones en las Illes Balears 2024: Pendiente de mater |
| 1941 | 2023 | Reserva para Inversiones en las Illes Balears 2023: Pendiente de mater |
| 1941 | 2024 | Reserva para Inversiones en las Illes Balears 2024: Pendiente de mater |
| 1941 | 2025 | Reserva para Inversiones en las Illes Balears 2025: Pendiente de mater |

### `irpf_anexo_b_carry_forward_remaining` (21 non-event members)

| id | revision | label_snippet |
|---|---|---|
| 1117 | 2020 | Importe satisfecho en 2017, 2018 y/o 2019 pendiente de aplicación en e |
| 1117 | 2021 | Importe satisfecho en 2018 pendiente de aplicación en ejercicios futur |
| 1117 | 2022 | Importe aplicado en el ejercicio |
| 1117 | 2023 | Por el pago de intereses de préstamos para adquisición de vivienda por |
| 1117 | 2024 | Por el pago de intereses de préstamos para adquisición de vivienda por |
| 1117 | 2025 | Por el pago de intereses de préstamos para adquisición de vivienda por |
| 1120 | 2020 | Importe satisfecho en 2020 pendiente de aplicación en ejercicios futur |
| 1120 | 2021 | Importe satisfecho en 2021 pendiente de aplicación en ejercicios futur |
| 1120 | 2022 | Importe satisfecho en 2022 pendiente de aplicación en ejercicios futur |
| 1120 | 2023 | Por la obtención de la condición de familia numerosa |
| 1120 | 2024 | Importe de la deducción |
| 1120 | 2025 | Importe de la deducción |
| 1186 | 2021 | Importe satisfecho en 2019 y/o 2020 pendiente de aplicación en ejercic |
| 1186 | 2022 | Importe satisfecho en 2019 y/o 2020 pendiente de aplicación en ejercic |
| 1186 | 2023 | Importe satisfecho en 2020 pendiente de aplicación en ejercicios futur |
| 1186 | 2024 | Importe generado en 2023 pendiente de aplicación |
| 1186 | 2025 | Importe generado en 2024 pendiente de aplicación |
| 1709 | 2022 | Importe satisfecho en 2021 pendiente de aplicación en ejercicios futur |
| 1709 | 2023 | Importe satisfecho en 2021 y/o 2022 pendiente de aplicación en ejercic |
| 1709 | 2024 | Importe satisfecho en 2021 y/o 2022 pendiente de aplicación en ejercic |
| 1709 | 2025 | Importe satisfecho en 2022 pendiente de aplicación en ejercicios futur |

### `irpf_anexo_c_exceso_eeficiencia_aplicado` (11 non-event members)

| id | revision | label_snippet |
|---|---|---|
| 1693 | 2024 | Ejercicio 2021: Aplicado en esta  declaración |
| 1693 | 2025 | Ejercicio 2022: Aplicado en esta  declaración |
| 1696 | 2022 | Reserva para Inversiones en Canarias 2016 (1): Inversiones previstas e |
| 1696 | 2023 | Ejercicio 2021: Aplicado en esta  declaración |
| 1696 | 2024 | Ejercicio 2022: Aplicado en esta  declaración |
| 1696 | 2025 | Ejercicio 2023: Aplicado en esta  declaración |
| 1855 | 2022 | Ejercicio 2021: Aplicado en esta  declaración |
| 1855 | 2023 | Ejercicio 2022: Aplicado en esta  declaración |
| 1855 | 2024 | Ejercicio 2023: Aplicado en esta  declaración |
| 1855 | 2025 | Ejercicio 2024: Aplicado en esta  declaración |
| 2025 | 2025 | Ejercicio 2021: Aplicado en esta  declaración |

### `irpf_anexo_c_exceso_eeficiencia_pendiente_fin` (9 non-event members)

| id | revision | label_snippet |
|---|---|---|
| 1694 | 2024 | Ejercicio 2021: Pendiente de aplicación en ejercicios futuros |
| 1697 | 2023 | Ejercicio 2021: Pendiente de aplicación en ejercicios futuros |
| 1697 | 2024 | Ejercicio 2022: Pendiente de aplicación en ejercicios futuros |
| 1697 | 2025 | Ejercicio 2023: Pendiente de aplicación en ejercicios futuros |
| 1856 | 2022 | Ejercicio 2021: Pendiente de aplicación en ejercicios futuros |
| 1856 | 2023 | Ejercicio 2022: Pendiente de aplicación en ejercicios futuros |
| 1856 | 2024 | Ejercicio 2023: Pendiente de aplicación en ejercicios futuros |
| 1856 | 2025 | Ejercicio 2024: Pendiente de aplicación en ejercicios futuros |
| 2048 | 2025 | Ejercicio 2022: Pendiente de aplicación en ejercicios futuros |

### `irpf_anexo_c_exceso_eeficiencia_pendiente_inicio` (11 non-event members)

| id | revision | label_snippet |
|---|---|---|
| 1692 | 2022 | Reserva para Inversiones en Canarias 2016 (1): Inversiones previstas e |
| 1692 | 2024 | Ejercicio 2021: Pendiente de aplicación  al principio del periodo |
| 1692 | 2025 | Ejercicio 2022: Pendiente de aplicación  al principio del periodo |
| 1695 | 2023 | Ejercicio 2021: Pendiente de aplicación  al principio del periodo |
| 1695 | 2024 | Ejercicio 2022: Pendiente de aplicación  al principio del periodo |
| 1695 | 2025 | Ejercicio 2023: Pendiente de aplicación  al principio del periodo |
| 1854 | 2022 | Ejercicio 2021: Pendiente de aplicación  al principio del periodo |
| 1854 | 2023 | Ejercicio 2022: Pendiente de aplicación  al principio del periodo |
| 1854 | 2024 | Ejercicio 2023: Pendiente de aplicación  al principio del periodo |
| 1854 | 2025 | Ejercicio 2024: Pendiente de aplicación  al principio del periodo |
| 2024 | 2025 | Ejercicio 2021: Pendiente de aplicación  al principio del periodo |

### `irpf_deduccion_contribuciones_empresariales_prevision_social_aplicado` (3 non-event members)

| id | revision | label_snippet |
|---|---|---|
| 0764 | 2023 | Por contribuciones empresariales a sistemas de previsión social (D.A.  |
| 0764 | 2024 | Por contribuciones empresariales a sistemas de previsión social (D.A.  |
| 0764 | 2025 | Por contribuciones empresariales a sistemas de previsión social (D.A.  |

### `irpf_deduccion_incentivos_inversion_empresarial_estatal` (7 non-event members)

| id | revision | label_snippet |
|---|---|---|
| 0554 | 2020 | Por incentivos y estímulos a la inversión empresarial (traslade los im |
| 0554 | 2021 | Por incentivos y estímulos a la inversión empresarial (traslade los im |
| 0554 | 2022 | Por incentivos y estímulos a la inversión empresarial (traslade los im |
| 0554 | 2023 | Por incentivos y estímulos a la inversión empresarial (traslade los im |
| 0554 | 2024 | Por incentivos y estímulos a la inversión empresarial (traslade los im |
| 0554 | 2025 | Por incentivos y estímulos a la inversión empresarial (importe de esta |
| 0814 | 2020 | \"Vigésimo quinta sesión de la Conferencia de las Partes de la Convenc |

**Note on ID 0814 rev=2020:** This casilla appears in the non-event table because
its stored label is truncated (ends with `...` rather than `": Aplicado en esta
declaracion"`) — the "Aplicado" tail was lost by the same parsing bug. Inspection of
the raw TOML confirms it is the COP25 event casilla (Vigésimo quinta sesión de la
Conferencia de las Partes COP25) in `deducciones_inversion_empresarial_res`.
A fix pass should include `(id=0814, rev=2020)` → `irpf_anexo_a_aeip_aplicado`.
The total requiring correction is therefore **174** (173 from the main table + this one).

## ID-reuse hazard

The following casilla IDs host different event names across revisions. Any automated fix script must target **(id, revision)** pairs, never bare IDs.

Affected IDs (46 total):

`0706`, `0757`, `0760`, `0761`, `0762`, `0765`, `0766`, `0767`, `0768`, `0779`, `0780`, `0781`, `0782`, `0783`, `0784`, `0785`, `0786`, `0787`, `0788`, `0791`, `0793`, `0795`, `0796`, `0797`, `0798`, `0801`, `0808`, `0809`, `0810`, `0815`, `1623`, `1627`, `1629`, `1692`, `1693`, `1695`, `1697`, `1698`, `1700`, `1702`, `1705`, `1708`, `1711`, `1713`, `1716`, `1717`
