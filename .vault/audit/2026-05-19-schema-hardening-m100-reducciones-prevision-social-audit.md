---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
---

# M100 schema-hardening audit — reducciones-prevision-social cluster

## Scope

Sections covered: `red_prevision_social`, `red_discapacidad`,
`red_patrimonio_protegido_discapacidad`, `red_deportistas`,
`red_pensiones_compensatorias_alimentos` (including the typo variant
`red_pensiones_comensatorias_alimentos` — treated as the same concept domain).

Revision range observed: 2020–2025.

Total casilla ids in cluster: 20 (casillas 0382, 0383, 0426, 0427, 0428, 0437,
0438, 0463, 0464, 0465, 0466, 0467, 0472, 0473, 0474, 0475, 0479, 0480, 0484,
0485, 0488, 0489, 0499).

Note: the JSON contains 20 unique top-level ids. Casillas 0471 and 0483 are
referenced in the TOML files for this section but are NOT present in the cluster
JSON (they already carry `disabled_person_nif` and `pension_recipient_nif`
respectively and are not unroled). They appear in the Id-reuse hazards section
for context only.

## Role assignments

Where a casilla id exhibits clear id-reuse (different concept in different
revision ranges), a separate row is emitted per concept with non-overlapping
`revisions_present`.

| id | role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|
| 0382 | `irpf_red_prevision_social_empleador_nif_extranjero_flag` | Si no tiene NIF, marque con una "X" | boolean | 2023, 2024, 2025 | Foreign-NIF indicator for employer in the previsión-social data-entry block. New role. |
| 0383 | `irpf_red_prevision_social_rendimientos_trabajo_rango_flag` | Si los rendimientos íntegros del trabajo de este empleador en el ejercicio son iguales o inferiores / superiores | boolean | 2023, 2024, 2025 | Boolean flag distinguishing the income-threshold band (≤ or >) for this employer's work income. Two distinct label variants represent the same discriminant concept. New role. |
| 0426 | `irpf_red_prevision_social_aportaciones_trabajador_con_contribucion_empresarial` | Aportaciones del trabajador al plan de pensiones de empleo, mutualidad de previsión social... siempre que se hayan efectuado contribuciones empresariales | money(default) | 2021, 2022, 2023, 2024, 2025 | Worker's own contributions where employer also contributes. Label changed phrasing in 2022-2025 (employer-contributions framing) but concept is identical. New role. |
| 0427 | `irpf_red_prevision_social_contribuciones_empresariales_excepto_scd` | Contribuciones (excepto contribuciones empresariales a seguros colectivos de dependencia) | money(default) | 2021, 2022, 2023, 2024, 2025 | Employer contributions to previsión social systems, excluding colectivos de dependencia insurance. Label was tightened in 2022+ but concept is consistent. New role. |
| 0428 | `irpf_red_prevision_social_aportaciones_ejercicio_2021` | Aportaciones del ejercicio 2021 | money(default) | 2021 | Current-year (2021) individual/worker contributions, present only in the 2021 revision when the form split out this line. New role. |
| 0437 | `irpf_red_prevision_social_exceso_2016_2020` | Excesos pendientes de reducir procedentes de los ejercicios 2016 a 2020 | money(default) | 2021 | Carry-forward excess from years 2016–2020, present only in 2021 revision. New role. |
| 0438 | `irpf_red_prevision_social_aportaciones_empresa_decision_trabajador` | Aportaciones efectuadas por la empresa que deriven de una decisión del trabajador | money(default) | 2022, 2023, 2024, 2025 | Employer contributions that derive from an employee election (voluntary salary sacrifice). New role. |
| 0463 (concept A) | `irpf_red_prevision_social_exceso_2015_2019` | Excesos pendientes de reducir procedentes de los ejercicios 2015 a 2019 (excepto los derivados de contrib. empresariales a seguros colectivos de dependencia) | money(default) | 2020 | **Id-reuse row A.** In revision 2020 this id carried the older carry-forward excess block (origin 2015–2019). New role. |
| 0463 (concept B) | `irpf_red_prevision_social_aportaciones_individuales_contribuciones_empresariales` | Aportaciones individuales y contribuciones empresariales (excepto los derivados de contrib. empresariales a seguros colectivos de dependencia) | money(default) | 2021 | **Id-reuse row B.** In revision 2021 the same id was repurposed for current-year individual + employer contributions (combined line). New role. |
| 0463 (concept C) | `irpf_red_prevision_social_aportaciones_individuales` | Aportaciones individuales (Cumplimente el anexo C.2) | money(default) | 2022, 2023, 2024, 2025 | **Id-reuse row C.** From 2022 onward the id holds only individual contributions; the employer-contributions line was split off. New role. |
| 0464 | `irpf_red_prevision_social_exceso_scd` | Excesos derivados de contribuciones empresariales a seguros colectivos de dependencia / Excesos pendientes de reducir procedentes de los ejercicios 2015 a 2019 derivados de contribuciones empresariales a scd | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Carry-forward and current-exercise excess from employer contributions to colectivos de dependencia insurance. Label wording evolved but the underlying SCD-excess concept is stable across all six revisions. New role. |
| 0465 | `irpf_red_prevision_social_aportaciones_trabajador` | Aportaciones del trabajador, salvo las consignadas en [0438] y [0426] / Aportaciones | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | General worker/individual contributions not captured in the more specific [0426] or [0438] lines. Earlier revisions used a simpler "Aportaciones" label; concept is consistent. New role. |
| 0466 | `irpf_red_prevision_social_contribuciones_scd` | Contribuciones a seguros colectivos de dependencia | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Employer contributions to collective dependency-risk insurance policies for current exercise. New role. |
| 0467 | `irpf_red_prevision_social_importes_derecho_reduccion` | Importes con derecho a reducción ([0463]+[0464]+[0465]+... ) (Límite máximo artículo...) | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Aggregate total of all amounts entitled to reduction under Art. 52 / Art. 49 LIRPF. Formula composition changed across revisions as sub-lines were restructured but the aggregate-total role is stable. New role. |
| 0472 | `irpf_red_discapacidad_exceso_aportaciones_propias` | Excesos pendientes de reducir procedentes de los ejercicios 20XX a 20YY por aportaciones realizadas por la propia persona con discapacidad | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Carry-forward excess from own-person disability contributions. Origin-year window shifts each revision (e.g. "2015–2019" in 2020, "2020–2024" in 2025) but the concept — excess from disability-person's own aportaciones — is stable. New role. |
| 0473 | `irpf_red_discapacidad_exceso_aportaciones_parientes` | Excesos pendientes de reducir procedentes de los ejercicios 20XX a 20YY por aportaciones realizadas por parientes o tutores | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Carry-forward excess from relatives'/tutors' disability contributions. Same rolling-window pattern as 0472. New role. |
| 0474 | `irpf_red_discapacidad_aportaciones_propias` | Aportaciones realizadas en 20XX por la propia persona con discapacidad | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Current-year contributions by the disabled person themselves. Year in label matches the revision year (rolling); concept is stable. New role. |
| 0475 | `irpf_red_discapacidad_aportaciones_parientes` | Aportaciones realizadas en 20XX por parientes o tutores a favor de la persona con discapacidad | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Current-year contributions by relatives or legal guardians on behalf of the disabled person. New role. |
| 0479 | `irpf_red_patrimonio_protegido_discapacidad_exceso` | Excesos pendientes de reducir procedentes de los ejercicios 20XX a 20YY (Vea el anexo C.3/C.4) | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Carry-forward excess from prior-year protected-estate contributions. Rolling origin window. New role. |
| 0480 | `irpf_red_patrimonio_protegido_discapacidad_aportaciones` | Aportaciones realizadas en 20XX al patrimonio protegido de la persona con discapacidad | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Current-year contributions to the legally protected estate of the disabled person. New role. |
| 0484 | `irpf_red_pensiones_compensatorias_receptor_nif_extranjero_flag` | Marque una "X" si en la casilla [0483] ha consignado un NIF de otro País | boolean | 2020, 2021, 2022, 2023, 2024, 2025 | Foreign-NIF indicator for the pension/annuity recipient. Appears under both section spellings (typo `comensatorias` and canonical `compensatorias`) — same concept. New role. |
| 0485 | `irpf_red_pensiones_compensatorias_importe` | Importe de la pensión o anualidad satisfecha en 20XX por decisión judicial | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Amount of compensatory pension or maintenance annuity paid under court order. Year in label is the current filing year. Appears under both section-name spellings — same concept. New role. |
| 0488 | `irpf_red_deportistas_exceso` | Excesos pendientes de reducir procedentes de los ejercicios 20XX a 20YY (Vea el anexo C.3/C.4) | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Carry-forward excess from prior years for the professional athletes' special regime (Art. 46 LIRPF). Origin-year window shifts annually. Note: 2021 label references "2017 a 2021" range, no separate 2021 label in JSON — the 2021 revision is still present in `revs`. New role. |
| 0489 | `irpf_red_deportistas_aportaciones_contribuciones` | Aportaciones y contribuciones realizadas en 20XX con derecho a reducción | money(default) | 2020, 2021, 2022, 2023, 2024, 2025 | Current-year contributions by or for professional athletes entitled to the special regime reduction. New role. |
| 0499 | `irpf_red_prevision_social_aportaciones_autonomos_empresarios` | Aportaciones de trabajadores por cuenta propia o autónomos, empresarios individuales o profesionales a planes de pensiones de empleo o mutualidades | money(default) | 2022, 2023, 2024, 2025 | Self-employed persons' and sole-trader professionals' contributions to occupational pension plans or mutual societies. Introduced with the 2022 reform expanding the self-employed pension pillar. New role. |

## Id-reuse hazards

**0463 — three distinct concepts across revision range 2020–2025.**

In revision 2020 the id held the pre-reform carry-forward block "Excesos
pendientes de reducir procedentes de los ejercicios 2015 a 2019 (excepto los
derivados de contribuciones empresariales a seguros colectivos de dependencia)".
In revision 2021 the form restructured and 0463 became "Aportaciones individuales
y contribuciones empresariales (excepto los derivados de contribuciones
empresariales a seguros colectivos de dependencia)". From 2022 onward the
employer-contributions component was again split off and 0463 narrowed to
individual contributions only ("Aportaciones individuales").
Three non-overlapping rows emitted in the Role assignments table (concepts A, B, C).

**0472 and 0473 — rolling origin-year windows.**

Both carry-forward casillas for own-person and parientes disability aportaciones
show six distinct label variants (one per revision), each shifting the referenced
origin-year range by one year. The underlying concept is stable in each case, so
a single role covers all revisions. Implementors must note that the human-visible
year range in the label is the filing year minus N years, not a fixed historical
period.

**0479 and 0488 — same rolling pattern in different sections.**

`red_patrimonio_protegido_discapacidad` (0479) and `red_deportistas` (0488) exhibit
the identical rolling-window pattern. Single role per casilla covers all revisions.

**0484 — dual-section spelling.**

The section field records both `red_pensiones_comensatorias_alimentos` (typo) and
`red_pensiones_compensatorias_alimentos` (canonical). This is a registry artefact,
not an id-reuse. The casilla is physically the same form field with a consistent
concept and data type across all revisions. No split row needed.

**0485 — dual-section spelling (same as 0484).**

Same artefact; single row emitted.

**Already-roled casillas (not in this audit's assignment table):**

- 0471 (`disabled_person_nif`) — NIF of disabled person; roled in the existing
  taxonomy; present in `red_discapacidad` TOML but absent from the cluster JSON.
- 0483 (`pension_recipient_nif`) — NIF of pension/annuity recipient; roled in
  the existing taxonomy; present in `red_pensiones_compensatorias_alimentos` TOML
  but absent from the cluster JSON.

## Data_type divergences

No data-type divergences were found within this cluster. Every casilla in the
JSON carries a single `data_types` entry across all of its revisions. The full
breakdown is:

- `boolean`: 0382, 0383, 0484
- `money(default)`: all remaining casillas (0426, 0427, 0428, 0437, 0438, 0463,
  0464, 0465, 0466, 0467, 0472, 0473, 0474, 0475, 0479, 0480, 0485, 0488, 0489,
  0499)

No casilla in this cluster has conflicting data types across revisions. The
id-reuse hazard on 0463 (three concepts) does not produce a data-type conflict
because all three concepts are `money(default)`.
