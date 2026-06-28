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

# Schema hardening — M100 deducciones-inversion-empresarial cluster

## Scope

Section `resultados/anexo_a_res/deducciones_inversion_empresarial_res` of modelo 100.
Revisions covered: 2020, 2021, 2022, 2023, 2024, 2025.
Total IDs in cluster: 63.

This section records amounts of business-investment incentive deductions (arts. 36 and 39 Ley 27/2014 LIS, art. 68.2 Ley 35/2006 LIRPF) applied to the current IRPF filing. The vast majority of casillas are one-per-event slots for AEAT-approved cultural, sporting, commemorative, and scientific patronage events (Mecenazgo deductions). A smaller sub-cluster captures economic-activity-income invested in new fixed assets, plus four boolean selector flags for cinema/audiovisual producers and financers.

Three existing roles match concepts in this section and are reused verbatim:
- `irpf_deduccion_incentivos_inversion_empresarial_estatal`
- `irpf_anexo_a_inversion_importe_base`
- `irpf_anexo_a_inversion_importe_deduccion_base`
- `irpf_anexo_a_inversion_deduccion_importe`
- `irpf_anexo_a_aeip_aplicado_flag` (already present in TOML for 0844)

## Role assignments

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0700 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "VIII Centenario de la Catedral de Burgos 2021": Aplicado en esta declaración | money(default) | 2022 | ID-reuse hazard: same id in 2020 was in section deduccion_vivienda_habitual_res with unrelated label; cluster JSON only shows 2022 in deducciones_inversion_empresarial_res |
| 0760 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración (event name varies per revision) | money(default) | 2020, 2022, 2023, 2025 | Each revision targets a different named event; role is stable |
| 0764 | `irpf_deduccion_contribuciones_empresariales_prevision_social_aplicado` | Por contribuciones empresariales a sistemas de previsión social (D.A. tercera RDL 13/2022): Aplicado en esta declaración | money(default) | 2020, 2021, 2023, 2024, 2025 | New role; RDL 13/2022 DA tercera; absent from 2022 revision |
| 0765 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Año Santo Jacobeo 2027": Aplicado en esta declaración | money(default) | 2020, 2021, 2022, 2023, 2025 | |
| 0773 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "20 Aniversario de Primavera Sound": Aplicado en esta declaración | money(default) | 2022, 2023, 2024 | |
| 0776 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "V Centenario expedición primera vuelta al mundo Magallanes/Elcano": Aplicado | money(default) | 2020, 2021, 2022 | |
| 0780 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Centenario Gaudí 2026": Aplicado en esta declaración | money(default) | 2020, 2021, 2022, 2023, 2025 | |
| 0782 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Campeonato Mundial Junior Balonmano Masculino 2019": Aplicado | money(default) | 2020, 2022, 2023, 2024 | |
| 0783 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Año de Investigación Santiago Ramón y Cajal 2022": Aplicado | money(default) | 2020, 2021, 2023, 2024, 2025 | |
| 0784 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Andalucía Valderrama Masters": Aplicado en esta declaración | money(default) | 2020, 2021, 2022, 2025 | |
| 0787 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Ceuta y la Legión, 100 años de unión": Aplicado | money(default) | 2020, 2022, 2023, 2025 | |
| 0795 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Universo Mujer (II)": Aplicado en esta declaración | money(default) | 2020, 2021, 2025 | |
| 0800 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "VIII Centenario de la Catedral de Burgos 2021": Aplicado | money(default) | 2020, 2021 | |
| 0801 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Deporte Inclusivo": Aplicado en esta declaración | money(default) | 2020, 2021 | |
| 0804 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Plan 2020 de Apoyo al Deporte de Base II": Aplicado | money(default) | 2020, 2021 | |
| 0805 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "España, Capital del Talento Joven": Aplicado | money(default) | 2020 | |
| 0806 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Conmemoración Centenario Coronación Nuestra Señora del Rocío": Aplicado | money(default) | 2020 | |
| 0807 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Traslado Imagen Nuestra Señora del Rocío": Aplicado | money(default) | 2020 | |
| 0808 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Camino Lebaniego": Aplicado en esta declaración | money(default) | 2020, 2021 | |
| 0809 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Expo Dubai 2020": Aplicado en esta declaración | money(default) | 2020, 2021, 2022 | |
| 0810 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2020, 2021 | Label not recovered from cluster JSON (backslash-only); pattern confirmed from sibling IDs in same revision block |
| 0811 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "XXV Aniversario Declaración UNESCO Real Monasterio Guadalupe": Aplicado | money(default) | 2020 | |
| 0814 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "COP25 Madrid": Aplicado en esta declaración | money(default) | 2020 | |
| 0815 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Plan Berlanga": Aplicado en esta declaración | money(default) | 2020, 2021, 2022, 2023 | |
| 0830 | `irpf_anexo_a_inversion_importe_base` | Importe rendimientos netos activ. económicas … que se invierten en elementos nuevos afectos | money(default) | 2020, 2021, 2022, 2023, 2025 | Prior-year investment base; same concept as 0833; year referenced in label shifts per revision |
| 0831 | `irpf_anexo_a_inversion_importe_deduccion_base` | … Importe con derecho a deducción (*) | money(default) | 2020, 2021, 2022, 2023, 2025 | Deductible portion of prior-year investment; same concept as 0834 |
| 0832 | `irpf_anexo_a_inversion_deduccion_importe` | … Importe de la deducción (**) | money(default) | 2020, 2021, 2022, 2023, 2025 | Computed deduction amount for prior-year investment; same concept as 0835 |
| 0833 | `irpf_anexo_a_inversion_importe_base` | Importe rendimientos netos activ. económicas … que se invierten (current-year window) | money(default) | 2020, 2021, 2022, 2023, 2024 | Role already assigned in TOML (2025 revision) |
| 0834 | `irpf_anexo_a_inversion_importe_deduccion_base` | … Importe con derecho a deducción (*) (current-year window) | money(default) | 2020, 2021, 2022, 2023, 2024 | Role already assigned in TOML (2025 revision) |
| 0835 | `irpf_anexo_a_inversion_deduccion_importe` | … Importe de la deducción (**) (current-year window) | money(default) | 2020, 2021, 2022, 2023, 2024 | Role already assigned in TOML (2025 revision) |
| 0844 | `irpf_anexo_a_aeip_aplicado_flag` | Ejercicio YYYY. Inversiones en la adquisición de activos fijos: Aplicado en esta declaración | money(default) | 2020, 2021, 2022, 2023, 2024 | Role already assigned in TOML (2025 revision); rolling year-window field |
| 1623 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Plan 2030 de Apoyo al Deporte Base II": Aplicado en esta declaración | money(default) | 2022, 2023, 2024, 2025 | |
| 1628 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Global Mobility Call": Aplicado en esta declaración | money(default) | 2022 | |
| 1630 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Año Santo Jubilar San Isidro Labrador": Aplicado | money(default) | 2022, 2023 | |
| 1689 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Alicante 2021. Salida Vuelta al Mundo a Vela": Aplicado | money(default) | 2021, 2022, 2024 | |
| 1690 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Bicentenarios de la independencia de las Repúblicas Iberoamericanas": Aplicado | money(default) | 2021, 2022, 2023 | |
| 1691 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "150 Aniversario creación Academia de España en Roma": Aplicado | money(default) | 2021, 2022, 2023 | |
| 1698 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "MADRID HORSE WEEK 21/23": Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | |
| 1699 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Centenario del Rugby en España y de la UE Santboiana": Aplicado | money(default) | 2021, 2022, 2023 | |
| 1700 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Solheim Cup 2023": Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | |
| 1701 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "IX Centenario de la Reconquista de Sigüenza": Aplicado | money(default) | 2021, 2022, 2023, 2024 | |
| 1702 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated in cluster JSON; TOML confirms section and legal refs identical to sibling IDs |
| 1703 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Same caveat as 1702 |
| 1704 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Cincuenta aniversario UNED": Aplicado en esta declaración | money(default) | 2021, 2022 | |
| 1705 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated |
| 1706 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023, 2024 | Label truncated |
| 1707 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated |
| 1708 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023, 2024 | Label truncated |
| 1710 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated |
| 1711 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated |
| 1712 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Hábitos Saludables Riesgo Cardiovascular - Aprender a cuidarnos": Aplicado | money(default) | 2021, 2022, 2023 | |
| 1713 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated |
| 1714 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated |
| 1715 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated |
| 1716 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated |
| 1717 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Programa Deporte Inclusivo": Aplicado en esta declaración | money(default) | 2021, 2022, 2023, 2024 | |
| 1718 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Valencia 2020-2021, Año Jubilar. Camino del Santo Cáliz": Aplicado | money(default) | 2021, 2022 | |
| 1719 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022 | Label truncated |
| 1720 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022, 2023 | Label truncated |
| 1721 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | Event patronage: Aplicado en esta declaración | money(default) | 2021, 2022 | Label truncated |
| 1722 | `irpf_deduccion_cine_productor_financiacion_externa_flag` | Contribuyente (productor) que aplica deducciones art. 36.1/3 LIS y art. 39.7 LIS con financiación por otro contribuyente | boolean | 2021 | New role; boolean selector for cinema producer with external financing arrangement |
| 1723 | `irpf_deduccion_cine_financiador_flag` | Contribuyente que financia producciones cinematográficas con derecho a deducción art. 36.1/3 LIS y art. 39.7 LIS | boolean | 2021 | New role; boolean selector for cinema/AV financer |
| 1730 | `irpf_deduccion_cine_productor_financiacion_externa_flag` | Contribuyente (productor) que aplica deducciones art. 36.1/3 LIS y art. 39.7 LIS con financiación por otro contribuyente | boolean | 2021 | Same concept as 1722; parallel slot (possibly declarant vs. conyuge position); boolean |
| 1731 | `irpf_deduccion_cine_financiador_flag` | Contribuyente que financia producciones cinematográficas con derecho a deducción art. 36.1/3 LIS y art. 39.7 LIS | boolean | 2021 | Same concept as 1723; parallel slot |
| 1945 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Centenario del Hockey 1923-2023": Aplicado en esta declaración | money(default) | 2023, 2024 | |
| 1946 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "60 Aniversario Rally Blendio Princesa de Asturias Ciudad de Oviedo": Aplicado | money(default) | 2023 | |
| 1949 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "125 aniversario del Athletic Club 1898-2023": Aplicado | money(default) | 2023 | |
| 1950 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Ryder Cup 2031": Aplicado en esta declaración | money(default) | 2023, 2024, 2025 | |
| 1958 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Celebración de la Bienal Manifesta 15 Barcelona": Aplicado | money(default) | 2023, 2024 | |
| 2060 | `irpf_deduccion_incentivos_inversion_empresarial_estatal` | "Barcelona 2026 Capital Mundial de la Arquitectura": Aplicado | money(default) | 2025 | |

## Id-reuse hazards

### 0700 — section change across revisions

In revision 2020, casilla 0700 belonged to section `resultados/anexo_a_res/deduccion_vivienda_habitual_res` with label "Parte estatal: Importe de la deducción" (vivienda habitual deduction, unrelated domain). From revision 2022 onwards the same numeric id appears exclusively in `deducciones_inversion_empresarial_res` with a completely different label ("VIII Centenario de la Catedral de Burgos 2021": Aplicado en esta declaración).

The cluster JSON records 0700 only in 2022 within this section, confirming the registry correctly segregates the two uses. The `revisions_present` column for this cluster entry is therefore `2022` only. The 2020 occurrence is a distinct casilla that happens to share the number.

**Action required:** any role-assignment pipeline that joins by id across all revisions must partition on `(id, section)` or `(id, revision_year)` before assigning roles to prevent the vivienda-habitual concept leaking into this cluster's role.

### 0830–0832 vs 0833–0835 — rolling prior-year window

Casillas 0830, 0831, 0832 capture the prior-fiscal-year investment window ("rendimientos de Y-1 que se invierten"). Casillas 0833, 0834, 0835 capture the current-fiscal-year window ("rendimientos de Y que se invierten"). The label text in each revision references a different source year (e.g. 2020 revision shows "2019 que se invierten" for 0833 and "2018 que se invierten" for 0830). Both triples represent the same three-field concept (base / deductible base / deduction amount), so the same three roles apply to both triples. No role split is needed; no id-reuse hazard is present across revisions — all five revisions where each appears share the same concept.

### 1722 vs 1730, and 1723 vs 1731 — parallel declarant/conyuge slots

Both pairs carry identical labels and identical `boolean` data types in 2021. The probable cause is that the form has separate fields for the primary declarant and conyuge (joint filing). The concept — cinema producer with external financing / cinema financer — is the same for both slots. A single role is assigned to each pair. No revision-level reuse hazard; both appear only in 2021.

## Data_type divergences

No data_type divergences were found within this cluster. Every casilla is `money(default)` except for 1722, 1723, 1730, and 1731, which are uniformly `boolean`. All four boolean casillas share a consistent data_type within their roles. No casilla in this cluster exhibits mixed data_types across revisions.
