---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
---

# `schema-hardening` audit: M100 `resultados.anexo_a_res` cluster — Plan C semantic role classification

## Scope

All 173 casillas under `resultados.anexo_a_res` in M100 IRPF revisions
2020–2025. Cross-revision constraint applied: every id present in multiple
revisions carries the same `semantic_role` unless a semantic change is
documented. Casillas already carrying a `semantic_role` (10 total) are
listed for completeness but are marked SKIP — they must not be re-roled.

Source revision used for role derivation: 2025. Cross-revision presence
verified for all 173 ids against revisions 2020–2025.

---

## Section family breakdown (2025)

| subsection | casilla_count | unroled_count |
|---|---:|---:|
| deducciones_inversion_empresarial_res | 82 | 76 |
| reserva_inversiones_canarias_res | 26 | 26 |
| deduccion_vivienda_habitual_res | 14 | 14 |
| reserva_inversiones_baleares_res | 17 | 17 |
| deduccion_mejoras_energeticas_viv_res | 10 | 10 |
| deduccion_donativos_res | 4 | 4 |
| deduccion_empresas_nueva_creacion_res | 4 | 2 (2 already roled) |
| deduccion_alquiler_res | 6 | 4 (2 already roled) |
| deduccion_residente_ue_res | 5 | 5 |
| vehiculos_elec_y_puntos_carga_res | 2 | 2 |
| deduccion_ceuta_melilla_res | 1 | 1 |
| deduccion_inv_interes_cultural_res | 1 | 1 |
| deduccion_la_palma_res | 1 | 1 |

---

## Per-id role assignment table

Columns: `id | subsection | proposed_role | label_snippet | data_type | revisions_present | notes`

SKIP = already roled; role confirmed consistent with taxonomy.

### A.1 — `deduccion_vivienda_habitual_res` (14 casillas)

Legacy pre-2013 and transitional housing deduction (LIRPF arts. 68.1, 69, 70 and DT 18a).
Per-row structure: obra dates, acquisition date, mortgage loan ID, percentage, and
deduction amounts (estatal + autonomica) for three sub-scenarios.

| id | subsection | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0683 | deduccion_vivienda_habitual_res | `irpf_anexo_a_obra_fecha_inicio` | Fecha de inicio de las obras | text | 2021–2025 | Construction start date; not present in 2020 |
| 0684 | deduccion_vivienda_habitual_res | `irpf_anexo_a_obra_fecha_fin` | Fecha de finalizacion de las obras | text | 2021–2025 | Construction end date; not present in 2020 |
| 0690 | deduccion_vivienda_habitual_res | `irpf_anexo_a_vivienda_fecha_adquisicion` | Fecha de adquisicion (post-31-12-2012, en construccion) | text | 2021–2025 | Acquisition date for post-2012 in-construction scenario |
| 0691 | deduccion_vivienda_habitual_res | `irpf_anexo_a_obra_fecha_inicio` | Fecha de inicio de las obras | text | 2021–2025 | Second obra start date slot; same role as 0683 |
| 0692 | deduccion_vivienda_habitual_res | `irpf_anexo_a_obra_fecha_fin` | Fecha de finalizacion de las obras | text | 2021–2025 | Second obra end date slot; same role as 0684 |
| 0698 | deduccion_vivienda_habitual_res | `irpf_anexo_a_deduccion_vivienda_estatal` | Parte estatal: Importe de la deduccion | decimal | 2020–2025 | Estatal tranche deduction amount |
| 0699 | deduccion_vivienda_habitual_res | `irpf_anexo_a_deduccion_vivienda_autonomica` | Parte autonomica: Importe de la deduccion | decimal | 2020–2025 | Autonomica tranche deduction amount |
| 0702 | deduccion_vivienda_habitual_res | `irpf_anexo_a_deduccion_vivienda_estatal` | Parte estatal: Importe de la deduccion | decimal | 2020–2025 | Second sub-scenario estatal slot |
| 0703 | deduccion_vivienda_habitual_res | `irpf_anexo_a_deduccion_vivienda_autonomica` | Parte autonomica: Importe de la deduccion | decimal | 2020–2025 | Second sub-scenario autonomica slot |
| 0704 | deduccion_vivienda_habitual_res | `irpf_anexo_a_deduccion_vivienda_estatal` | Parte estatal: Importe de la deduccion | decimal | 2020–2025 | Third sub-scenario estatal slot |
| 0705 | deduccion_vivienda_habitual_res | `irpf_anexo_a_deduccion_vivienda_autonomica` | Parte autonomica: Importe de la deduccion | decimal | 2020–2025 | Third sub-scenario autonomica slot |
| 0708 | deduccion_vivienda_habitual_res | `irpf_anexo_a_vivienda_fecha_adquisicion` | Fecha de adquisicion de la vivienda (salvo [0690]) | text | 2020–2025 | General acquisition date; reuses role from 0690 |
| 0709 | deduccion_vivienda_habitual_res | `irpf_anexo_a_prestamo_id` | Numero de identificacion del prestamo hipotecario | text | 2020–2025 | Mortgage loan reference string; new role |
| 0710 | deduccion_vivienda_habitual_res | `irpf_anexo_a_prestamo_porcentaje_vivienda` | Porcentaje del prestamo destinado a adquisicion de vivienda habitual | decimal | 2020–2025 | Percentage 0-100; no data_type in TOML — inferred decimal |

### A.2 — `deduccion_alquiler_res` (6 casillas, 2 already roled)

Legacy state-level rental deduction (art. 68.7 LIRPF, pre-2015; transitional DT 15a).
Structure: NIF arrendador + foreign-NIF flag + total amounts paid.

| id | subsection | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0715 | deduccion_alquiler_res | **SKIP** `landlord_nif` | NIF del arrendador 1 | nif | 2020–2025 | Already roled |
| 0716 | deduccion_alquiler_res | `irpf_anexo_a_nif_extranjero_flag` | Marque X si en [0715] consigno NIF de otro pais | boolean | 2020–2025 | OQ-1 companion flag for arrendador 1 |
| 0717 | deduccion_alquiler_res | **SKIP** `landlord_nif` | NIF del arrendador 2 | nif | 2020–2025 | Already roled |
| 0718 | deduccion_alquiler_res | `irpf_anexo_a_nif_extranjero_flag` | Marque X si en [0717] consigno NIF de otro pais | boolean | 2020–2025 | OQ-1 companion flag for arrendador 2; same role as 0716 |
| 0719 | deduccion_alquiler_res | `irpf_anexo_a_alquiler_cantidades_satisfechas` | Cantidades totales satisfechas al arrendador 1 | decimal | 2020–2025 | Total rent paid to landlord 1 |
| 0720 | deduccion_alquiler_res | `irpf_anexo_a_alquiler_cantidades_satisfechas` | Cantidades totales satisfechas al arrendador 2 | decimal | 2020–2025 | Total rent paid to landlord 2; same role as 0719 |

### A.3 — `deduccion_empresas_nueva_creacion_res` (4 casillas, 2 already roled)

Investment in newly-created companies deduction (art. 68.1 LIRPF).
Structure: NIF entity + qualifying investment amount pairs.

| id | subsection | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0711 | deduccion_empresas_nueva_creacion_res | **SKIP** `investment_entity_nif` | NIF de la entidad 1 nueva o reciente creacion | nif | 2020–2025 | Already roled |
| 0712 | deduccion_empresas_nueva_creacion_res | `irpf_anexo_a_inversion_importe_deduccion` | Importe de la inversion con derecho a deduccion | decimal | 2020–2025 | Qualifying investment amount for entity 1 |
| 0713 | deduccion_empresas_nueva_creacion_res | **SKIP** `investment_entity_nif` | NIF de la entidad 2 nueva o reciente creacion | nif | 2020–2025 | Already roled |
| 0714 | deduccion_empresas_nueva_creacion_res | `irpf_anexo_a_inversion_importe_deduccion` | Importe de la inversion con derecho a deduccion | decimal | 2020–2025 | Qualifying investment amount for entity 2; same role as 0712 |

### A.4 — `deduccion_donativos_res` (4 casillas)

Donativo deductions (art. 68.3 LIRPF): mecenazgo prioritario, Ley 49/2002 entities,
other foundations, political party quotas.

| id | subsection | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0722 | deduccion_donativos_res | `irpf_anexo_a_donativo_deduccion_importe` | Importe deduccion: Aportaciones mecenazgo prioritario (15% base liquidable) | decimal | 2020–2025 | |
| 0723 | deduccion_donativos_res | `irpf_anexo_a_donativo_deduccion_importe` | Importe deduccion: Donativos entidades Ley 49/2002 | decimal | 2020–2025 | Same structural role, different donativo bucket |
| 0724 | deduccion_donativos_res | `irpf_anexo_a_donativo_deduccion_importe` | Importe deduccion: Donativos fundaciones/asociaciones utilidad publica no Ley 49/2002 | decimal | 2020–2025 | |
| 0725 | deduccion_donativos_res | `irpf_anexo_a_donativo_deduccion_importe` | Importe deduccion: Cuotas partidos politicos / federaciones | decimal | 2020–2025 | Political-party quota subtype |

### A.5 — `deduccion_inv_interes_cultural_res` (1 casilla)

Investment in goods of cultural interest deduction (art. 68.5 LIRPF): 15%.

| id | subsection | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0726 | deduccion_inv_interes_cultural_res | `irpf_anexo_a_interes_cultural_deduccion_importe` | Importe de la deduccion: 15 por 100 | decimal | 2020–2025 | Single casilla; typo-twin warning expected and accepted |

### A.6 — `deduccion_ceuta_melilla_res` (1 casilla)

Ceuta/Melilla residency deduction (art. 68.4 LIRPF).

| id | subsection | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0727 | deduccion_ceuta_melilla_res | `irpf_anexo_a_ceuta_melilla_deduccion_importe` | Importe total deduccion por rentas en Ceuta o Melilla | decimal | 2020–2025 | Single casilla; typo-twin warning expected and accepted |

### A.7 — `deduccion_residente_ue_res` (5 casillas)

EU-resident family-unit deduction (art. 84 LIRPF): applies when family members are
EU-resident IRNR taxpayers. Structure: cuotas comparativas + difference + deduccion.

| id | subsection | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0728 | deduccion_residente_ue_res | `irpf_anexo_a_residente_ue_cuota_familiar_irpf` | Cuotas liquidas estatal y autonomica miembros unidad familiar contribuyentes IRPF | decimal | 2020–2025 | Sum of IRPF cuotas for family-unit members |
| 0729 | deduccion_residente_ue_res | `irpf_anexo_a_residente_ue_cuota_irnr` | Cuotas IRNR rentas obtenidas en Espana miembros UE | decimal | 2020–2025 | IRNR quotas for EU-resident family members |
| 0730 | deduccion_residente_ue_res | `irpf_anexo_a_residente_ue_cuota_conjunta_hipotetica` | Cuota liquida total si todos tributasen conjuntamente | decimal | 2020–2025 | Hypothetical joint-filing cuota |
| 0731 | deduccion_residente_ue_res | `irpf_anexo_a_residente_ue_diferencia` | Diferencia ([0728]+[0729]-[0730]) | decimal | 2020–2025 | Computed; zero when negative |
| 0732 | deduccion_residente_ue_res | `irpf_anexo_a_residente_ue_deduccion_importe` | Deduccion que corresponde al contribuyente | decimal | 2020–2025 | Final deduction amount after cap |

### A.8 — `reserva_inversiones_canarias_res` (26 casillas)

Reserva para Inversiones en Canarias (RIC) — art. 27 Ley 19/1994.
Per-vintage structure: dotacion amount, year (text), investment type A/B/B-bis/D-1,
investment type C/D-2-to-6, pendiente de materializar. Vintages covered: 2021–2025.
Plus two anticipatory investment slots (no vintage year).

| id | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|
| 0733 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2021(1): Importe de las dotaciones | decimal | 2020–2025 | |
| 0734 | `irpf_anexo_a_ric_dotacion_anio` | RIC 2021(1): Ano de la dotacion | text | 2020–2025 | Year as text string, not typed year |
| 0735 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2022(2): Importe de las dotaciones | decimal | 2020–2025 | |
| 0736 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC 2022(2): Inversiones A, B, B.bis y D(1a) art. 27.4 | decimal | 2020–2025 | Investment type A/B/B-bis/D-1 slot |
| 0737 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC 2022(2): Inversiones C y D(2a a 6a) art. 27.4 | decimal | 2020–2025 | Investment type C/D-2-to-6 slot |
| 0738 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2023: Importe de las dotaciones | decimal | 2020–2025 | |
| 0739 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC 2023: Inversiones A, B, B.bis y D(1a) | decimal | 2020–2025 | |
| 0740 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC 2023: Inversiones C y D(2a a 6a) | decimal | 2020–2025 | |
| 0741 | `irpf_anexo_a_ric_pendiente_materializar` | RIC 2023: Pendiente de materializar | decimal | 2020–2025 | |
| 0742 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2024: Importe de las dotaciones | decimal | 2020–2025 | |
| 0743 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC 2024: Inversiones A, B, B.bis y D(1a) | decimal | 2020–2025 | |
| 0744 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC 2024: Inversiones C y D(2a a 6a) | decimal | 2020–2025 | |
| 0745 | `irpf_anexo_a_ric_pendiente_materializar` | RIC 2024: Pendiente de materializar | decimal | 2020–2025 | |
| 0746 | `irpf_anexo_a_ric_dotacion_importe` | RIC 2025: Importe de las dotaciones | decimal | 2020–2025 | |
| 0747 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC 2025: Inversiones A, B, B.bis y D(1a) | decimal | 2020–2025 | |
| 0748 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC 2025: Inversiones C y D(2a a 6a) | decimal | 2020–2025 | |
| 0749 | `irpf_anexo_a_ric_pendiente_materializar` | RIC 2025: Pendiente de materializar | decimal | 2020–2025 | |
| 0750 | `irpf_anexo_a_ric_inversion_tipo_abd` | Inversiones anticipadas RIC 2025: Inversiones A, B, B.bis y D(1a) | decimal | 2020–2025 | Anticipatory investment; no vintage year |
| 0751 | `irpf_anexo_a_ric_inversion_tipo_cd` | Inversiones anticipadas RIC 2025: Inversiones C y D(2a a 6a) | decimal | 2020–2025 | |
| 0777 | `irpf_anexo_a_ric_inversion_tipo_abd` | RIC 2021(1): Inversiones A, B, B.bis y D(1a) | decimal | 2020–2025 | 2021 vintage A/B/D slot |
| 0778 | `irpf_anexo_a_ric_inversion_tipo_cd` | RIC 2021(1): Inversiones C y D(2a a 6a) | decimal | 2020–2025 | 2021 vintage C/D slot |
| 0789 | `irpf_anexo_a_ric_dotacion_anio` | RIC 2022(2): Ano de la dotacion | text | 2020–2025 | |
| 0790 | `irpf_anexo_a_ric_pendiente_materializar` | RIC 2022(2): Pendiente de materializar | decimal | 2020–2025 | |
| 0792 | `irpf_anexo_a_ric_dotacion_anio` | RIC 2023: Ano de la dotacion | text | 2020–2025 | |
| 0794 | `irpf_anexo_a_ric_dotacion_anio` | RIC 2024: Ano de la dotacion | text | 2020–2025 | |
| 0802 | `irpf_anexo_a_ric_dotacion_anio` | RIC 2025: Ano de la dotacion | text | 2020–2025 | |

### A.9 — `deducciones_inversion_empresarial_res` (82 casillas, 6 already roled)

Deducciones por inversiones empresariales (art. 68.2 LIRPF, referencing LIS arts. 35–39
and Ley 19/1994 Canarias incentivos). Three structural sub-families:

Sub-family 1 — AEIP / LIS deduction applied-in-this-declaration flags (63 casillas):
Each is a boolean marker "Aplicado en esta declaracion" for a named cultural/sporting/
public-interest event (Acontecimiento de Excepcional Interes Publico) or a LIS
deduction type. No data_type declared in TOML; should be set to `boolean`.

Sub-family 2 — Investment computation amounts (7 casillas).
Sub-family 3 — Producer NIF slots, already roled (6 casillas, SKIP).

**Sub-family 1 — AEIP / LIS flags:**

| id | proposed_role | label_snippet | data_type | revisions_present |
|---|---|---|---|---|
| 0706 | `irpf_anexo_a_aeip_aplicado_flag` | "Barcelona Music Lab. El Futuro de la Musica": Aplicado | (no dt — boolean) | 2020–2025 |
| 0707 | `irpf_anexo_a_aeip_aplicado_flag` | "Bicentenario de la Policia Nacional": Aplicado | (no dt — boolean) | 2020–2025 |
| 0752 | `irpf_anexo_a_aeip_aplicado_flag` | Deducciones regimen general LIS: Aplicado | (no dt — boolean) | 2020–2025 |
| 0753 | `irpf_anexo_a_aeip_aplicado_flag` | Regimenes especiales AEIP: Aplicado | (no dt — boolean) | 2020–2025 |
| 0754 | `irpf_anexo_a_aeip_aplicado_flag` | I+D art. 35.1 LIS: Aplicado | (no dt — boolean) | 2020–2025 |
| 0755 | `irpf_anexo_a_aeip_aplicado_flag` | Producciones cinematograficas art. 36.1 LIS productor: Aplicado | (no dt — boolean) | 2020–2025 |
| 0756 | `irpf_anexo_a_aeip_aplicado_flag` | Creacion empleo discapacidad art. 38 LIS: Aplicado | (no dt — boolean) | 2020–2025 |
| 0757 | `irpf_anexo_a_aeip_aplicado_flag` | "Primavera Sound, created in Barcelona": Aplicado | (no dt — boolean) | 2020–2025 |
| 0758 | `irpf_anexo_a_aeip_aplicado_flag` | Inversion en beneficios art. 37 TRLIS DT 24a: Aplicado | (no dt — boolean) | 2020–2025 |
| 0759 | `irpf_anexo_a_aeip_aplicado_flag` | Inversiones Africa Occidental art. 27.1.a) bis Ley 19/1994: Aplicado | (no dt — boolean) | 2020–2025 |
| 0760 | `irpf_anexo_a_aeip_aplicado_flag` | "Ano Tapies. Cien anos del nacimiento de Antoni Tapies (1923-2012)": Aplicado | (no dt — boolean) | 2020–2025 |
| 0761 | `irpf_anexo_a_aeip_aplicado_flag` | "Eduardo Chillida 100 anos": Aplicado | (no dt — boolean) | 2020–2025 |
| 0762 | `irpf_anexo_a_aeip_aplicado_flag` | "VIII Centenario de la Catedral gotica de Toledo": Aplicado | (no dt — boolean) | 2020–2025 |
| 0764 | `irpf_anexo_a_aeip_aplicado_flag` | Contribuciones empresariales prevision social DA3a RDL 13/2022: Aplicado | (no dt — boolean) | 2020–2025 |
| 0765 | `irpf_anexo_a_aeip_aplicado_flag` | "Ano Santo Jacobeo 2027": Aplicado | (no dt — boolean) | 2020–2025 |
| 0766 | `irpf_anexo_a_aeip_aplicado_flag` | "Centenario de la Generacion del 27": Aplicado | (no dt — boolean) | 2020–2025 |
| 0767 | `irpf_anexo_a_aeip_aplicado_flag` | "Musica clasica para todos": Aplicado | (no dt — boolean) | 2020–2025 |
| 0768 | `irpf_anexo_a_aeip_aplicado_flag` | "150.o aniversario del nacimiento de Pau Casals": Aplicado | (no dt — boolean) | 2022–2025 |
| 0769 | `irpf_anexo_a_aeip_aplicado_flag` | "Petit Liceu": Aplicado | (no dt — boolean) | 2022–2025 |
| 0779 | `irpf_anexo_a_aeip_aplicado_flag` | "Fundacio Joan Miro 50.o aniversario": Aplicado | (no dt — boolean) | 2020–2025 |
| 0780 | `irpf_anexo_a_aeip_aplicado_flag` | "Centenario Gaudi 2026": Aplicado | (no dt — boolean) | 2020–2025 |
| 0781 | `irpf_anexo_a_aeip_aplicado_flag` | "Quincuagesimo aniversario del Teatre Lliure": Aplicado | (no dt — boolean) | 2020–2025 |
| 0783 | `irpf_anexo_a_aeip_aplicado_flag` | "Ano de Investigacion Santiago Ramon y Cajal 2022": Aplicado | (no dt — boolean) | 2020–2025 |
| 0784 | `irpf_anexo_a_aeip_aplicado_flag` | "Ano Jubilar Lebaniego 2023-2024": Aplicado | (no dt — boolean) | 2020–2025 |
| 0785 | `irpf_anexo_a_aeip_aplicado_flag` | "Vigesimo aniversario del Festival Bilbao BBK Live": Aplicado | (no dt — boolean) | 2020–2025 |
| 0786 | `irpf_anexo_a_aeip_aplicado_flag` | "75.a edicion del Festival Musica y Danza de Granada": Aplicado | (no dt — boolean) | 2020–2025 |
| 0787 | `irpf_anexo_a_aeip_aplicado_flag` | "Caravaca de la Cruz 2024. Ano Jubilar": Aplicado | (no dt — boolean) | 2020–2025 |
| 0788 | `irpf_anexo_a_aeip_aplicado_flag` | "150.o aniversario del nacimiento de Manuel de Falla": Aplicado | (no dt — boolean) | 2020–2025 |
| 0791 | `irpf_anexo_a_aeip_aplicado_flag` | "Dansaneu, Festival de Cultures del Pirineu": Aplicado | (no dt — boolean) | 2020–2025 |
| 0793 | `irpf_anexo_a_aeip_aplicado_flag` | "San Diego Comic-Con Malaga": Aplicado | (no dt — boolean) | 2020–2025 |
| 0795 | `irpf_anexo_a_aeip_aplicado_flag` | "Programa preparacion deportistas espanoles Juegos Angeles 2028": Aplicado | (no dt — boolean) | 2020–2025 |
| 0796 | `irpf_anexo_a_aeip_aplicado_flag` | "Universo Mujer IV": Aplicado | (no dt — boolean) | 2020–2025 |
| 0797 | `irpf_anexo_a_aeip_aplicado_flag` | "Gran Premio de Espana de Motociclismo": Aplicado | (no dt — boolean) | 2020–2025 |
| 0798 | `irpf_anexo_a_aeip_aplicado_flag` | "Deporte Inclusivo III": Aplicado | (no dt — boolean) | 2020–2025 |
| 0817 | `irpf_anexo_a_aeip_aplicado_flag` | "Plan de Fomento de la opera en la Calle del Teatro Real": Aplicado | (no dt — boolean) | 2020–2025 |
| 0837 | `irpf_anexo_a_aeip_aplicado_flag` | Inversiones en adquisicion de activos fijos: Aplicado | (no dt — boolean) | 2020–2025 |
| 0838 | `irpf_anexo_a_aeip_aplicado_flag` | Restantes modalidades: Aplicado | (no dt — boolean) | 2020–2025 |
| 0839 | `irpf_anexo_a_aeip_aplicado_flag` | I+D art. 35.1 LIS (pending section): Aplicado | (no dt — boolean) | 2020–2025 |
| 0840 | `irpf_anexo_a_aeip_aplicado_flag` | Producciones cinematograficas art. 36.1 LIS productor (pending): Aplicado | (no dt — boolean) | 2020–2025 |
| 0841 | `irpf_anexo_a_aeip_aplicado_flag` | Creacion empleo discapacidad art. 38 LIS (pending): Aplicado | (no dt — boolean) | 2020–2025 |
| 0842 | `irpf_anexo_a_aeip_aplicado_flag` | Contribuciones empresariales prevision social (pending): Aplicado | (no dt — boolean) | 2021–2025 |
| 0843 | `irpf_anexo_a_aeip_aplicado_flag` | Gastos propaganda/publicidad art. 27.1.b) bis Ley 19/1994: Aplicado | (no dt — boolean) | 2020–2025 |
| 0844 | `irpf_anexo_a_aeip_aplicado_flag` | Ejercicio 2025. Inversiones activos fijos: Aplicado | (no dt — boolean) | 2020–2025 |
| 1623 | `irpf_anexo_a_aeip_aplicado_flag` | "Plan 2030 de Apoyo al Deporte Base II": Aplicado | (no dt — boolean) | 2022–2025 |
| 1627 | `irpf_anexo_a_aeip_aplicado_flag` | "Ironman Calella-Barcelona": Aplicado | (no dt — boolean) | **2022–2025 only** — ID-REUSE HAZARD; see section below |
| 1629 | `irpf_anexo_a_aeip_aplicado_flag` | "Barcelona Mobile World Capital": Aplicado | (no dt — boolean) | **2022–2025 only** — ID-REUSE HAZARD; see section below |
| 1686 | `irpf_anexo_a_aeip_aplicado_flag` | Innovacion tecnologica art. 35.2 LIS: Aplicado | (no dt — boolean) | 2021–2025 |
| 1687 | `irpf_anexo_a_aeip_aplicado_flag` | Producciones cinematograficas extranjeras art. 36.2 LIS (**): Aplicado | (no dt — boolean) | 2021–2025 |
| 1688 | `irpf_anexo_a_aeip_aplicado_flag` | Espectaculos escenicos art. 36.3 LIS productor: Aplicado | (no dt — boolean) | 2021–2025 |
| 1722 | `irpf_anexo_a_aeip_aplicado_flag` | Producciones cinematograficas art. 36.1 LIS financiador: Aplicado | (no dt — boolean) | 2021–2025 |
| 1723 | `irpf_anexo_a_aeip_aplicado_flag` | Espectaculos escenicos art. 36.3 LIS financiador: Aplicado | (no dt — boolean) | 2021–2025 |
| 1727 | `irpf_anexo_a_aeip_aplicado_flag` | Innovacion tecnologica art. 35.2 LIS (pending): Aplicado | (no dt — boolean) | 2021–2025 |
| 1728 | `irpf_anexo_a_aeip_aplicado_flag` | Producciones cinematograficas extranjeras art. 36.2 LIS (*) (pending): Aplicado | (no dt — boolean) | 2021–2025 |
| 1729 | `irpf_anexo_a_aeip_aplicado_flag` | Espectaculos escenicos art. 36.3 LIS productor (pending): Aplicado | (no dt — boolean) | 2021–2025 |
| 1730 | `irpf_anexo_a_aeip_aplicado_flag` | Producciones cinematograficas art. 36.1 LIS financiador (pending): Aplicado | (no dt — boolean) | 2021–2025 |
| 1731 | `irpf_anexo_a_aeip_aplicado_flag` | Espectaculos escenicos art. 36.3 LIS financiador (pending): Aplicado | (no dt — boolean) | 2021–2025 |
| 1944 | `irpf_anexo_a_aeip_aplicado_flag` | "Inauguracion de la Galeria de las Colecciones Reales": Aplicado | (no dt — boolean) | 2023–2025 |
| 1947 | `irpf_anexo_a_aeip_aplicado_flag` | "60 aniversario del Festival Porta Ferrada": Aplicado | (no dt — boolean) | 2023–2025 |
| 1948 | `irpf_anexo_a_aeip_aplicado_flag` | "Programa EN PLAN BIEN": Aplicado | (no dt — boolean) | 2023–2025 |
| 1950 | `irpf_anexo_a_aeip_aplicado_flag` | "Ryder Cup 2031": Aplicado | (no dt — boolean) | 2023–2025 |
| 1951 | `irpf_anexo_a_aeip_aplicado_flag` | "Open Barcelona-Trofeo Conde de Godo": Aplicado | (no dt — boolean) | 2023–2025 |
| 1952 | `irpf_anexo_a_aeip_aplicado_flag` | "125 aniversario del Real Club de Tenis Barcelona": Aplicado | (no dt — boolean) | 2023–2025 |
| 1953 | `irpf_anexo_a_aeip_aplicado_flag` | "750 aniversario del Consolat del Mar": Aplicado | (no dt — boolean) | 2023–2025 |
| 1954 | `irpf_anexo_a_aeip_aplicado_flag` | "Congreso de la Union Internacional de Arquitectos": Aplicado | (no dt — boolean) | 2023–2025 |
| 1955 | `irpf_anexo_a_aeip_aplicado_flag` | "Festival Internacional Sonar de Musica, Creativitat i Tecnologia": Aplicado | (no dt — boolean) | 2023–2025 |
| 1956 | `irpf_anexo_a_aeip_aplicado_flag` | "XXXVII Copa America Barcelona": Aplicado | (no dt — boolean) | 2023–2025 |
| 1957 | `irpf_anexo_a_aeip_aplicado_flag` | "Programa deportivo 'RETO DE'": Aplicado | (no dt — boolean) | 2023–2025 |
| 2060 | `irpf_anexo_a_aeip_aplicado_flag` | "Barcelona 2026 Capital Mundial de la Arquitectura": Aplicado | (no dt — boolean) | 2025 only |
| 2061 | `irpf_anexo_a_aeip_aplicado_flag` | "Rally Islas Canarias": Aplicado | (no dt — boolean) | 2025 only |

**Sub-family 2 — Investment computation slots:**

| id | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|
| 0830 | `irpf_anexo_a_inversion_importe_base` | Rendimientos netos act. econ. 2024 invertidos en elementos nuevos afectos | decimal | 2020–2025 | Gross investment amount, prior year |
| 0831 | `irpf_anexo_a_inversion_importe_deduccion_base` | Rendimientos netos act. econ. 2024: Importe con derecho a deduccion (*) | decimal | 2020–2025 | Qualifying base after cap |
| 0832 | `irpf_anexo_a_inversion_deduccion_importe` | Rendimientos netos act. econ. 2024: Importe de la deduccion (**) | decimal | 2020–2025 | Computed deduction |
| 0833 | `irpf_anexo_a_inversion_importe_base` | Rendimientos netos act. econ. 2025 invertidos en elementos nuevos afectos | decimal | 2020–2025 | Gross investment amount, current year; same role as 0830 |
| 0834 | `irpf_anexo_a_inversion_importe_deduccion_base` | Rendimientos netos act. econ. 2025: Importe con derecho a deduccion (*) | decimal | 2020–2025 | Same role as 0831 |
| 0835 | `irpf_anexo_a_inversion_deduccion_importe` | Rendimientos netos act. econ. 2025: Importe de la deduccion (**) | decimal | 2020–2025 | Same role as 0832 |
| 0836 | `irpf_anexo_a_inversion_deduccion_importe` | Deduccion por inversion en elementos nuevos inmovilizado/inmobiliario: Importe (**) | decimal | 2020–2025 | Aggregate deduction from 0832+0835 |

**Sub-family 3 — Producer NIFs (already roled, SKIP):**

| id | role | notes |
|---|---|---|
| 1724 | **SKIP** `producer_nif` | Cinematographic producer 1 (financiador context) |
| 1725 | **SKIP** `producer_nif` | Cinematographic producer 2 |
| 1726 | **SKIP** `producer_nif` | Cinematographic producer 3 |
| 1732 | **SKIP** `producer_nif` | Espectaculos producer 1 |
| 1733 | **SKIP** `producer_nif` | Espectaculos producer 2 |
| 1734 | **SKIP** `producer_nif` | Espectaculos producer 3 |

### A.10 — `deduccion_mejoras_energeticas_viv_res` (10 casillas)

Deducciones por mejoras de eficiencia energetica de viviendas (DA 40a–42a LIRPF, RDL 19/2021).
Three sub-deductions: reduccion demanda calefaccion/refrigeracion (slots 1+2), mejora consumo
energia primaria no renovable (slots 1+2), obras en edificios residenciales (base+importe+carry).

| id | subsection | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 1661 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_deduccion_importe` | Importe deduccion reduccion demanda calefaccion y refrigeracion (slot 1) | decimal | 2021–2025 | |
| 1662 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_deduccion_importe` | Importe deduccion reduccion demanda calefaccion y refrigeracion (slot 2) | decimal | 2021–2025 | |
| 1669 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_deduccion_importe` | Importe deduccion mejora consumo energia primaria no renovable (slot 1) | decimal | 2021–2025 | |
| 1670 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_deduccion_importe` | Importe deduccion mejora consumo energia primaria no renovable (slot 2) | decimal | 2021–2025 | |
| 1678 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_base_deduccion` | Base de la deduccion (limite anual maximo: 5.000 euros) | decimal | 2021–2025 | Base for edificios residenciales |
| 1679 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_deduccion_importe` | Importe de la deduccion: 60 por 100 | decimal | 2021–2025 | 60% deduction for edificios residenciales |
| 1680 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_exceso_pendiente` | Exceso cantidades satisfechas 2025 con derecho a deduccion (4 ejercicios siguientes) | decimal | 2021–2025 | Carry-forward excess |
| 1777 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_base_aplicada_prev` | Base deduccion aplicada en 2021, 2022, 2023 y 2024 | decimal | 2022–2025 | Prior-year aggregate base |
| 1778 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_exceso_pendiente` | Excesos pendientes de deducir procedentes ejercicios 2021–2024 | decimal | 2022–2025 | Prior-year carry-forward; same role as 1680 |
| 1779 | deduccion_mejoras_energeticas_viv_res | `irpf_anexo_a_mejora_energia_base_deduccion` | Importe con derecho a deduccion por obras en edificios residenciales en 2025 | decimal | 2022–2025 | Qualifying amount for residential-building obras; same role as 1678 |

### A.11 — `reserva_inversiones_baleares_res` (17 casillas)

Reserva para Inversiones en las Illes Balears (RIB) — Ley 8/2019 Illes Balears.
Per-vintage structure (2023–2025): dotacion amount, year (text), investment type A/B,
investment type C, pendiente de materializar. Plus two anticipatory slots for 2025.

| id | proposed_role | label_snippet | data_type | revisions_present |
|---|---|---|---|---|
| 1681 | `irpf_anexo_a_rib_dotacion_importe` | RIB 2023: Importe de las dotaciones | decimal | 2021–2025 |
| 1682 | `irpf_anexo_a_rib_dotacion_anio` | RIB 2023: Ano de la dotacion | text | 2021–2025 |
| 1684 | `irpf_anexo_a_rib_inversion_tipo_ab` | RIB 2023: Inversiones letras A y B del apartado 4 | decimal | 2021–2025 |
| 1685 | `irpf_anexo_a_rib_inversion_tipo_c` | RIB 2023: Inversiones letra C del apartado 4 | decimal | 2021–2025 |
| 1689 | `irpf_anexo_a_rib_pendiente_materializar` | RIB 2023: Pendiente de materializar | decimal | 2021–2025 |
| 1780 | `irpf_anexo_a_rib_dotacion_importe` | RIB 2024: Importe de las dotaciones | decimal | 2021–2025 |
| 1781 | `irpf_anexo_a_rib_dotacion_anio` | RIB 2024: Ano de la dotacion | text | 2021–2025 |
| 1782 | `irpf_anexo_a_rib_inversion_tipo_ab` | RIB 2024: Inversiones letras A y B del apartado 4 | decimal | 2021–2025 |
| 1783 | `irpf_anexo_a_rib_inversion_tipo_c` | RIB 2024: Inversiones letra C del apartado 4 | decimal | 2021–2025 |
| 1784 | `irpf_anexo_a_rib_pendiente_materializar` | RIB 2024: Pendiente de materializar | decimal | 2021–2025 |
| 1937 | `irpf_anexo_a_rib_dotacion_importe` | RIB 2025: Importe de las dotaciones | decimal | 2023–2025 |
| 1938 | `irpf_anexo_a_rib_dotacion_anio` | RIB 2025: Ano de la dotacion | text | 2023–2025 |
| 1939 | `irpf_anexo_a_rib_inversion_tipo_ab` | RIB 2025: Inversiones letras A y B del apartado 4 | decimal | 2023–2025 |
| 1940 | `irpf_anexo_a_rib_inversion_tipo_c` | RIB 2025: Inversiones letra C del apartado 4 | decimal | 2023–2025 |
| 1941 | `irpf_anexo_a_rib_pendiente_materializar` | RIB 2025: Pendiente de materializar | decimal | 2023–2025 |
| 1942 | `irpf_anexo_a_rib_inversion_tipo_ab` | Inversiones anticipadas RIB 2025: Inversiones letras A y B | decimal | 2023–2025 |
| 1943 | `irpf_anexo_a_rib_inversion_tipo_c` | Inversiones anticipadas RIB 2025: Inversiones letra C | decimal | 2023–2025 |

### A.12 — `vehiculos_elec_y_puntos_carga_res` (2 casillas)

Electric vehicle and charging point deduction (DA 43a LIRPF, RDL 5/2023).

| id | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|
| 1927 | `irpf_anexo_a_vehiculo_electrico_deduccion_importe` | Importe deduccion adquisicion vehiculos electricos enchufables y pila combustible | decimal | 2023–2025 | Typo-twin warning expected; genuinely new statutory deduction |
| 1935 | `irpf_anexo_a_mejora_energia_deduccion_importe` | Importe deduccion mejora consumo energia primaria no renovable | decimal | 2023–2025 | Same concept as deduccion_mejoras_energeticas_viv_res; role shared across subsections |

### A.13 — `deduccion_la_palma_res` (1 casilla)

La Palma residency deduction (DA Decimoctava LIRPF, volcanic eruption emergency).

| id | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|
| 1847 | `irpf_anexo_a_la_palma_deduccion_importe` | Importe total deduccion por residencia habitual y efectiva en la isla de La Palma | decimal | 2022–2025 | Typo-twin warning expected; genuinely one-off statutory deduction |

---

## New roles introduced (36 total)

All are not present in the canonical taxonomy as of 2026-05-19.

**Date / text roles (4):**
- `irpf_anexo_a_obra_fecha_inicio` — construction works start date (text)
- `irpf_anexo_a_obra_fecha_fin` — construction works end date (text)
- `irpf_anexo_a_vivienda_fecha_adquisicion` — dwelling acquisition date (text)
- `irpf_anexo_a_prestamo_id` — mortgage loan reference string (text)

**Percentage role (1):**
- `irpf_anexo_a_prestamo_porcentaje_vivienda` — proportion of mortgage for dwelling acquisition (decimal, 0–100)

**Flag roles (2):**
- `irpf_anexo_a_nif_extranjero_flag` — OQ-1 companion: adjacent NIF slot is foreign (boolean)
- `irpf_anexo_a_aeip_aplicado_flag` — AEIP/LIS deduction applied-in-this-declaration flag (boolean; no data_type in TOML — bulk-apply should set boolean)

**Housing deduction amount roles (5):**
- `irpf_anexo_a_deduccion_vivienda_estatal` — state-tranche housing deduction (decimal)
- `irpf_anexo_a_deduccion_vivienda_autonomica` — autonomic-tranche housing deduction (decimal)
- `irpf_anexo_a_alquiler_cantidades_satisfechas` — total rent paid to landlord (decimal)
- `irpf_anexo_a_inversion_importe_deduccion` — qualifying investment amount for entity deduction (decimal)
- `irpf_anexo_a_donativo_deduccion_importe` — donativo deduction amount across all four buckets (decimal)

**Single-deduction amount roles (6):**
- `irpf_anexo_a_interes_cultural_deduccion_importe` — cultural-interest 15% deduction (decimal)
- `irpf_anexo_a_ceuta_melilla_deduccion_importe` — Ceuta/Melilla total deduction (decimal)
- `irpf_anexo_a_residente_ue_deduccion_importe` — EU-resident family deduction (decimal)
- `irpf_anexo_a_vehiculo_electrico_deduccion_importe` — EV/fuel-cell vehicle deduction (decimal)
- `irpf_anexo_a_la_palma_deduccion_importe` — La Palma residency deduction (decimal)

**EU-resident comparative computation roles (4):**
- `irpf_anexo_a_residente_ue_cuota_familiar_irpf` — IRPF cuotas of family-unit IRPF members (decimal)
- `irpf_anexo_a_residente_ue_cuota_irnr` — IRNR quotas of EU-resident family members (decimal)
- `irpf_anexo_a_residente_ue_cuota_conjunta_hipotetica` — hypothetical joint-filing cuota (decimal)
- `irpf_anexo_a_residente_ue_diferencia` — difference [0728]+[0729]-[0730]; zero when negative (decimal)

**RIC (Reserva Inversiones Canarias) roles (5):**
- `irpf_anexo_a_ric_dotacion_importe` — RIC dotacion gross amount (decimal)
- `irpf_anexo_a_ric_dotacion_anio` — RIC dotacion year string (text)
- `irpf_anexo_a_ric_inversion_tipo_abd` — RIC investment type A/B/B-bis/D-1 (decimal)
- `irpf_anexo_a_ric_inversion_tipo_cd` — RIC investment type C/D-2-to-6 (decimal)
- `irpf_anexo_a_ric_pendiente_materializar` — RIC pending materialization (decimal)

**RIB (Reserva Inversiones Illes Balears) roles (5):**
- `irpf_anexo_a_rib_dotacion_importe` — RIB dotacion gross amount (decimal)
- `irpf_anexo_a_rib_dotacion_anio` — RIB dotacion year string (text)
- `irpf_anexo_a_rib_inversion_tipo_ab` — RIB investment types A and B (decimal)
- `irpf_anexo_a_rib_inversion_tipo_c` — RIB investment type C (decimal)
- `irpf_anexo_a_rib_pendiente_materializar` — RIB pending materialization (decimal)

**Empresarial investment computation roles (3):**
- `irpf_anexo_a_inversion_importe_base` — gross rendimientos net invested in new fixed assets (decimal)
- `irpf_anexo_a_inversion_importe_deduccion_base` — qualifying base after cap (*) (decimal)
- `irpf_anexo_a_inversion_deduccion_importe` — computed deduction amount (**) (decimal)

**Mejoras energeticas roles (4):**
- `irpf_anexo_a_mejora_energia_deduccion_importe` — energy-improvement deduction amount; covers all DA 40a–42a sub-deductions and vehiculos_elec 1935 (decimal)
- `irpf_anexo_a_mejora_energia_base_deduccion` — energy-improvement deduction base (decimal)
- `irpf_anexo_a_mejora_energia_exceso_pendiente` — excess carry-forward for subsequent years (decimal)
- `irpf_anexo_a_mejora_energia_base_aplicada_prev` — prior-year aggregate base already applied (decimal)

---

## ID-reuse hazards

### Critical: 1627 and 1629 — section change in 2022

Both ids appear in `toma_datos_ampliada.gp_otros_elementos.elemento_patrimonial`
in revisions 2020–2021 (patrimonial gains element — unrelated to AEIP) and move to
`resultados.anexo_a_res.deducciones_inversion_empresarial_res` in 2022–2025 as
AEIP boolean flags ("Ironman Calella-Barcelona" / "Barcelona Mobile World Capital").

These are semantically unrelated across the revision boundary. The cross-revision
role constraint cannot be satisfied with a single role.

**Resolution:** Assign `irpf_anexo_a_aeip_aplicado_flag` for revisions 2022–2025 only.
The bulk-apply pass must carry an explicit per-revision guard for these two ids and
must not write to their 2020–2021 occurrences. The 2020–2021 occurrences will be
handled by the `toma_datos_ampliada.gp_otros_elementos` audit cluster.

---

## Decimal / money divergences

All amount casillas in `resultados.anexo_a_res` either have no explicit `data_type`
declared (inferred `decimal` by the registry) or are confirmed `decimal`. No `money`
type casillas exist in this section. No decimal/money divergences arise from this
cluster. All monetary roles proposed here bind `decimal` exclusively.

---

## Typo-twin warnings expected

Single-occurrence roles that will produce `warnings.warn` at registry load
(all legitimate; accepted here):

- `irpf_anexo_a_interes_cultural_deduccion_importe` (0726 only)
- `irpf_anexo_a_ceuta_melilla_deduccion_importe` (0727 only)
- `irpf_anexo_a_la_palma_deduccion_importe` (1847 only)
- `irpf_anexo_a_vehiculo_electrico_deduccion_importe` (1927 only)
- `irpf_anexo_a_prestamo_id` (0709 only)
- `irpf_anexo_a_residente_ue_cuota_conjunta_hipotetica` (0730 only)
- `irpf_anexo_a_residente_ue_diferencia` (0731 only)
- `irpf_anexo_a_mejora_energia_base_aplicada_prev` (1777 only)

---

## Acceptance notes

- 10 casillas are already roled (SKIP). Their roles are confirmed consistent
  with this cluster's semantic context and must not be overwritten.
- 163 casillas receive new role proposals in this document.
- 36 new roles required; none conflict with existing taxonomy name strings.
- IDs 1627 and 1629 must be treated as revision-scoped. Role
  `irpf_anexo_a_aeip_aplicado_flag` applies for 2022–2025 only. The bulk-apply
  pass must not write to 2020–2021 for these two ids.
- IDs 2060 and 2061 are 2025-only; no cross-revision constraint applies.
- All `irpf_anexo_a_ric_dotacion_anio` and `irpf_anexo_a_rib_dotacion_anio` slots
  carry `data_type = "text"` not `year`; do not infer a year type.
- The `irpf_anexo_a_aeip_aplicado_flag` role covers 63 casillas (largest single new
  role in this cluster). All carry no `data_type` in TOML; the bulk-apply pass should
  set `data_type = "boolean"` consistent with the OQ-1 flag pattern and the other
  boolean casillas in this section (0716, 0718).
- The new roles should be appended to the canonical taxonomy reference after the
  bulk-apply commit lands.
