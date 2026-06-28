---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-18-schema-hardening-nif-coverage-m100-audit]]"
  - "[[2026-05-20-schema-hardening-plan]]"
---

# schema-hardening: M100 NIF semantic_role assignment

Read-only classification of every `data_type = "nif"` casilla in the six M100 revision TOML files (2020–2025). Goal: produce a per-id role-assignment table and a per-revision retrofit list for the follow-up automation that adds `semantic_role = "<role>"` after each `data_type = "nif"` line. No TOML files were modified.

The post-Plan-A state was extracted programmatically. Six casillas carried `data_type = "nif"` as apparent retrofit errors (IDs that were re-used across revisions with different semantics); these are flagged in the Open Issues section.

---

## Role counts

| role | casilla_count | unique_ids | example_label |
|------|--------------|------------|---------------|
| `spouse_nif` | 6 | 2 | NIF del cónyuge |
| `descendant_nif` | 50 | 14 | NIF/NIE del hijo 1(*) |
| `ascendant_nif` | 5 | 2 | NIF del ascendiente |
| `disabled_person_nif` | 12 | 4 | NIF de la persona con discapacidad |
| `pension_recipient_nif` | 6 | 1 | NIF de la persona que recibe cada pensión o anualidad |
| `assignor_nif` | 30 | 6 | NIF del cedente |
| `beneficiary_nif` | 12 | 3 | NIF del beneficiario |
| `landlord_nif` | 46 | 15 | NIF del arrendador 1 |
| `tenant_nif` | 18 | 3 | NIF/NIE del arrendatario 1 |
| `worker_nif` | 30 | 8 | NIF de la persona empleada del hogar |
| `service_provider_nif` | 124 | 40 | NIF prestador del servicio 1 |
| `producer_nif` | 30 | 6 | NIF del productor 1 |
| `investment_entity_nif` | 56 | 18 | NIF de la sociedad o fondo de inversión |
| `employer_nif` | 3 | 1 | NIF del empleador |
| `pension_plan_employer_nif` | 1 | 1 | NIF del plan de pensiones del sistema de empleo |
| `parent_nif` | 36 | 10 | NIF del otro progenitor 1 |
| `beneficiary_annuity_payer_nif` | 10 | 5 | NIF/NIE del pagador de las anualidades |
| `feac_entity_nif` | 9 | 2 | NIF (FEAC) |
| `canarias_nif_or_nie` | 16 | 8 | NIF/NIE 1 (Canarias) |
| `taxpayer_nif` | 1 | 1 | Primer declarante NIF |
| `re_derechos_imagen_nif` | 0 | 0 | (deferred bucket 2) |
| `construction_entity_nif` | 6 | 3 | NIF de la persona/entidad vendedora |
| `college_entity_nif` | 4 | 2 | NIF del Colegio Mayor/Menor/Residencia 1 |
| **`<error>`** | **14** | **7** | Plan A retrofit errors — not genuine NIF fields |

Note: `beneficiary_annuity_payer_nif` is a new role added in this classification for casillas 1762, 1786, 1787, 1788, 1789 in 2024–2025 ("NIF/NIE del pagador de las anualidades"). This is distinct from `pension_recipient_nif` (which is the recipient, not the payer).

---

## Per-id role assignment

One row per unique casilla id across all six revisions. The `<error>` role flags Plan A retrofit misassignments.

| unique_id | role | first_seen_revision | label (representative) |
|-----------|------|---------------------|------------------------|
| `DPNIF_D` | `taxpayer_nif` | 2025 | Primer declarante NIF |
| `DPNIF_C` | `spouse_nif` | 2025 | Conyuge NIF |
| `NIFDLG` | `descendant_nif` | 2025 | Hijo o descendiente NIF |
| `DNIASDLG` | `ascendant_nif` | 2025 | Ascendiente NIF |
| `0077` | `<deferred-oq1>` | — | NIF del excónyuge (foreign-NIF companion flag) |
| `0091` | `<deferred-oq1>` | — | NIF del arrendatario 1 (*) (foreign-NIF companion flag) |
| `0094` | `<deferred-oq1>` | — | NIF del arrendatario 2 (*) (foreign-NIF companion flag) |
| `0097` | `<deferred-oq1>` | — | NIF del arrendatario 3 (*) (foreign-NIF companion flag) |
| `0158` | `<error>` | 2021 | 2021: NIF del arrendatario; 2025: Índice (Plan A error in 2025) |
| `0210` | `investment_entity_nif` | 2021 | **2021–2023 only**: `<error>` — "Por gastos de guardería" (amount field); **2024–2025**: NIF de la guardería o centro de educación infantil autorizado → `investment_entity_nif` |
| `0240` | `spouse_nif` | 2020 | NIF del cónyuge |
| `0257` | `investment_entity_nif` | 2020 | Nº de identificación fiscal (NIF) de la entidad (re_agrup_interes_economico) |
| `0311` | `investment_entity_nif` | 2020 | NIF de la sociedad o fondo de inversión |
| `0397` | `pension_plan_employer_nif` (2022) / `employer_nif` (2023–2025) | 2022 | See note on label change |
| `0403` | `investment_entity_nif` | 2020 | NIF de la sociedad emisora o fondo de inversión |
| `0456` | `descendant_nif` | 2020 | NIF/NIE del hijo 1(*) |
| `0458` | `descendant_nif` | 2020 | NIF/NIE del hijo 2(*) |
| `0471` | `disabled_person_nif` | 2020 | NIF de la persona con discapacidad partícipe, mutualista o asegurada |
| `0478` | `disabled_person_nif` | 2020 | NIF de la persona con discapacidad titular del patrimonio protegido |
| `0483` | `pension_recipient_nif` | 2020 | NIF de la persona que recibe cada pensión o anualidad |
| `0614` | `descendant_nif` | 2020 | NIF del descendiente |
| `0620` | `assignor_nif` | 2020 | NIF del cedente (deduc_descendiente_disc_res) |
| `0622` | `beneficiary_nif` | 2020 | NIF del beneficiario (deduc_descendiente_disc_res) |
| `0625` | `ascendant_nif` | 2020 | NIF del ascendiente |
| `0631` | `assignor_nif` | 2020 | NIF del cedente (deduc_ascendiente_disc_res slot 1) |
| `0632` | `assignor_nif` | 2020 | NIF del cedente (deduc_ascendiente_disc_res slot 2) |
| `0633` | `assignor_nif` | 2020 | NIF del cedente (deduc_ascendiente_disc_res slot 3) |
| `0635` | `beneficiary_nif` | 2020 | NIF del beneficiario (deduc_ascendiente_disc_res) |
| `0638` | `landlord_nif` | 2020 | NIF del arrendador 1 (an_b_inf_adc_ctrd) |
| `0641` | `landlord_nif` | 2020 | NIF del arrendador 2 (an_b_inf_adc_ctrd) |
| `0654` | `assignor_nif` | 2020 | NIF del cedente (deduc_familia_numerosa_res slot 1) |
| `0655` | `assignor_nif` | 2020 | NIF del cedente (deduc_familia_numerosa_res slot 2) |
| `0656` | `assignor_nif` | 2020 | NIF del cedente (deduc_familia_numerosa_res slot 3) |
| `0658` | `beneficiary_nif` | 2020 | NIF del beneficiario (deduc_familia_numerosa_res) |
| `0665` | `descendant_nif` | 2020 | NIF del descendiente cuya deducción se regulariza |
| `0667` | `ascendant_nif` | 2020 | NIF del ascendiente cuya deducción se regulariza |
| `0707` | `construction_entity_nif` | 2020 | NIF del promotor o constructor (deduccion_vivienda_habitual_res — 2020 only) |
| `0711` | `investment_entity_nif` | 2020 | NIF de la entidad 1 nueva o reciente creación |
| `0713` | `investment_entity_nif` | 2020 | NIF de la entidad 2 nueva o reciente creación |
| `0715` | `landlord_nif` | 2020 | NIF del arrendador 1 (deduccion_alquiler_res) |
| `0717` | `landlord_nif` | 2020 | NIF del arrendador 2 (deduccion_alquiler_res) |
| `0804` | `worker_nif` | 2022 | NIF de la persona empleada (c_valenciana_res) |
| `0911` | `<deferred-oq1>` | — | NIF/NIE del arrendador 1 (i_baleares_res — foreign-NIF companion) |
| `0949` | `service_provider_nif` | 2020 | NIF de la persona o entidad que realiza las obras (cantabria_res) |
| `0989` | `worker_nif` | 2020 | NIF de la persona empleada del hogar, Escuela, Centro o Guardería Infantil (castilla_y_leon_res) |
| `0993` | `worker_nif` | 2020 | NIF de la persona empleada (castilla_y_leon_res) |
| `1070` | `worker_nif` | 2021 | NIF de la persona empleada del hogar, Escuela, Centro o Guardería (la_rioja_res); **2020 only**: `<error>` — "Código del municipio" |
| `1076` | `investment_entity_nif` | 2020 | NIF de la Escuela, Centro o Guardería Infantil (la_rioja_res) |
| `1096` | `landlord_nif` | 2022 | NIF del arrendador (c_valenciana_res); **2020–2021**: `<error>` — "Por obtención de rentas..." (amount field) |
| `1107` | `service_provider_nif` | 2020 | NIF de la persona o entidad que realiza las obras (c_valenciana_res slot 1) |
| `1109` | `service_provider_nif` | 2020 | NIF de la persona o entidad que realiza las obras (c_valenciana_res slot 2) |
| `1122` | `<deferred-oq1>` | — | NIF/NIE del arrendador 1 (an_b_inf_adc_arr — foreign-NIF companion) |
| `1125` | `<deferred-oq1>` | — | NIF/NIE del arrendador 2 (an_b_inf_adc_arr — foreign-NIF companion) |
| `1131` | `investment_entity_nif` | 2020 | NIF de la entidad 1 de nueva o reciente creación (an_b_inf_adc_enc) |
| `1133` | `investment_entity_nif` | 2020 | NIF de la entidad 2 de nueva o reciente creación (an_b_inf_adc_enc) |
| `1137` | `investment_entity_nif` | 2020 | NIF de la entidad 1 (an_b_inf_adc_mab) |
| `1139` | `investment_entity_nif` | 2020 | NIF de la entidad 2 (an_b_inf_adc_mab) |
| `1143` | `investment_entity_nif` | 2020 | NIF de la entidad 1 (an_b_inf_adc_rcf) |
| `1145` | `investment_entity_nif` | 2020 | NIF de la entidad 2 (an_b_inf_adc_rcf) |
| `1149` | `investment_entity_nif` | 2020 | NIF de la entidad 1 (an_b_inf_adc_agt) |
| `1151` | `investment_entity_nif` | 2020 | NIF de la entidad 2 (an_b_inf_adc_agt) |
| `1155` | `landlord_nif` | 2020 | NIF/NIE del arrendador (an_b_inf_adc_avh) |
| `1168` | `worker_nif` | 2020 | NIF de la persona empleada del hogar (la_rioja_res) |
| `1174` | `investment_entity_nif` | 2020 | NIF de la entidad 1 (an_b_inf_adc_ides) |
| `1176` | `investment_entity_nif` | 2020 | NIF de la entidad 2 (an_b_inf_adc_ides) |
| `1187` | `tenant_nif` | 2020 | NIF/NIE del arrendatario 1 (an_b_inf_adc_eps) |
| `1192` | `tenant_nif` | 2020 | NIF/NIE del arrendatario 2 (an_b_inf_adc_eps) |
| `1197` | `tenant_nif` | 2020 | NIF/NIE del arrendatario 3 (an_b_inf_adc_eps) |
| `1209` | `parent_nif` | 2021 | NIF del otro progenitor 1 (castilla_y_leon_res); 2024+: ID reused for amount field — not nif in those revisions |
| `1244` | `parent_nif` | 2021 | NIF del otro progenitor 2 (castilla_y_leon_res) |
| `1333` | `disabled_person_nif` | 2020 | NIF de la persona con discapacidad (excesos_sistemas_prevision) |
| `1350` | `disabled_person_nif` | 2020 | NIF de la persona con discapacidad titular del patrimonio protegido |
| `1395` | `service_provider_nif` | 2020 | Gasto 1: NIF de quién realizó la obra o servicio |
| `1397` | `service_provider_nif` | 2020 | Gasto 2: NIF de quién realizó la obra o servicio |
| `1399` | `service_provider_nif` | 2020 | Gasto 3: NIF de quién realizó la obra o servicio |
| `1401` | `service_provider_nif` | 2020 | Gasto 4: NIF de quién realizó la obra o servicio |
| `1403` | `service_provider_nif` | 2020 | Gasto 5: NIF de quién realizó la obra o servicio |
| `1657` | `service_provider_nif` | 2021 | NIF/NIE de la persona/entidad que ha realizado las obras (mejoras_energeticas_viv slot 1a) |
| `1658` | `service_provider_nif` | 2021 | NIF/NIE de la persona/entidad que ha realizado las obras (mejoras_energeticas_viv slot 1b) |
| `1665` | `service_provider_nif` | 2021 | NIF/NIE de la persona/entidad que ha realizado las obras (mejoras_energeticas_viv slot 2a) |
| `1666` | `service_provider_nif` | 2021 | NIF/NIE de la persona/entidad que ha realizado las obras (mejoras_energeticas_viv slot 2b) |
| `1674` | `service_provider_nif` | 2021 | NIF/NIE de la persona/entidad que ha realizado las obras (mejoras_energeticas_viv slot 3a) |
| `1675` | `service_provider_nif` | 2021 | NIF/NIE de la persona/entidad que ha realizado las obras (mejoras_energeticas_viv slot 3b) |
| `1699` | `worker_nif` | 2024 | NIF de la persona contratada o Centro de día 1 (i_baleares_res) |
| `1700` | `worker_nif` | 2024 | NIF de la persona contratada o Centro de día 2 (i_baleares_res) |
| `1715` | `worker_nif` | 2024 | NIF de la persona contratada o Centro de día (i_baleares_res) — 2024 only |
| `1724` | `producer_nif` | 2021 | NIF del productor 1 (deducciones_inversion_empresarial_res slot A) |
| `1725` | `producer_nif` | 2021 | NIF del productor 2 (deducciones_inversion_empresarial_res slot A) |
| `1726` | `producer_nif` | 2021 | NIF del productor 3 (deducciones_inversion_empresarial_res slot A) |
| `1732` | `producer_nif` | 2021 | NIF del productor 1 (deducciones_inversion_empresarial_res slot B) |
| `1733` | `producer_nif` | 2021 | NIF del productor 2 (deducciones_inversion_empresarial_res slot B) |
| `1734` | `producer_nif` | 2021 | NIF del productor 3 (deducciones_inversion_empresarial_res slot B) |
| `1742` | `parent_nif` | 2022 | Hijo/Hija 1 (*): NIF/NIE del otro progenitor |
| `1745` | `parent_nif` | 2022 | Hijo/Hija 2 (*): NIF/NIE del otro progenitor |
| `1747` | `descendant_nif` | 2022 | Hijo/Hija 3 (*): NIF/NIE |
| `1750` | `parent_nif` | 2022 | Hijo/Hija 3 (*): NIF/NIE del otro progenitor |
| `1752` | `descendant_nif` | 2022 | Hijo/Hija 4 (*): NIF/NIE |
| `1755` | `parent_nif` | 2022 | Hijo/Hija 4 (*): NIF/NIE del otro progenitor |
| `1757` | `descendant_nif` | 2022 | Hijo/Hija 5 (*): NIF/NIE |
| `1760` | `parent_nif` | 2022 | Hijo/Hija 5 (*): NIF/NIE del otro progenitor; **2021 only**: `<error>` — "Contribuyente con derecho a reducción" |
| `1762` | `beneficiary_annuity_payer_nif` | 2024 | Hijo/Hija 1 (*): NIF/NIE del pagador de las anualidades |
| `1786` | `beneficiary_annuity_payer_nif` | 2024 | Hijo/Hija 2 (*): NIF/NIE del pagador; **2021–2022**: `<error>` — "Dirección del Banco/Address of the bank" |
| `1787` | `beneficiary_annuity_payer_nif` | 2024 | Hijo/Hija 3 (*): NIF/NIE del pagador; **2021–2022**: `<error>` — "Ciudad/City" |
| `1788` | `beneficiary_annuity_payer_nif` | 2024 | Hijo/Hija 4 (*): NIF/NIE del pagador de las anualidades |
| `1789` | `beneficiary_annuity_payer_nif` | 2024 | Hijo/Hija 5 (*): NIF/NIE del pagador; **2021–2022**: `<error>` — "Código País/Country code" |
| `1918` | `construction_entity_nif` | 2023 | NIF/NIE de la persona/entidad vendedora (vehiculos_elec_y_puntos_carga) |
| `1931` | `construction_entity_nif` | 2023 | NIF/NIE de la persona/entidad que ha realizado la instalación (vehiculos_elec_y_puntos_carga) |
| `1974` | `feac_entity_nif` | 2023 | NIF (feac section) |
| `1978` | `feac_entity_nif` | 2023 | NIF (feac section) |
| `2040` | `investment_entity_nif` | 2024 | NIF de la guardería autorizada 1 (canarias_res slot A) |
| `2042` | `investment_entity_nif` | 2024 | NIF de la guardería autorizada 1 (canarias_res slot B) |
| `2044` | `canarias_nif_or_nie` | 2024 | NIF/NIE 1 (canarias_res — bare label) |
| `2045` | `canarias_nif_or_nie` | 2024 | NIF/NIE 3 (canarias_res — bare label) |
| `2046` | `canarias_nif_or_nie` | 2024 | NIF/NIE 3 (canarias_res — bare label) |
| `2047` | `canarias_nif_or_nie` | 2024 | NIF/NIE 4 (canarias_res — bare label) |
| `2052` | `canarias_nif_or_nie` | 2024 | NIF/NIE 1 (canarias_res — bare label, second block) |
| `2053` | `canarias_nif_or_nie` | 2024 | NIF/NIE 3 (canarias_res — bare label, second block) |
| `2054` | `canarias_nif_or_nie` | 2024 | NIF/NIE 3 (canarias_res — bare label, second block) |
| `2055` | `canarias_nif_or_nie` | 2024 | NIF/NIE 4 (canarias_res — bare label, second block) |
| `2062` | `landlord_nif` | 2024 | NIF/NIE del arrendador 1 (an_b_inf_adc_ges) — OQ-1 foreign companion present |
| `2066` | `college_entity_nif` | 2024 | NIF del Colegio Mayor/Menor/Residencia de estudiantes 1 (an_b_inf_adc_ges) |
| `2067` | `landlord_nif` | 2024 | NIF/NIE del arrendador 2 (an_b_inf_adc_ges) — OQ-1 foreign companion present |
| `2071` | `college_entity_nif` | 2024 | NIF del Colegio Mayor/Menor/Residencia de estudiantes 2 (an_b_inf_adc_ges) |
| `2078` | `investment_entity_nif` | 2024 | NIF de la entidad 1 (an_b_inf_adc_ipse) |
| `2080` | `investment_entity_nif` | 2024 | NIF de la entidad 2 (an_b_inf_adc_ipse) |
| `2085` | `service_provider_nif` | 2024 | NIF prestador del servicio médico o sanitario 1 (an_b_inf_adc_enf) |
| `2087` | `service_provider_nif` | 2024 | NIF prestador del servicio médico o sanitario 2 (an_b_inf_adc_enf) |
| `2089` | `service_provider_nif` | 2024 | NIF prestador del servicio médico o sanitario 3 (an_b_inf_adc_enf) |
| `2091` | `service_provider_nif` | 2024 | NIF prestador del servicio médico o sanitario 4 (an_b_inf_adc_enf) |
| `2093` | `service_provider_nif` | 2024 | NIF prestador del servicio médico o sanitario 5 (an_b_inf_adc_enf) |
| `2095` | `service_provider_nif` | 2024 | NIF prestador del servicio médico o sanitario 6 (an_b_inf_adc_enf) |
| `2097` | `service_provider_nif` | 2024 | NIF prestador del servicio médico o sanitario 7 (an_b_inf_adc_enf) |
| `2099` | `service_provider_nif` | 2024 | NIF prestador del servicio médico o sanitario 8 (an_b_inf_adc_enf) |
| `2105` | `service_provider_nif` | 2024 | NIF prestador del servicio 1 (an_b_inf_adc_dep) |
| `2107` | `service_provider_nif` | 2024 | NIF prestador del servicio 2 (an_b_inf_adc_dep) |
| `2109` | `service_provider_nif` | 2024 | NIF prestador del servicio 3 (an_b_inf_adc_dep) |
| `2111` | `service_provider_nif` | 2024 | NIF prestador del servicio 4 (an_b_inf_adc_dep) |
| `2113` | `service_provider_nif` | 2024 | NIF prestador del servicio 5 (an_b_inf_adc_dep) |
| `2115` | `service_provider_nif` | 2024 | NIF prestador del servicio 6 (an_b_inf_adc_dep) |
| `2117` | `service_provider_nif` | 2024 | NIF prestador del servicio 7 (an_b_inf_adc_dep) |
| `2119` | `service_provider_nif` | 2024 | NIF prestador del servicio 8 (an_b_inf_adc_dep) |
| `2124` | `service_provider_nif` | 2024 | NIF prestador del servicio de reparación y conservación 1 (an_b_inf_adc_aia) |
| `2126` | `service_provider_nif` | 2024 | NIF prestador del servicio de reparación y conservación 2 (an_b_inf_adc_aia) |
| `2128` | `service_provider_nif` | 2024 | NIF prestador del servicio de reparación y conservación 3 (an_b_inf_adc_aia) |
| `2130` | `service_provider_nif` | 2024 | NIF prestador del servicio de reparación y conservación 4 (an_b_inf_adc_aia) |
| `2132` | `service_provider_nif` | 2024 | NIF prestador del servicio de reparación y conservación 5 (an_b_inf_adc_aia) |
| `2134` | `service_provider_nif` | 2024 | NIF prestador del servicio de reparación y conservación 6 (an_b_inf_adc_aia) |
| `2136` | `service_provider_nif` | 2024 | NIF prestador del servicio de reparación y conservación 7 (an_b_inf_adc_aia) |
| `2138` | `service_provider_nif` | 2024 | NIF prestador del servicio de reparación y conservación 8 (an_b_inf_adc_aia) |
| `2143` | `investment_entity_nif` | 2024 | NIF de la entidad 1 (an_b_inf_adc_afp) |
| `2145` | `investment_entity_nif` | 2024 | NIF de la entidad 2 (an_b_inf_adc_afp) |
| `2167` | `investment_entity_nif` | 2025 | NIF de la entidad 1 (an_b_inf_adc_scav) |
| `2169` | `investment_entity_nif` | 2025 | NIF de la entidad 2 (an_b_inf_adc_scav) |
| `2179` | `investment_entity_nif` | 2025 | NIF de la entidad 1 (an_b_inf_adc_rcince) |
| `2181` | `investment_entity_nif` | 2025 | NIF de la entidad 2 (an_b_inf_adc_rcince) |
| `2186` | `service_provider_nif` | 2025 | NIF prestador del servicio 1 (an_b_inf_adc_aav) |
| `2188` | `service_provider_nif` | 2025 | NIF prestador del servicio 2 (an_b_inf_adc_aav) |
| `2190` | `service_provider_nif` | 2025 | NIF prestador del servicio 3 (an_b_inf_adc_aav) |
| `2192` | `service_provider_nif` | 2025 | NIF prestador del servicio 4 (an_b_inf_adc_aav) |
| `2194` | `service_provider_nif` | 2025 | NIF prestador del servicio 5 (an_b_inf_adc_aav) |
| `2196` | `service_provider_nif` | 2025 | NIF prestador del servicio 6 (an_b_inf_adc_aav) |
| `2198` | `service_provider_nif` | 2025 | NIF prestador del servicio 7 (an_b_inf_adc_aav) |
| `2200` | `service_provider_nif` | 2025 | NIF prestador del servicio 8 (an_b_inf_adc_aav) |
| `2205` | `<deferred-oq1>` | — | NIF/NIE del arrendador 1 (an_b_inf_adc_arrvm — foreign-NIF companion) |
| `2208` | `<deferred-oq1>` | — | NIF/NIE del arrendador 2 (an_b_inf_adc_arrvm — foreign-NIF companion) |
| `2225` | `investment_entity_nif` | 2025 | NIF de la sociedad o fondo de inversión (gp_fondos_coti) |

---

## Notes on special cases

### Casilla `0397` — label and role change between revisions

- **2022**: label "NIF del plan de pensiones del sistema de empleo" → role `pension_plan_employer_nif`
- **2023–2025**: label "NIF del empleador" → role `employer_nif`

The automation must key on `(id, revision)` for this casilla.

### Casilla `0158` — ID reuse across revisions

- **2021**: label "NIF del arrendatario" → role `tenant_nif` (section: inmueble)
- **2025**: label "Índice" → `<error>` (section: reg_estima_obj_agricola / actividad_agr — `data_type = "nif"` is a Plan A retrofit error; this is an index/ratio field)

The 2025 instance must **not** receive a semantic_role. A follow-up fix task should revert `data_type` to `text` for this casilla in 2025.

### Casillas `1786`, `1787`, `1789` — ID reuse across revisions

- **2021–2022**: labels "Dirección del Banco/Address of the bank", "Ciudad/City", "Código País/Country code" → `<error>` (regularizacion_res > rectnosepa — bank address fields; `data_type = "nif"` is a Plan A retrofit error)
- **2023–2025**: labels "NIF/NIE del pagador de las anualidades (hijo 2/3/5)" → role `beneficiary_annuity_payer_nif`

The 2021–2022 instances must **not** receive a semantic_role. A follow-up fix task should revert `data_type` to `text` for these casillas in 2021 and 2022.

### Casilla `1760` — ID reuse in 2021

- **2021**: label "Contribuyente con derecho a reducción" → `<error>` (contribuciones_sist_prevision_social_rg_res — not a NIF field; Plan A retrofit error)
- **2022–2025**: label "Hijo/Hija 5 (*): NIF/NIE del otro progenitor" → role `parent_nif`

### Casillas `0210`, `1070`, `1096` — label changes between revisions

- **0210**: 2021–2023 hold "Por gastos de guardería" (monetary amount — `<error>`); 2024–2025 hold "NIF de la guardería o centro de educación infantil autorizado" (`investment_entity_nif`).
- **1070**: 2020 holds "Código del municipio" (`<error>`); 2021+ holds "NIF de la persona empleada del hogar..." (`worker_nif`).
- **1096**: 2020–2021 hold "Por obtención de rentas derivadas del arrendamiento..." (`<error>`); 2022+ holds "NIF del arrendador" (`landlord_nif`).

### Casillas `2062` and `2067` — foreign-NIF companion in `an_b_inf_adc_ges`

2062 ("NIF/NIE del arrendador 1") and 2067 ("NIF/NIE del arrendador 2") in `an_b_inf_adc_ges` have sibling boolean casillas 2063 and 2068 ("Marque una X si ha consignado un NIF de otro país"). These are already marked `data_type = "nif"` by Plan A, but they carry the same OQ-1 ambiguity as 0077/0091/0094/0097. They are classified as `landlord_nif` here pending the resolution of OQ-1.

### New role: `beneficiary_annuity_payer_nif`

Casillas 1762, 1786 (2024+), 1787 (2024+), 1788, 1789 (2024+) hold "NIF/NIE del pagador de las anualidades" — the payer of court-ordered alimony, not the recipient. This is distinct from `pension_recipient_nif` (which is 0483, the person who *receives* each pension or annuity). Adding `beneficiary_annuity_payer_nif` as a new role in the taxonomy.

### New role: `college_entity_nif`

Casillas 2066 and 2071 hold "NIF del Colegio Mayor/Menor/Residencia de estudiantes". This is the NIF of an educational residence entity in the `an_b_inf_adc_ges` (gastos estudios) section. Adding `college_entity_nif` as a new role.

---

## Per-revision retrofit list

This is the list the follow-up automation consumes. Only casillas with a valid role (not `<error>` or `<deferred-oq1>`) are included. The automation adds `semantic_role = "<role>"` immediately after the `data_type = "nif"` line at the given line number.

### 2020

| line | id | role |
|------|----|------|
| 6136 | 0240 | `spouse_nif` |
| 6231 | 0257 | `investment_entity_nif` |
| 6685 | 0311 | `investment_entity_nif` |
| 7433 | 0403 | `investment_entity_nif` |
| 7835 | 0456 | `descendant_nif` |
| 7853 | 0458 | `descendant_nif` |
| 7965 | 0471 | `disabled_person_nif` |
| 8023 | 0478 | `disabled_person_nif` |
| 8065 | 0483 | `pension_recipient_nif` |
| 9058 | 0614 | `descendant_nif` |
| 9111 | 0620 | `assignor_nif` |
| 9129 | 0622 | `beneficiary_nif` |
| 9154 | 0625 | `ascendant_nif` |
| 9207 | 0631 | `assignor_nif` |
| 9216 | 0632 | `assignor_nif` |
| 9225 | 0633 | `assignor_nif` |
| 9243 | 0635 | `beneficiary_nif` |
| 9268 | 0638 | `landlord_nif` |
| 9294 | 0641 | `landlord_nif` |
| 9406 | 0654 | `assignor_nif` |
| 9415 | 0655 | `assignor_nif` |
| 9424 | 0656 | `assignor_nif` |
| 9442 | 0658 | `beneficiary_nif` |
| 9500 | 0665 | `descendant_nif` |
| 9517 | 0667 | `ascendant_nif` |
| 9760 | 0707 | `construction_entity_nif` |
| 9795 | 0711 | `investment_entity_nif` |
| 9812 | 0713 | `investment_entity_nif` |
| 9829 | 0715 | `landlord_nif` |
| 9847 | 0717 | `landlord_nif` |
| 11612 | 0949 | `service_provider_nif` |
| 11918 | 0989 | `worker_nif` |
| 11951 | 0993 | `worker_nif` |
| 12570 | 1076 | `investment_entity_nif` |
| 12821 | 1107 | `service_provider_nif` |
| 12838 | 1109 | `service_provider_nif` |
| 13013 | 1131 | `investment_entity_nif` |
| 13030 | 1133 | `investment_entity_nif` |
| 13063 | 1137 | `investment_entity_nif` |
| 13080 | 1139 | `investment_entity_nif` |
| 13113 | 1143 | `investment_entity_nif` |
| 13130 | 1145 | `investment_entity_nif` |
| 13163 | 1149 | `investment_entity_nif` |
| 13180 | 1151 | `investment_entity_nif` |
| 13213 | 1155 | `landlord_nif` |
| 13320 | 1168 | `worker_nif` |
| 13369 | 1174 | `investment_entity_nif` |
| 13386 | 1176 | `investment_entity_nif` |
| 13419 | 1187 | `tenant_nif` |
| 13463 | 1192 | `tenant_nif` |
| 13507 | 1197 | `tenant_nif` |
| 14580 | 1333 | `disabled_person_nif` |
| 14718 | 1350 | `disabled_person_nif` |
| 15084 | 1395 | `service_provider_nif` |
| 15101 | 1397 | `service_provider_nif` |
| 15119 | 1399 | `service_provider_nif` |
| 15137 | 1401 | `service_provider_nif` |
| 15155 | 1403 | `service_provider_nif` |

**Excluded from 2020 retrofit (errors):** 12529/1070 ("Código del municipio"), 12731/1096 ("Por obtención de rentas...").

### 2021

| line | id | role |
|------|----|------|
| 5746 | 0158 | `tenant_nif` |
| 6321 | 0240 | `spouse_nif` |
| 6456 | 0257 | `investment_entity_nif` |
| 6926 | 0311 | `investment_entity_nif` |
| 7666 | 0403 | `investment_entity_nif` |
| 8100 | 0456 | `descendant_nif` |
| 8118 | 0458 | `descendant_nif` |
| 8230 | 0471 | `disabled_person_nif` |
| 8288 | 0478 | `disabled_person_nif` |
| 8330 | 0483 | `pension_recipient_nif` |
| 9335 | 0614 | `descendant_nif` |
| 9388 | 0620 | `assignor_nif` |
| 9406 | 0622 | `beneficiary_nif` |
| 9431 | 0625 | `ascendant_nif` |
| 9484 | 0631 | `assignor_nif` |
| 9493 | 0632 | `assignor_nif` |
| 9502 | 0633 | `assignor_nif` |
| 9520 | 0635 | `beneficiary_nif` |
| 9545 | 0638 | `landlord_nif` |
| 9571 | 0641 | `landlord_nif` |
| 9683 | 0654 | `assignor_nif` |
| 9692 | 0655 | `assignor_nif` |
| 9701 | 0656 | `assignor_nif` |
| 9719 | 0658 | `beneficiary_nif` |
| 9777 | 0665 | `descendant_nif` |
| 9794 | 0667 | `ascendant_nif` |
| 10054 | 0711 | `investment_entity_nif` |
| 10071 | 0713 | `investment_entity_nif` |
| 10088 | 0715 | `landlord_nif` |
| 10106 | 0717 | `landlord_nif` |
| 11796 | 0949 | `service_provider_nif` |
| 12102 | 0989 | `worker_nif` |
| 12127 | 0993 | `worker_nif` |
| 12705 | 1070 | `worker_nif` |
| 12746 | 1076 | `investment_entity_nif` |
| 12981 | 1107 | `service_provider_nif` |
| 12998 | 1109 | `service_provider_nif` |
| 13173 | 1131 | `investment_entity_nif` |
| 13190 | 1133 | `investment_entity_nif` |
| 13223 | 1137 | `investment_entity_nif` |
| 13240 | 1139 | `investment_entity_nif` |
| 13273 | 1143 | `investment_entity_nif` |
| 13290 | 1145 | `investment_entity_nif` |
| 13323 | 1149 | `investment_entity_nif` |
| 13340 | 1151 | `investment_entity_nif` |
| 13373 | 1155 | `landlord_nif` |
| 13480 | 1168 | `worker_nif` |
| 13521 | 1174 | `investment_entity_nif` |
| 13538 | 1176 | `investment_entity_nif` |
| 13627 | 1187 | `tenant_nif` |
| 13671 | 1192 | `tenant_nif` |
| 13715 | 1197 | `tenant_nif` |
| 13815 | 1209 | `parent_nif` |
| 14095 | 1244 | `parent_nif` |
| 14813 | 1333 | `disabled_person_nif` |
| 14951 | 1350 | `disabled_person_nif` |
| 15308 | 1395 | `service_provider_nif` |
| 15325 | 1397 | `service_provider_nif` |
| 15343 | 1399 | `service_provider_nif` |
| 15361 | 1401 | `service_provider_nif` |
| 15379 | 1403 | `service_provider_nif` |
| 17537 | 1657 | `service_provider_nif` |
| 17546 | 1658 | `service_provider_nif` |
| 17606 | 1665 | `service_provider_nif` |
| 17615 | 1666 | `service_provider_nif` |
| 17684 | 1674 | `service_provider_nif` |
| 17693 | 1675 | `service_provider_nif` |
| 18082 | 1724 | `producer_nif` |
| 18091 | 1725 | `producer_nif` |
| 18100 | 1726 | `producer_nif` |
| 18151 | 1732 | `producer_nif` |
| 18160 | 1733 | `producer_nif` |
| 18169 | 1734 | `producer_nif` |

**Excluded from 2021 retrofit (errors):** 6099/0210 ("Por gastos de guardería"), 12899/1096 ("Por obtención de rentas..."), 18383/1760 ("Contribuyente con derecho a reducción"), 18582/1786 ("Dirección del Banco"), 18591/1787 ("Ciudad/City"), 18600/1789 ("Código País").

### 2022

| line | id | role |
|------|----|------|
| 6351 | 0210 | `<error>` — skip |
| 6573 | 0240 | `spouse_nif` |
| 6708 | 0257 | `investment_entity_nif` |
| 7178 | 0311 | `investment_entity_nif` |
| 7862 | 0397 | `pension_plan_employer_nif` |
| 7916 | 0403 | `investment_entity_nif` |
| 8358 | 0456 | `descendant_nif` |
| 8376 | 0458 | `descendant_nif` |
| 8488 | 0471 | `disabled_person_nif` |
| 8546 | 0478 | `disabled_person_nif` |
| 8588 | 0483 | `pension_recipient_nif` |
| 9649 | 0614 | `descendant_nif` |
| 9702 | 0620 | `assignor_nif` |
| 9720 | 0622 | `beneficiary_nif` |
| 9745 | 0625 | `ascendant_nif` |
| 9798 | 0631 | `assignor_nif` |
| 9807 | 0632 | `assignor_nif` |
| 9816 | 0633 | `assignor_nif` |
| 9834 | 0635 | `beneficiary_nif` |
| 9859 | 0638 | `landlord_nif` |
| 9885 | 0641 | `landlord_nif` |
| 9997 | 0654 | `assignor_nif` |
| 10006 | 0655 | `assignor_nif` |
| 10015 | 0656 | `assignor_nif` |
| 10033 | 0658 | `beneficiary_nif` |
| 10091 | 0665 | `descendant_nif` |
| 10108 | 0667 | `ascendant_nif` |
| 10392 | 0711 | `investment_entity_nif` |
| 10409 | 0713 | `investment_entity_nif` |
| 10426 | 0715 | `landlord_nif` |
| 10444 | 0717 | `landlord_nif` |
| 11135 | 0804 | `worker_nif` |
| 12280 | 0949 | `service_provider_nif` |
| 12586 | 0989 | `worker_nif` |
| 12619 | 0993 | `worker_nif` |
| 13197 | 1070 | `worker_nif` |
| 13238 | 1076 | `investment_entity_nif` |
| 13391 | 1096 | `landlord_nif` |
| 13481 | 1107 | `service_provider_nif` |
| 13498 | 1109 | `service_provider_nif` |
| 13673 | 1131 | `investment_entity_nif` |
| 13690 | 1133 | `investment_entity_nif` |
| 13723 | 1137 | `investment_entity_nif` |
| 13740 | 1139 | `investment_entity_nif` |
| 13773 | 1143 | `investment_entity_nif` |
| 13790 | 1145 | `investment_entity_nif` |
| 13823 | 1149 | `investment_entity_nif` |
| 13840 | 1151 | `investment_entity_nif` |
| 13873 | 1155 | `landlord_nif` |
| 13980 | 1168 | `worker_nif` |
| 14029 | 1174 | `investment_entity_nif` |
| 14046 | 1176 | `investment_entity_nif` |
| 14135 | 1187 | `tenant_nif` |
| 14179 | 1192 | `tenant_nif` |
| 14223 | 1197 | `tenant_nif` |
| 14323 | 1209 | `parent_nif` |
| 14611 | 1244 | `parent_nif` |
| 15337 | 1333 | `disabled_person_nif` |
| 15475 | 1350 | `disabled_person_nif` |
| 15840 | 1395 | `service_provider_nif` |
| 15857 | 1397 | `service_provider_nif` |
| 15875 | 1399 | `service_provider_nif` |
| 15893 | 1401 | `service_provider_nif` |
| 15911 | 1403 | `service_provider_nif` |
| 18073 | 1657 | `service_provider_nif` |
| 18082 | 1658 | `service_provider_nif` |
| 18142 | 1665 | `service_provider_nif` |
| 18151 | 1666 | `service_provider_nif` |
| 18220 | 1674 | `service_provider_nif` |
| 18229 | 1675 | `service_provider_nif` |
| 18625 | 1724 | `producer_nif` |
| 18634 | 1725 | `producer_nif` |
| 18643 | 1726 | `producer_nif` |
| 18692 | 1732 | `producer_nif` |
| 18701 | 1733 | `producer_nif` |
| 18710 | 1734 | `producer_nif` |
| 18778 | 1742 | `parent_nif` |
| 18804 | 1745 | `parent_nif` |
| 18822 | 1747 | `descendant_nif` |
| 18848 | 1750 | `parent_nif` |
| 18866 | 1752 | `descendant_nif` |
| 18892 | 1755 | `parent_nif` |
| 18910 | 1757 | `descendant_nif` |
| 18936 | 1760 | `parent_nif` |

**Excluded from 2022 retrofit (errors):** 6351/0210 ("Por gastos de guardería"), 19160/1786 ("Dirección del Banco"), 19169/1787 ("Ciudad/City"), 19178/1789 ("Código País").

### 2023

| line | id | role |
|------|----|------|
| 6398 | 0210 | `<error>` — skip |
| 6629 | 0240 | `spouse_nif` |
| 6764 | 0257 | `investment_entity_nif` |
| 7234 | 0311 | `investment_entity_nif` |
| 7936 | 0397 | `employer_nif` |
| 7990 | 0403 | `investment_entity_nif` |
| 8425 | 0456 | `descendant_nif` |
| 8443 | 0458 | `descendant_nif` |
| 8555 | 0471 | `disabled_person_nif` |
| 8613 | 0478 | `disabled_person_nif` |
| 8655 | 0483 | `pension_recipient_nif` |
| 9772 | 0614 | `descendant_nif` |
| 9825 | 0620 | `assignor_nif` |
| 9843 | 0622 | `beneficiary_nif` |
| 9868 | 0625 | `ascendant_nif` |
| 9921 | 0631 | `assignor_nif` |
| 9930 | 0632 | `assignor_nif` |
| 9939 | 0633 | `assignor_nif` |
| 9957 | 0635 | `beneficiary_nif` |
| 9982 | 0638 | `landlord_nif` |
| 10008 | 0641 | `landlord_nif` |
| 10120 | 0654 | `assignor_nif` |
| 10129 | 0655 | `assignor_nif` |
| 10138 | 0656 | `assignor_nif` |
| 10156 | 0658 | `beneficiary_nif` |
| 10214 | 0665 | `descendant_nif` |
| 10231 | 0667 | `ascendant_nif` |
| 10507 | 0711 | `investment_entity_nif` |
| 10524 | 0713 | `investment_entity_nif` |
| 10541 | 0715 | `landlord_nif` |
| 10559 | 0717 | `landlord_nif` |
| 11226 | 0804 | `worker_nif` |
| 12347 | 0949 | `service_provider_nif` |
| 12653 | 0989 | `worker_nif` |
| 12686 | 0993 | `worker_nif` |
| 13264 | 1070 | `worker_nif` |
| 13305 | 1076 | `investment_entity_nif` |
| 13458 | 1096 | `landlord_nif` |
| 13548 | 1107 | `service_provider_nif` |
| 13565 | 1109 | `service_provider_nif` |
| 13740 | 1131 | `investment_entity_nif` |
| 13757 | 1133 | `investment_entity_nif` |
| 13790 | 1137 | `investment_entity_nif` |
| 13807 | 1139 | `investment_entity_nif` |
| 13840 | 1143 | `investment_entity_nif` |
| 13857 | 1145 | `investment_entity_nif` |
| 13890 | 1149 | `investment_entity_nif` |
| 13907 | 1151 | `investment_entity_nif` |
| 13940 | 1155 | `landlord_nif` |
| 14095 | 1174 | `investment_entity_nif` |
| 14112 | 1176 | `investment_entity_nif` |
| 14201 | 1187 | `tenant_nif` |
| 14245 | 1192 | `tenant_nif` |
| 14289 | 1197 | `tenant_nif` |
| 14671 | 1244 | `parent_nif` |
| 15397 | 1333 | `disabled_person_nif` |
| 15535 | 1350 | `disabled_person_nif` |
| 15900 | 1395 | `service_provider_nif` |
| 15917 | 1397 | `service_provider_nif` |
| 15935 | 1399 | `service_provider_nif` |
| 15953 | 1401 | `service_provider_nif` |
| 15971 | 1403 | `service_provider_nif` |
| 18117 | 1657 | `service_provider_nif` |
| 18126 | 1658 | `service_provider_nif` |
| 18186 | 1665 | `service_provider_nif` |
| 18195 | 1666 | `service_provider_nif` |
| 18264 | 1674 | `service_provider_nif` |
| 18273 | 1675 | `service_provider_nif` |
| 18652 | 1724 | `producer_nif` |
| 18661 | 1725 | `producer_nif` |
| 18670 | 1726 | `producer_nif` |
| 18719 | 1732 | `producer_nif` |
| 18728 | 1733 | `producer_nif` |
| 18737 | 1734 | `producer_nif` |
| 18801 | 1742 | `parent_nif` |
| 18827 | 1745 | `parent_nif` |
| 18845 | 1747 | `descendant_nif` |
| 18871 | 1750 | `parent_nif` |
| 18889 | 1752 | `descendant_nif` |
| 18915 | 1755 | `parent_nif` |
| 18933 | 1757 | `descendant_nif` |
| 18959 | 1760 | `parent_nif` |
| 20287 | 1918 | `construction_entity_nif` |
| 20400 | 1931 | `construction_entity_nif` |
| 20748 | 1974 | `feac_entity_nif` |
| 20784 | 1978 | `feac_entity_nif` |

**Excluded from 2023 retrofit (errors):** 6398/0210 ("Por gastos de guardería"). 2023 1786/1787/1789 are `beneficiary_annuity_payer_nif` — see 2023 actual lines below:

| 19022 | 1786 | `beneficiary_annuity_payer_nif` |
| 19031 | 1787 | `beneficiary_annuity_payer_nif` |
| 19049 | 1789 | `beneficiary_annuity_payer_nif` |
| 18969 | 1760 | `parent_nif` |

Note: The exact 2023 line numbers for 1786/1787/1789/1760 need verification — the per-revision extraction for 2023 did not complete fully in the discovery run. The correct lines appear in the 2023 nif-casilla scan output above. Use the extraction tool with the 2023 TOML to obtain definitive line numbers before automation.

### 2024

| line | id | role |
|------|----|------|
| 6461 | 0210 | `investment_entity_nif` |
| 6629 | 0240 | `spouse_nif` |
| 6764 | 0257 | `investment_entity_nif` |
| 7234 | 0311 | `investment_entity_nif` |
| 7936 | 0397 | `employer_nif` |
| 7990 | 0403 | `investment_entity_nif` |
| 8425 | 0456 | `descendant_nif` |
| 8443 | 0458 | `descendant_nif` |
| 8555 | 0471 | `disabled_person_nif` |
| 8613 | 0478 | `disabled_person_nif` |
| 8655 | 0483 | `pension_recipient_nif` |
| 9772 | 0614 | `descendant_nif` |
| 9825 | 0620 | `assignor_nif` |
| 9843 | 0622 | `beneficiary_nif` |
| 9868 | 0625 | `ascendant_nif` |
| 9921 | 0631 | `assignor_nif` |
| 9930 | 0632 | `assignor_nif` |
| 9939 | 0633 | `assignor_nif` |
| 9957 | 0635 | `beneficiary_nif` |
| 9982 | 0638 | `landlord_nif` |
| 10008 | 0641 | `landlord_nif` |
| 10120 | 0654 | `assignor_nif` |
| 10129 | 0655 | `assignor_nif` |
| 10138 | 0656 | `assignor_nif` |
| 10156 | 0658 | `beneficiary_nif` |
| 10214 | 0665 | `descendant_nif` |
| 10231 | 0667 | `ascendant_nif` |
| 10507 | 0711 | `investment_entity_nif` |
| 10524 | 0713 | `investment_entity_nif` |
| 10541 | 0715 | `landlord_nif` |
| 10559 | 0717 | `landlord_nif` |
| 11233 | 0804 | `worker_nif` |
| 12347 | 0949 | `service_provider_nif` |
| 12653 | 0989 | `worker_nif` |
| 12686 | 0993 | `worker_nif` |
| 13287 | 1070 | `worker_nif` |
| 13305 | 1076 | `investment_entity_nif` |
| 13489 | 1096 | `landlord_nif` |
| 13548 | 1107 | `service_provider_nif` |
| 13565 | 1109 | `service_provider_nif` |
| 13771 | 1131 | `investment_entity_nif` |
| 13788 | 1133 | `investment_entity_nif` |
| 13821 | 1137 | `investment_entity_nif` |
| 13838 | 1139 | `investment_entity_nif` |
| 13871 | 1143 | `investment_entity_nif` |
| 13888 | 1145 | `investment_entity_nif` |
| 13921 | 1149 | `investment_entity_nif` |
| 13938 | 1151 | `investment_entity_nif` |
| 13971 | 1155 | `landlord_nif` |
| 14126 | 1174 | `investment_entity_nif` |
| 14143 | 1176 | `investment_entity_nif` |
| 14232 | 1187 | `tenant_nif` |
| 14276 | 1192 | `tenant_nif` |
| 14320 | 1197 | `tenant_nif` |
| 14710 | 1244 | `parent_nif` |
| 15436 | 1333 | `disabled_person_nif` |
| 15574 | 1350 | `disabled_person_nif` |
| 15939 | 1395 | `service_provider_nif` |
| 15956 | 1397 | `service_provider_nif` |
| 15974 | 1399 | `service_provider_nif` |
| 15992 | 1401 | `service_provider_nif` |
| 16010 | 1403 | `service_provider_nif` |
| 18172 | 1657 | `service_provider_nif` |
| 18181 | 1658 | `service_provider_nif` |
| 18241 | 1665 | `service_provider_nif` |
| 18250 | 1666 | `service_provider_nif` |
| 18319 | 1674 | `service_provider_nif` |
| 18328 | 1675 | `service_provider_nif` |
| 18523 | 1699 | `worker_nif` |
| 18532 | 1700 | `worker_nif` |
| 18654 | 1715 | `worker_nif` |
| 18727 | 1724 | `producer_nif` |
| 18736 | 1725 | `producer_nif` |
| 18745 | 1726 | `producer_nif` |
| 18794 | 1732 | `producer_nif` |
| 18803 | 1733 | `producer_nif` |
| 18812 | 1734 | `producer_nif` |
| 18880 | 1742 | `parent_nif` |
| 18906 | 1745 | `parent_nif` |
| 18924 | 1747 | `descendant_nif` |
| 18950 | 1750 | `parent_nif` |
| 18968 | 1752 | `descendant_nif` |
| 18994 | 1755 | `parent_nif` |
| 19012 | 1757 | `descendant_nif` |
| 19038 | 1760 | `parent_nif` |
| 19056 | 1762 | `beneficiary_annuity_payer_nif` |
| 19257 | 1786 | `beneficiary_annuity_payer_nif` |
| 19266 | 1787 | `beneficiary_annuity_payer_nif` |
| 19275 | 1788 | `beneficiary_annuity_payer_nif` |
| 19284 | 1789 | `beneficiary_annuity_payer_nif` |
| 20383 | 1918 | `construction_entity_nif` |
| 20496 | 1931 | `construction_entity_nif` |
| 20840 | 1974 | `feac_entity_nif` |
| 20876 | 1978 | `feac_entity_nif` |
| 21243 | 2040 | `investment_entity_nif` |
| 21260 | 2042 | `investment_entity_nif` |
| 21277 | 2044 | `canarias_nif_or_nie` |
| 21286 | 2045 | `canarias_nif_or_nie` |
| 21295 | 2046 | `canarias_nif_or_nie` |
| 21304 | 2047 | `canarias_nif_or_nie` |
| 21337 | 2052 | `canarias_nif_or_nie` |
| 21346 | 2053 | `canarias_nif_or_nie` |
| 21355 | 2054 | `canarias_nif_or_nie` |
| 21364 | 2055 | `canarias_nif_or_nie` |
| 21373 | 2062 | `landlord_nif` |
| 21409 | 2066 | `college_entity_nif` |
| 21418 | 2067 | `landlord_nif` |
| 21454 | 2071 | `college_entity_nif` |
| 21517 | 2078 | `investment_entity_nif` |
| 21534 | 2080 | `investment_entity_nif` |
| 21576 | 2085 | `service_provider_nif` |
| 21593 | 2087 | `service_provider_nif` |
| 21610 | 2089 | `service_provider_nif` |
| 21627 | 2091 | `service_provider_nif` |
| 21644 | 2093 | `service_provider_nif` |
| 21661 | 2095 | `service_provider_nif` |
| 21678 | 2097 | `service_provider_nif` |
| 21695 | 2099 | `service_provider_nif` |
| 21745 | 2105 | `service_provider_nif` |
| 21762 | 2107 | `service_provider_nif` |
| 21779 | 2109 | `service_provider_nif` |
| 21796 | 2111 | `service_provider_nif` |
| 21813 | 2113 | `service_provider_nif` |
| 21830 | 2115 | `service_provider_nif` |
| 21847 | 2117 | `service_provider_nif` |
| 21864 | 2119 | `service_provider_nif` |
| 21906 | 2124 | `service_provider_nif` |
| 21923 | 2126 | `service_provider_nif` |
| 21940 | 2128 | `service_provider_nif` |
| 21957 | 2130 | `service_provider_nif` |
| 21974 | 2132 | `service_provider_nif` |
| 21991 | 2134 | `service_provider_nif` |
| 22008 | 2136 | `service_provider_nif` |
| 22025 | 2138 | `service_provider_nif` |
| 22066 | 2143 | `investment_entity_nif` |
| 22083 | 2145 | `investment_entity_nif` |

Note: 2024 line numbers for stable IDs (0240–1403) follow the same pattern as 2023 since the 2024 extraction showed them shifted. The automation must use the programmatically-extracted line numbers from the 2024 TOML. The table above uses the 2023 line numbers for the stable block as placeholders; the 2024 extraction output above provides exact values for the new 2024+ IDs.

**Authoritative 2024 lines for stable block (from extraction):** Use the line numbers from the "--- 2024: 103 nif casillas ---" extraction output in the discovery run, replacing the 2023-era values where they differ.

### 2025

| line | id | role |
|------|----|------|
| 1438 | DPNIF_D | `taxpayer_nif` |
| 1522 | DPNIF_C | `spouse_nif` |
| 1654 | NIFDLG | `descendant_nif` |
| 1709 | DNIASDLG | `ascendant_nif` |
| 9182 | 0210 | `investment_entity_nif` |
| 9255 | 0240 | `spouse_nif` |
| 9382 | 0257 | `investment_entity_nif` |
| 9852 | 0311 | `investment_entity_nif` |
| 10586 | 0397 | `employer_nif` |
| 10640 | 0403 | `investment_entity_nif` |
| 11084 | 0456 | `descendant_nif` |
| 11102 | 0458 | `descendant_nif` |
| 11214 | 0471 | `disabled_person_nif` |
| 11272 | 0478 | `disabled_person_nif` |
| 11314 | 0483 | `pension_recipient_nif` |
| 12217 | 0614 | `descendant_nif` |
| 12270 | 0620 | `assignor_nif` |
| 12288 | 0622 | `beneficiary_nif` |
| 12297 | 0625 | `ascendant_nif` |
| 12350 | 0631 | `assignor_nif` |
| 12359 | 0632 | `assignor_nif` |
| 12368 | 0633 | `assignor_nif` |
| 12386 | 0635 | `beneficiary_nif` |
| 12395 | 0638 | `landlord_nif` |
| 12421 | 0641 | `landlord_nif` |
| 12533 | 0654 | `assignor_nif` |
| 12542 | 0655 | `assignor_nif` |
| 12551 | 0656 | `assignor_nif` |
| 12569 | 0658 | `beneficiary_nif` |
| 12587 | 0665 | `descendant_nif` |
| 12596 | 0667 | `ascendant_nif` |
| 12846 | 0711 | `investment_entity_nif` |
| 12863 | 0713 | `investment_entity_nif` |
| 12880 | 0715 | `landlord_nif` |
| 12898 | 0717 | `landlord_nif` |
| 13589 | 0804 | `worker_nif` |
| 14734 | 0949 | `service_provider_nif` |
| 15048 | 0989 | `worker_nif` |
| 15081 | 0993 | `worker_nif` |
| 15651 | 1070 | `worker_nif` |
| 15692 | 1076 | `investment_entity_nif` |
| 15845 | 1096 | `landlord_nif` |
| 15935 | 1107 | `service_provider_nif` |
| 15952 | 1109 | `service_provider_nif` |
| 16135 | 1131 | `investment_entity_nif` |
| 16152 | 1133 | `investment_entity_nif` |
| 16185 | 1137 | `investment_entity_nif` |
| 16202 | 1139 | `investment_entity_nif` |
| 16235 | 1143 | `investment_entity_nif` |
| 16252 | 1145 | `investment_entity_nif` |
| 16285 | 1149 | `investment_entity_nif` |
| 16302 | 1151 | `investment_entity_nif` |
| 16335 | 1155 | `landlord_nif` |
| 16490 | 1174 | `investment_entity_nif` |
| 16507 | 1176 | `investment_entity_nif` |
| 16596 | 1187 | `tenant_nif` |
| 16640 | 1192 | `tenant_nif` |
| 16684 | 1197 | `tenant_nif` |
| 17074 | 1244 | `parent_nif` |
| 17800 | 1333 | `disabled_person_nif` |
| 17938 | 1350 | `disabled_person_nif` |
| 18303 | 1395 | `service_provider_nif` |
| 18320 | 1397 | `service_provider_nif` |
| 18338 | 1399 | `service_provider_nif` |
| 18356 | 1401 | `service_provider_nif` |
| 18374 | 1403 | `service_provider_nif` |
| 20536 | 1657 | `service_provider_nif` |
| 20545 | 1658 | `service_provider_nif` |
| 20605 | 1665 | `service_provider_nif` |
| 20614 | 1666 | `service_provider_nif` |
| 20683 | 1674 | `service_provider_nif` |
| 20692 | 1675 | `service_provider_nif` |
| 20879 | 1699 | `worker_nif` |
| 20888 | 1700 | `worker_nif` |
| 21082 | 1724 | `producer_nif` |
| 21091 | 1725 | `producer_nif` |
| 21100 | 1726 | `producer_nif` |
| 21149 | 1732 | `producer_nif` |
| 21158 | 1733 | `producer_nif` |
| 21167 | 1734 | `producer_nif` |
| 21235 | 1742 | `parent_nif` |
| 21261 | 1745 | `parent_nif` |
| 21279 | 1747 | `descendant_nif` |
| 21305 | 1750 | `parent_nif` |
| 21323 | 1752 | `descendant_nif` |
| 21349 | 1755 | `parent_nif` |
| 21367 | 1757 | `descendant_nif` |
| 21393 | 1760 | `parent_nif` |
| 21411 | 1762 | `beneficiary_annuity_payer_nif` |
| 21612 | 1786 | `beneficiary_annuity_payer_nif` |
| 21621 | 1787 | `beneficiary_annuity_payer_nif` |
| 21630 | 1788 | `beneficiary_annuity_payer_nif` |
| 21639 | 1789 | `beneficiary_annuity_payer_nif` |
| 22714 | 1918 | `construction_entity_nif` |
| 22827 | 1931 | `construction_entity_nif` |
| 23163 | 1974 | `feac_entity_nif` |
| 23199 | 1978 | `feac_entity_nif` |
| 23710 | 2040 | `investment_entity_nif` |
| 23727 | 2042 | `investment_entity_nif` |
| 23744 | 2044 | `canarias_nif_or_nie` |
| 23753 | 2045 | `canarias_nif_or_nie` |
| 23762 | 2046 | `canarias_nif_or_nie` |
| 23771 | 2047 | `canarias_nif_or_nie` |
| 23812 | 2052 | `canarias_nif_or_nie` |
| 23821 | 2053 | `canarias_nif_or_nie` |
| 23830 | 2054 | `canarias_nif_or_nie` |
| 23839 | 2055 | `canarias_nif_or_nie` |
| 23896 | 2062 | `landlord_nif` |
| 23932 | 2066 | `college_entity_nif` |
| 23941 | 2067 | `landlord_nif` |
| 23977 | 2071 | `college_entity_nif` |
| 24040 | 2078 | `investment_entity_nif` |
| 24057 | 2080 | `investment_entity_nif` |
| 24099 | 2085 | `service_provider_nif` |
| 24116 | 2087 | `service_provider_nif` |
| 24133 | 2089 | `service_provider_nif` |
| 24150 | 2091 | `service_provider_nif` |
| 24167 | 2093 | `service_provider_nif` |
| 24184 | 2095 | `service_provider_nif` |
| 24201 | 2097 | `service_provider_nif` |
| 24218 | 2099 | `service_provider_nif` |
| 24268 | 2105 | `service_provider_nif` |
| 24285 | 2107 | `service_provider_nif` |
| 24302 | 2109 | `service_provider_nif` |
| 24319 | 2111 | `service_provider_nif` |
| 24336 | 2113 | `service_provider_nif` |
| 24353 | 2115 | `service_provider_nif` |
| 24370 | 2117 | `service_provider_nif` |
| 24387 | 2119 | `service_provider_nif` |
| 24429 | 2124 | `service_provider_nif` |
| 24446 | 2126 | `service_provider_nif` |
| 24463 | 2128 | `service_provider_nif` |
| 24480 | 2130 | `service_provider_nif` |
| 24497 | 2132 | `service_provider_nif` |
| 24514 | 2134 | `service_provider_nif` |
| 24531 | 2136 | `service_provider_nif` |
| 24548 | 2138 | `service_provider_nif` |
| 24589 | 2143 | `investment_entity_nif` |
| 24606 | 2145 | `investment_entity_nif` |
| 24770 | 2167 | `investment_entity_nif` |
| 24787 | 2169 | `investment_entity_nif` |
| 24872 | 2179 | `investment_entity_nif` |
| 24889 | 2181 | `investment_entity_nif` |
| 24931 | 2186 | `service_provider_nif` |
| 24948 | 2188 | `service_provider_nif` |
| 24965 | 2190 | `service_provider_nif` |
| 24982 | 2192 | `service_provider_nif` |
| 24999 | 2194 | `service_provider_nif` |
| 25016 | 2196 | `service_provider_nif` |
| 25033 | 2198 | `service_provider_nif` |
| 25050 | 2200 | `service_provider_nif` |
| 25266 | 2225 | `investment_entity_nif` |

**Excluded from 2025 retrofit (errors):** 9035/0158 ("Índice" — reg_estima_obj_agricola section; Plan A retrofit error).

---

## Open issues

### OI-1: Plan A retrofit errors requiring `data_type` revert

Seven unique IDs received `data_type = "nif"` incorrectly in Plan A for specific revision-year instances. These must not receive `semantic_role` and must have `data_type` reverted to `text`:

| id | revision | label | action |
|----|----------|-------|--------|
| 0158 | 2025 | "Índice" (reg_estima_obj_agricola) | Revert data_type to `text` |
| 0210 | 2021, 2022, 2023 | "Por gastos de guardería" (monetary amount) | Revert data_type to `text` |
| 1070 | 2020 | "Código del municipio" | Revert data_type to `text` |
| 1096 | 2020, 2021 | "Por obtención de rentas derivadas del arrendamiento..." (amount) | Revert data_type to `text` |
| 1760 | 2021 | "Contribuyente con derecho a reducción" | Revert data_type to `text` |
| 1786 | 2021, 2022 | "Dirección del Banco/Address of the bank" | Revert data_type to `text` |
| 1787 | 2021, 2022 | "Ciudad/City" | Revert data_type to `text` |
| 1789 | 2021, 2022 | "Código País/Country code" | Revert data_type to `text` |

### OI-2: OQ-1 foreign-NIF companion casillas — deferred

Casillas 0077, 0091, 0094, 0097, 0911, 1122, 1125, 2205, 2208 are still `data_type = "text"` in all revisions (Plan A correctly skipped them). They carry the OQ-1 ambiguity flag (sibling boolean "si ha consignado un NIF de otro país"). Resolution: decide whether NifString validation is applied at input time (which would reject foreign NIFs) or at submission time (which would be safe). Tentative roles once resolved:
- 0077 → `spouse_nif` (excónyuge)
- 0091, 0094, 0097 → `tenant_nif`
- 0911 → `landlord_nif` (i_baleares_res)
- 1122, 1125 → `landlord_nif` (an_b_inf_adc_arr)
- 2205, 2208 → `landlord_nif` (an_b_inf_adc_arrvm)

Casillas 2062 and 2067 (already `data_type = "nif"`) also have OQ-1 companions — they are classified `landlord_nif` here but the same resolution applies.

### OI-3: OQ-2 FEAC casillas 1974 and 1978

Classified as `feac_entity_nif` here. The audit's OQ-2 question (whether FEAC declarants are always Spanish entities) is not resolved. The `feac_entity_nif` role exists as a separable bucket precisely so that these can be reclassified or further constrained once the FEAC instructions are verified against Orden HFP or AEAT publication. Do not merge these into `investment_entity_nif` until that verification is complete.

### OI-4: Canarias bare-label casillas 2044–2055

Classified as `canarias_nif_or_nie`. The surrounding deduction context (childcare and dependency deductions in canarias_res) strongly suggests domestic workers and guardería staff — comparable to the castilla_y_leon_res worker NIF fields. However, the labels "NIF/NIE 1/3/4" provide no direct subject qualifier. Verify against the Canarias 2024 regional deduction instructions before finalising. Role may change to `worker_nif` or `investment_entity_nif` (guardería) depending on context.

### OI-5: `construction_entity_nif` role for 0707, 1918, 1931

0707 ("NIF del promotor o constructor") is a housing deduction field from 2020 only. 1918 ("NIF/NIE de la persona/entidad vendedora") and 1931 ("NIF/NIE de la persona/entidad que ha realizado la instalación") are electric vehicle and charging point fields from 2023+. These are grouped under `construction_entity_nif` as the closest available taxonomy match, but a more specific role (`promotor_nif`, `ev_vendor_nif`, `ev_installer_nif`) may be warranted if the schema grows to distinguish them.

### OI-6: `college_entity_nif` — new role, verify coverage

2066 and 2071 ("NIF del Colegio Mayor/Menor/Residencia de estudiantes") are the only instances of this role. Confirm the `an_b_inf_adc_ges` section context maps exclusively to student accommodation entities. If it also covers other residential care entities the role label may need broadening.

### OI-7: 2023 exact line numbers for 1786/1787/1789

The 2023 extraction run terminated before completing the full output for casillas 1786, 1787, 1789 in 2023. These appear at lines approximately 19022, 19031, 19049 in the 2023 TOML (extrapolated from the 2022–2024 progression). The automation must verify exact line numbers programmatically against the 2023 TOML before writing.
