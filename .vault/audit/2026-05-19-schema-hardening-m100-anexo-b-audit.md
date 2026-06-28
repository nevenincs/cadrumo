---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-19'
modified: '2026-05-19'
related:
  - "[[2026-05-19-schema-hardening-role-taxonomy-reference]]"
  - "[[2026-05-19-schema-hardening-m100-section-inventory-audit]]"
  - "[[2026-05-19-schema-hardening-m100-nif-role-assignment-audit]]"
---

# `schema-hardening` audit: M100 `resultados.datos_adicionales_anexo_b` cluster

## Scope

Read-only classification of all casillas whose `section` places them under
`resultados.datos_adicionales_anexo_b` across six M100 revisions (2020–2025).

- 2025 revision: **230 casillas** (64 unique sub-section slots)
- Unique casilla ids across all revisions: **161**
- Already-roled (NIF roles applied in prior audit): **64 casilla-ids**
- Unroled ids classified here: **97 casilla-ids** (amounts, flags, references, text keys)

No TOML files were modified.

---

## Sub-section inventory

The cluster spans 14 named sub-sections in 2025. Earlier revisions carried fewer sub-sections
as new CCAA deduction blocks were added annually.

| sub_section | slug | first_rev | description |
|---|---|---|---|
| `an_b_inf_adc_ctrd` | ctrd | 2020 | Contrato arrendamiento — landlord NIF + amounts |
| `an_b_inf_adc_arr` | arr | 2020 | Arrendamiento (foreign-NIF variant) — landlord text + amounts |
| `an_b_inf_adc_enc` | enc | 2020 | Empresas nueva/reciente creación — entity NIF + investment amounts |
| `an_b_inf_adc_mab` | mab | 2020 | MAB (Mercado Alternativo Bursátil) — entity NIF + investment amounts |
| `an_b_inf_adc_rcf` | rcf | 2020 | Renta Canaria Fondo — entity NIF + investment amounts |
| `an_b_inf_adc_agt` | agt | 2020 | Agrupaciones empresariales — entity NIF + investment amounts |
| `an_b_inf_adc_avh` | avh | 2020 | Arrendamiento vivienda habitual — landlord NIF + amount |
| `an_b_inf_adc_ides` | ides | 2020 | Inversión deducción especial — entity NIF + investment amounts |
| `an_b_inf_adc_eps` | eps | 2020 | Primas seguro alquiler — tenant NIF + catastral refs + amounts |
| `an_b_inf_ad_ref_cat` | ref_cat | 2021 | Referencias catastrales supplementary block |
| `an_b_inf_adc_inst_auto` | inst_auto | 2021 | Instalaciones 2020–2022 carry-forward amounts |
| `an_b_inf_ad_i_baleares` | i_baleares | 2023 | I.Baleares nacimiento/adopción deduction amounts |
| `an_b_inf_adc_ges` | ges | 2024 | Gastos estudiante — landlord + catastral + college entity NIF |
| `an_b_inf_adc_vv` | vv | 2024 | Vivienda vacacional — catastral refs only |
| `an_b_inf_adc_ipse` | ipse | 2024 | Inversión PYME sector estratégico — entity NIF + amounts |
| `an_b_inf_adc_enf` | enf | 2024 | Enfermedad — contributor key + service NIF + amounts |
| `an_b_inf_adc_dep` | dep | 2024 | Dependencia — contributor key + service NIF + amounts |
| `an_b_inf_adc_aia` | aia | 2024 | Accesibilidad inmueble arrendado — contributor key + service NIF + amounts |
| `an_b_inf_adc_afp` | afp | 2024 | Acciones/fondos PYME — entity NIF + amounts |
| `an_b_inf_adc_scav` | scav | 2025 | Suscripción capital Canarias — entity NIF + amounts |
| `an_b_inf_adc_rcince` | rcince | 2025 | Rehabilitación catastral INCE — catastral + entity NIF + amounts |
| `an_b_inf_adc_aav` | aav | 2025 | Accesibilidad arrendamiento vivienda — contributor key + service NIF + amounts + carry-forward |
| `an_b_inf_adc_arrvm` | arrvm | 2025 | Arrendamiento vivienda módulos (foreign-NIF variant) — landlord text + amounts |
| `an_b_inf_ad_cm_viv_hab` | cm_viv_hab | 2025 | Cuenta-ahorro vivienda habitual — account metadata + amounts |

---

## Per-id role-assignment table

### Already-roled casilla ids (NIF audit — do not re-assign)

| id | sub_section | role | label_snippet | data_type | revisions_present |
|---|---|---|---|---|---|
| 0638 | an_b_inf_adc_ctrd | `landlord_nif` | NIF del arrendador 1 | nif | 2020–2025 |
| 0641 | an_b_inf_adc_ctrd | `landlord_nif` | NIF del arrendador 2 | nif | 2020–2025 |
| 1122 | an_b_inf_adc_arr | `landlord_or_foreign_id_nif` | NIF/NIE del arrendador 1 | text | 2020–2025 |
| 1125 | an_b_inf_adc_arr | `landlord_or_foreign_id_nif` | NIF/NIE del arrendador 2 | text | 2020–2025 |
| 1131 | an_b_inf_adc_enc | `investment_entity_nif` | NIF de la entidad 1 de nueva o reciente creación | nif | 2020–2025 |
| 1133 | an_b_inf_adc_enc | `investment_entity_nif` | NIF de la entidad 2 de nueva o reciente creación | nif | 2020–2025 |
| 1137 | an_b_inf_adc_mab | `investment_entity_nif` | NIF de la entidad 1 | nif | 2020–2025 |
| 1139 | an_b_inf_adc_mab | `investment_entity_nif` | NIF de la entidad 2 | nif | 2020–2025 |
| 1143 | an_b_inf_adc_rcf | `investment_entity_nif` | NIF de la entidad 1 | nif | 2020–2025 |
| 1145 | an_b_inf_adc_rcf | `investment_entity_nif` | NIF de la entidad 2 | nif | 2020–2025 |
| 1149 | an_b_inf_adc_agt | `investment_entity_nif` | NIF de la entidad 1 | nif | 2020–2025 |
| 1151 | an_b_inf_adc_agt | `investment_entity_nif` | NIF de la entidad 2 | nif | 2020–2025 |
| 1155 | an_b_inf_adc_avh | `landlord_nif` | NIF/NIE del arrendador | nif | 2020–2025 |
| 1174 | an_b_inf_adc_ides | `investment_entity_nif` | NIF de la entidad 1 | nif | 2020–2025 |
| 1176 | an_b_inf_adc_ides | `investment_entity_nif` | NIF de la entidad 2 | nif | 2020–2025 |
| 1187 | an_b_inf_adc_eps | `tenant_nif` | NIF/NIE del arrendatario 1 | nif | 2020–2025 |
| 1192 | an_b_inf_adc_eps | `tenant_nif` | NIF/NIE del arrendatario 2 | nif | 2020–2025 |
| 1197 | an_b_inf_adc_eps | `tenant_nif` | NIF/NIE del arrendatario 3 | nif | 2020–2025 |
| 2062 | an_b_inf_adc_ges | `landlord_nif` | NIF/NIE del arrendador 1 | nif | 2024–2025 |
| 2066 | an_b_inf_adc_ges | `college_entity_nif` | NIF del Colegio Mayor/Menor/Residencia 1 | nif | 2024–2025 |
| 2067 | an_b_inf_adc_ges | `landlord_nif` | NIF/NIE del arrendador 2 | nif | 2024–2025 |
| 2071 | an_b_inf_adc_ges | `college_entity_nif` | NIF del Colegio Mayor/Menor/Residencia 2 | nif | 2024–2025 |
| 2078 | an_b_inf_adc_ipse | `investment_entity_nif` | NIF de la entidad 1 | nif | 2024–2025 |
| 2080 | an_b_inf_adc_ipse | `investment_entity_nif` | NIF de la entidad 2 | nif | 2024–2025 |
| 2085 | an_b_inf_adc_enf | `service_provider_nif` | NIF prestador del servicio médico 1 | nif | 2024–2025 |
| 2087 | an_b_inf_adc_enf | `service_provider_nif` | NIF prestador del servicio médico 2 | nif | 2024–2025 |
| 2089 | an_b_inf_adc_enf | `service_provider_nif` | NIF prestador del servicio médico 3 | nif | 2024–2025 |
| 2091 | an_b_inf_adc_enf | `service_provider_nif` | NIF prestador del servicio médico 4 | nif | 2024–2025 |
| 2093 | an_b_inf_adc_enf | `service_provider_nif` | NIF prestador del servicio médico 5 | nif | 2024–2025 |
| 2095 | an_b_inf_adc_enf | `service_provider_nif` | NIF prestador del servicio médico 6 | nif | 2024–2025 |
| 2097 | an_b_inf_adc_enf | `service_provider_nif` | NIF prestador del servicio médico 7 | nif | 2024–2025 |
| 2099 | an_b_inf_adc_enf | `service_provider_nif` | NIF prestador del servicio médico 8 | nif | 2024–2025 |
| 2105 | an_b_inf_adc_dep | `service_provider_nif` | NIF prestador del servicio 1 | nif | 2024–2025 |
| 2107 | an_b_inf_adc_dep | `service_provider_nif` | NIF prestador del servicio 2 | nif | 2024–2025 |
| 2109 | an_b_inf_adc_dep | `service_provider_nif` | NIF prestador del servicio 3 | nif | 2024–2025 |
| 2111 | an_b_inf_adc_dep | `service_provider_nif` | NIF prestador del servicio 4 | nif | 2024–2025 |
| 2113 | an_b_inf_adc_dep | `service_provider_nif` | NIF prestador del servicio 5 | nif | 2024–2025 |
| 2115 | an_b_inf_adc_dep | `service_provider_nif` | NIF prestador del servicio 6 | nif | 2024–2025 |
| 2117 | an_b_inf_adc_dep | `service_provider_nif` | NIF prestador del servicio 7 | nif | 2024–2025 |
| 2119 | an_b_inf_adc_dep | `service_provider_nif` | NIF prestador del servicio 8 | nif | 2024–2025 |
| 2124 | an_b_inf_adc_aia | `service_provider_nif` | NIF prestador del servicio de reparación 1 | nif | 2024–2025 |
| 2126 | an_b_inf_adc_aia | `service_provider_nif` | NIF prestador del servicio de reparación 2 | nif | 2024–2025 |
| 2128 | an_b_inf_adc_aia | `service_provider_nif` | NIF prestador del servicio de reparación 3 | nif | 2024–2025 |
| 2130 | an_b_inf_adc_aia | `service_provider_nif` | NIF prestador del servicio de reparación 4 | nif | 2024–2025 |
| 2132 | an_b_inf_adc_aia | `service_provider_nif` | NIF prestador del servicio de reparación 5 | nif | 2024–2025 |
| 2134 | an_b_inf_adc_aia | `service_provider_nif` | NIF prestador del servicio de reparación 6 | nif | 2024–2025 |
| 2136 | an_b_inf_adc_aia | `service_provider_nif` | NIF prestador del servicio de reparación 7 | nif | 2024–2025 |
| 2138 | an_b_inf_adc_aia | `service_provider_nif` | NIF prestador del servicio de reparación 8 | nif | 2024–2025 |
| 2143 | an_b_inf_adc_afp | `investment_entity_nif` | NIF de la entidad 1 | nif | 2024–2025 |
| 2145 | an_b_inf_adc_afp | `investment_entity_nif` | NIF de la entidad 2 | nif | 2024–2025 |
| 2167 | an_b_inf_adc_scav | `investment_entity_nif` | NIF de la entidad 1 | nif | 2025 |
| 2169 | an_b_inf_adc_scav | `investment_entity_nif` | NIF de la entidad 2 | nif | 2025 |
| 2179 | an_b_inf_adc_rcince | `investment_entity_nif` | NIF de la entidad 1 | nif | 2025 |
| 2181 | an_b_inf_adc_rcince | `investment_entity_nif` | NIF de la entidad 2 | nif | 2025 |
| 2186 | an_b_inf_adc_aav | `service_provider_nif` | NIF prestador del servicio 1 | nif | 2025 |
| 2188 | an_b_inf_adc_aav | `service_provider_nif` | NIF prestador del servicio 2 | nif | 2025 |
| 2190 | an_b_inf_adc_aav | `service_provider_nif` | NIF prestador del servicio 3 | nif | 2025 |
| 2192 | an_b_inf_adc_aav | `service_provider_nif` | NIF prestador del servicio 4 | nif | 2025 |
| 2194 | an_b_inf_adc_aav | `service_provider_nif` | NIF prestador del servicio 5 | nif | 2025 |
| 2196 | an_b_inf_adc_aav | `service_provider_nif` | NIF prestador del servicio 6 | nif | 2025 |
| 2198 | an_b_inf_adc_aav | `service_provider_nif` | NIF prestador del servicio 7 | nif | 2025 |
| 2200 | an_b_inf_adc_aav | `service_provider_nif` | NIF prestador del servicio 8 | nif | 2025 |
| 2205 | an_b_inf_adc_arrvm | `landlord_or_foreign_id_nif` | NIF/NIE del arrendador 1 | text | 2025 |
| 2208 | an_b_inf_adc_arrvm | `landlord_or_foreign_id_nif` | NIF/NIE del arrendador 2 | text | 2025 |

---

### Unroled casilla ids — proposed roles for bulk-apply

**Role key used in this table:**

- `irpf_anexo_b_foreign_nif_flag` — boolean companion to a NIF field signalling a foreign fiscal identifier was used
- `irpf_anexo_b_catastral_ref` — catastral property reference string (Spanish Catastro ID)
- `irpf_anexo_b_no_catastral_flag` — boolean flag when no catastral reference exists
- `irpf_anexo_b_rental_amount` — amount paid per-landlord instance (cantidades satisfechas per slot)
- `irpf_anexo_b_rental_amount_total` — total of rental amounts across all slots in a sub-section
- `irpf_anexo_b_rental_deduccion_eligibility` — amounts with right to deduction (cantidades con derecho a deducción)
- `irpf_anexo_b_deduccion_autonomica` — final computed autonomic deduction amount
- `irpf_anexo_b_investment_amount` — investment amount per entity slot with right to deduction
- `irpf_anexo_b_investment_amount_total` — total of investment amounts across entity slots
- `irpf_anexo_b_service_amount` — annual amount paid per service provider slot (importe anual satisfecho)
- `irpf_anexo_b_service_amount_total` — total investment/service amounts across all provider slots
- `irpf_anexo_b_device_purchase_amount` — apparatus/device purchase amounts (enfermedad section)
- `irpf_anexo_b_insurance_premium` — insurance premium per arrendatario slot (primas satisfechas)
- `irpf_anexo_b_insurance_premium_total` — total insurance premiums across all arrendatario slots
- `irpf_anexo_b_contributor_key` — text key identifying which contributor has the deduction right (Contribuyente con derecho a deducción)
- `irpf_anexo_b_carry_forward_pending` — prior-year amount pending application in future periods
- `irpf_anexo_b_carry_forward_applied` — prior-year amount applied in current period
- `irpf_anexo_b_carry_forward_remaining` — prior-year amount remaining after current-period application
- `irpf_anexo_b_account_holder_key` — text: titular de la cuenta (savings-account block)
- `irpf_anexo_b_account_opening_date` — text: fecha de apertura de la cuenta
- `irpf_anexo_b_account_identifier` — text: identificación de la cuenta (account number / IBAN stub)
- `irpf_anexo_b_account_foreign_flag` — boolean: cuenta en entidad extranjera marker
- `irpf_anexo_b_account_balance_increase` — decimal: incremento del saldo en el ejercicio
- `irpf_anexo_b_birth_deduction_amount` — Baleares deducción por nacimiento: importe de la deducción
- `irpf_anexo_b_birth_advance_paid` — Baleares deducción por nacimiento: importe del abono anticipado
- `irpf_anexo_b_birth_pending_claim` — Baleares deducción por nacimiento: importe pendiente a solicitar
- `irpf_anexo_b_birth_advance_regularize` — Baleares: importe del cobro anticipado a regularizar
- `irpf_anexo_b_adoption_deduction_amount` — Baleares deducción por adopción: importe de la deducción
- `irpf_anexo_b_adoption_pending_claim` — Baleares deducción por adopción: importe pendiente a solicitar
- `irpf_anexo_b_other_service_amount` — otros gastos amount (aia section)
- `irpf_anexo_b_aav_amount_current` — importe total satisfecho en 2025 (aav carry-forward section)
- `irpf_anexo_b_aav_amount_applied` — importe satisfecho que se aplica en el ejercicio (aav)
- `irpf_anexo_b_aav_amount_pending` — importe satisfecho en 2025 pendiente de aplicación (aav)

| id | sub_section | proposed_role | label_snippet | data_type | revisions_present | notes |
|---|---|---|---|---|---|---|
| 0639 | an_b_inf_adc_ctrd | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [0638] NIF de otro país | boolean | 2020–2025 | OQ-1 companion to 0638 |
| 0640 | an_b_inf_adc_ctrd | `irpf_anexo_b_rental_amount` | Cantidades satisfechas | (implied decimal) | 2020–2025 | Per-slot rental amount arrendador 1 |
| 0642 | an_b_inf_adc_ctrd | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [0641] NIF de otro país | boolean | 2020–2025 | OQ-1 companion to 0641 |
| 0643 | an_b_inf_adc_ctrd | `irpf_anexo_b_rental_amount` | Cantidades satisfechas | (implied decimal) | 2020–2025 | Per-slot rental amount arrendador 2 |
| 0644 | an_b_inf_adc_ctrd | `irpf_anexo_b_rental_amount_total` | Importe total satisfecho | (implied decimal) | 2020–2025 | Sum of 0640+0643 |
| 0645 | an_b_inf_adc_ctrd | `irpf_anexo_b_rental_deduccion_eligibility` | Cantidades satisfechas con derecho a deducción | (implied decimal) | 2020–2025 | |
| 0646 | an_b_inf_adc_ctrd | `irpf_anexo_b_deduccion_autonomica` | Importe de la deducción autonómica por arrendamiento | (implied decimal) | 2020–2025 | |
| 1078 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_pending` | Importe satisfecho en 2020 pendiente de aplicación | (implied decimal) | 2021–2024 | Year-specific carry-forward; 2025 not present |
| 1115 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_pending` | Importe satisfecho en 2018 pendiente de aplicación | (implied decimal) | 2021–2022 | |
| 1116 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_applied` | Importe satisfecho en 2018 que se aplica en el ejercicio | (implied decimal) | 2021–2022 | |
| 1117 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_remaining` | Importe satisfecho en 2018 pendiente en ejercicios futuros | (implied decimal) | 2021 | |
| 1118 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_pending` | Importe satisfecho en 2022 | (implied decimal) | 2021–2022 | |
| 1119 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_applied` | Importe satisfecho que se aplica en el ejercicio | (implied decimal) | 2021–2022 | |
| 1120 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_remaining` | Importe satisfecho en 2022 pendiente en ejercicios futuros | (implied decimal) | 2021–2022 | |
| 1123 | an_b_inf_adc_arr | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [1122] NIF de otro país | boolean | 2020–2025 | OQ-1 companion to 1122 |
| 1124 | an_b_inf_adc_arr | `irpf_anexo_b_rental_amount` | Cantidades satisfechas | (implied decimal) | 2020–2025 | Per-slot arrendador 1 |
| 1126 | an_b_inf_adc_arr | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [1125] NIF de otro país | boolean | 2020–2025 | OQ-1 companion to 1125 |
| 1127 | an_b_inf_adc_arr | `irpf_anexo_b_rental_amount` | Cantidades satisfechas | (implied decimal) | 2020–2025 | Per-slot arrendador 2 |
| 1128 | an_b_inf_adc_arr | `irpf_anexo_b_rental_amount_total` | Importe total satisfecho (suma [1124]+[1127]) | (computed) | 2020–2025 | Computed sum |
| 1129 | an_b_inf_adc_arr | `irpf_anexo_b_rental_deduccion_eligibility` | Cantidades satisfechas con derecho a deducción | (implied decimal) | 2020–2025 | |
| 1130 | an_b_inf_adc_arr | `irpf_anexo_b_deduccion_autonomica` | Importe de la deducción autonómica por arrendamiento | (implied decimal) | 2020–2025 | |
| 1132 | an_b_inf_adc_enc | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 1 |
| 1134 | an_b_inf_adc_enc | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 2 |
| 1135 | an_b_inf_adc_enc | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2020–2025 | |
| 1136 | an_b_inf_adc_enc | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción por inversiones en empresas nueva/reciente creación | (implied decimal) | 2020–2025 | |
| 1138 | an_b_inf_adc_mab | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 1 |
| 1140 | an_b_inf_adc_mab | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 2 |
| 1141 | an_b_inf_adc_mab | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades con derecho a deducción | (implied decimal) | 2020–2025 | |
| 1142 | an_b_inf_adc_mab | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2020–2025 | |
| 1144 | an_b_inf_adc_rcf | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 1 |
| 1146 | an_b_inf_adc_rcf | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 2 |
| 1147 | an_b_inf_adc_rcf | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2020–2025 | |
| 1148 | an_b_inf_adc_rcf | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2020–2025 | |
| 1150 | an_b_inf_adc_agt | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 1 |
| 1152 | an_b_inf_adc_agt | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 2 |
| 1153 | an_b_inf_adc_agt | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2020–2025 | |
| 1154 | an_b_inf_adc_agt | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2020–2025 | |
| 1156 | an_b_inf_adc_avh | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [1155] NIF de otro país | boolean | 2020–2025 | OQ-1 companion to 1155 |
| 1159 | an_b_inf_adc_avh | `irpf_anexo_b_rental_amount` | Cantidades satisfechas | (implied decimal) | 2020–2025 | |
| 1170 | an_b_inf_adc_avh | `irpf_anexo_b_deduccion_autonomica` | Importe de la deducción autonómica arrendamiento vivienda habitual vinculado dación en pago | (implied decimal) | 2020–2025 | |
| 1175 | an_b_inf_adc_ides | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 1 |
| 1177 | an_b_inf_adc_ides | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2020–2025 | Per entity slot 2 |
| 1178 | an_b_inf_adc_ides | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2020–2025 | |
| 1179 | an_b_inf_adc_ides | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2020–2025 | |
| 1185 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_applied` | Importe satisfecho en 2020 que se aplica en el ejercicio | (implied decimal) | 2021–2024 | |
| 1186 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_remaining` | Importe satisfecho en 2020 pendiente en ejercicios futuros | (implied decimal) | 2021–2023 | |
| 1188 | an_b_inf_adc_eps | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [1187] NIF de otro país | boolean | 2020–2025 | OQ-1 companion to 1187 |
| 1189 | an_b_inf_adc_eps | `irpf_anexo_b_catastral_ref` | Referencia catastral 1 | text | 2020–2025 | |
| 1190 | an_b_inf_adc_eps | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2020–2025 | |
| 1191 | an_b_inf_adc_eps | `irpf_anexo_b_insurance_premium` | Primas satisfechas | (implied decimal) | 2020–2025 | Per-slot arrendatario 1 |
| 1193 | an_b_inf_adc_eps | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [1192] NIF de otro país | boolean | 2020–2025 | OQ-1 companion to 1192 |
| 1194 | an_b_inf_adc_eps | `irpf_anexo_b_catastral_ref` | Referencia catastral 2 | text | 2020–2025 | |
| 1195 | an_b_inf_adc_eps | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2020–2025 | |
| 1196 | an_b_inf_adc_eps | `irpf_anexo_b_insurance_premium` | Primas satisfechas | (implied decimal) | 2020–2025 | Per-slot arrendatario 2 |
| 1198 | an_b_inf_adc_eps | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [1197] NIF de otro país | boolean | 2020–2025 | OQ-1 companion to 1197 |
| 1199 | an_b_inf_adc_eps | `irpf_anexo_b_catastral_ref` | Referencia catastral 3 | text | 2020–2025 | |
| 1200 | an_b_inf_adc_eps | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2020–2025 | |
| 1201 | an_b_inf_adc_eps | `irpf_anexo_b_insurance_premium` | Primas satisfechas | (implied decimal) | 2020–2025 | Per-slot arrendatario 3 |
| 1202 | an_b_inf_adc_eps | `irpf_anexo_b_insurance_premium_total` | Importe total de las primas de seguro satisfechas con derecho a deducción | (implied decimal) | 2020–2025 | |
| 1203 | an_b_inf_adc_eps | `irpf_anexo_b_deduccion_autonomica` | Importe de la deducción autonómica por primas de seguros de crédito | (implied decimal) | 2020–2025 | |
| 1206 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_pending` | Importe satisfecho en 2022 | (implied decimal) | 2021–2022 | |
| 1207 | an_b_inf_ad_ref_cat | `irpf_anexo_b_catastral_ref` | Referencia catastral 1 | text | 2021–2025 | TYPE_DRIFT: absent in 2021, text in 2022+ (see hazards) |
| 1208 | an_b_inf_ad_ref_cat | `irpf_anexo_b_catastral_ref` | Referencia catastral 2 | text | 2021–2025 | TYPE_DRIFT: absent in 2021, text in 2022+ (see hazards) |
| 1392 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_pending` | Importe satisfecho en 2021 y/o 2022 pendiente de aplicación | (implied decimal) | 2022–2025 | |
| 1635 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_applied` | Importe satisfecho en 2021 y/o 2022 que se aplica en el ejercicio | (implied decimal) | 2022–2025 | |
| 1709 | an_b_inf_adc_inst_auto | `irpf_anexo_b_carry_forward_remaining` | Importe satisfecho en 2022 pendiente de aplicación en ejercicios futuros | (implied decimal) | 2022–2025 | |
| 1990 | an_b_inf_ad_i_baleares | `irpf_anexo_b_birth_deduction_amount` | Deducción por nacimiento: Importe de la deducción | (implied decimal) | 2023–2025 | |
| 1991 | an_b_inf_ad_i_baleares | `irpf_anexo_b_birth_advance_paid` | Deducción por nacimiento: Importe del abono anticipado | (implied decimal) | 2023–2025 | |
| 1992 | an_b_inf_ad_i_baleares | `irpf_anexo_b_birth_pending_claim` | Deducción por nacimiento: Importe pendiente a solicitar | (implied decimal) | 2023–2025 | |
| 1993 | an_b_inf_ad_i_baleares | `irpf_anexo_b_birth_advance_regularize` | Deducción por nacimiento: Importe del cobro anticipado a regularizar | (implied decimal) | 2023–2025 | |
| 1994 | an_b_inf_ad_i_baleares | `irpf_anexo_b_adoption_deduction_amount` | Deducción por adopción: Importe de la deducción | (implied decimal) | 2023–2025 | |
| 1995 | an_b_inf_ad_i_baleares | `irpf_anexo_b_adoption_pending_claim` | Deducción por adopción: Importe pendiente a solicitar | (implied decimal) | 2023–2025 | |
| 1996 | an_b_inf_ad_ref_cat | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2024–2025 | |
| 1997 | an_b_inf_ad_ref_cat | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2024–2025 | |
| 1998 | an_b_inf_ad_ref_cat | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2024–2025 | |
| 1999 | an_b_inf_ad_ref_cat | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2024–2025 | |
| 2000 | an_b_inf_ad_ref_cat | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2024–2025 | |
| 2001 | an_b_inf_ad_ref_cat | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2024–2025 | |
| 2063 | an_b_inf_adc_ges | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [2062] NIF de otro país | boolean | 2024–2025 | OQ-1 companion to 2062 |
| 2064 | an_b_inf_adc_ges | `irpf_anexo_b_catastral_ref` | Referencia catastral 1 | text | 2024–2025 | |
| 2065 | an_b_inf_adc_ges | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2024–2025 | |
| 2068 | an_b_inf_adc_ges | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [2067] NIF de otro país | boolean | 2024–2025 | OQ-1 companion to 2067 |
| 2069 | an_b_inf_adc_ges | `irpf_anexo_b_catastral_ref` | Referencia catastral 2 | text | 2024–2025 | |
| 2070 | an_b_inf_adc_ges | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2024–2025 | |
| 2072 | an_b_inf_adc_vv | `irpf_anexo_b_catastral_ref` | Referencia catastral 1 | text | 2024–2025 | |
| 2073 | an_b_inf_adc_vv | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2024–2025 | |
| 2074 | an_b_inf_adc_vv | `irpf_anexo_b_catastral_ref` | Referencia catastral 2 | text | 2024–2025 | |
| 2075 | an_b_inf_adc_vv | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2024–2025 | |
| 2076 | an_b_inf_adc_vv | `irpf_anexo_b_catastral_ref` | Referencia catastral 3 | text | 2024–2025 | |
| 2077 | an_b_inf_adc_vv | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2024–2025 | |
| 2079 | an_b_inf_adc_ipse | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2024–2025 | Per entity slot 1 |
| 2081 | an_b_inf_adc_ipse | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2024–2025 | Per entity slot 2 |
| 2082 | an_b_inf_adc_ipse | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2024–2025 | |
| 2083 | an_b_inf_adc_ipse | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2024–2025 | |
| 2084 | an_b_inf_adc_enf | `irpf_anexo_b_contributor_key` | Contribuyente con derecho a deducción | text | 2024–2025 | |
| 2086 | an_b_inf_adc_enf | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 1 |
| 2088 | an_b_inf_adc_enf | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 2 |
| 2090 | an_b_inf_adc_enf | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 3 |
| 2092 | an_b_inf_adc_enf | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 4 |
| 2094 | an_b_inf_adc_enf | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 5 |
| 2096 | an_b_inf_adc_enf | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 6 |
| 2098 | an_b_inf_adc_enf | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 7 |
| 2100 | an_b_inf_adc_enf | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 8 |
| 2101 | an_b_inf_adc_enf | `irpf_anexo_b_device_purchase_amount` | Importe anual por adquisición de aparatos y complementos para deficiencias físicas | (implied decimal) | 2024–2025 | |
| 2102 | an_b_inf_adc_enf | `irpf_anexo_b_service_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2024–2025 | |
| 2103 | an_b_inf_adc_enf | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2024–2025 | |
| 2104 | an_b_inf_adc_dep | `irpf_anexo_b_contributor_key` | Contribuyente con derecho a deducción | text | 2024–2025 | |
| 2106 | an_b_inf_adc_dep | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 1 |
| 2108 | an_b_inf_adc_dep | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 2 |
| 2110 | an_b_inf_adc_dep | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 3 |
| 2112 | an_b_inf_adc_dep | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 4 |
| 2114 | an_b_inf_adc_dep | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 5 |
| 2116 | an_b_inf_adc_dep | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 6 |
| 2118 | an_b_inf_adc_dep | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 7 |
| 2120 | an_b_inf_adc_dep | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 8 |
| 2121 | an_b_inf_adc_dep | `irpf_anexo_b_service_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2024–2025 | |
| 2122 | an_b_inf_adc_dep | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2024–2025 | |
| 2123 | an_b_inf_adc_aia | `irpf_anexo_b_contributor_key` | Contribuyente con derecho a deducción | text | 2024–2025 | |
| 2125 | an_b_inf_adc_aia | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 1 |
| 2127 | an_b_inf_adc_aia | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 2 |
| 2129 | an_b_inf_adc_aia | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 3 |
| 2131 | an_b_inf_adc_aia | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 4 |
| 2133 | an_b_inf_adc_aia | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 5 |
| 2135 | an_b_inf_adc_aia | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 6 |
| 2137 | an_b_inf_adc_aia | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 7 |
| 2139 | an_b_inf_adc_aia | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2024–2025 | Per provider slot 8 |
| 2140 | an_b_inf_adc_aia | `irpf_anexo_b_other_service_amount` | Importe anual satisfecho de otros gastos | (implied decimal) | 2024–2025 | |
| 2141 | an_b_inf_adc_aia | `irpf_anexo_b_service_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2024–2025 | |
| 2142 | an_b_inf_adc_aia | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2024–2025 | |
| 2144 | an_b_inf_adc_afp | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2024–2025 | Per entity slot 1 |
| 2146 | an_b_inf_adc_afp | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2024–2025 | Per entity slot 2 |
| 2147 | an_b_inf_adc_afp | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2024–2025 | |
| 2148 | an_b_inf_adc_afp | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2024–2025 | |
| 2168 | an_b_inf_adc_scav | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2025 | Per entity slot 1 |
| 2170 | an_b_inf_adc_scav | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2025 | Per entity slot 2 |
| 2171 | an_b_inf_adc_scav | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2025 | |
| 2172 | an_b_inf_adc_scav | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2025 | |
| 2173 | an_b_inf_adc_rcince | `irpf_anexo_b_catastral_ref` | Referencia catastral 1 | text | 2025 | |
| 2174 | an_b_inf_adc_rcince | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2025 | |
| 2175 | an_b_inf_adc_rcince | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2025 | Per catastral slot 1 |
| 2176 | an_b_inf_adc_rcince | `irpf_anexo_b_catastral_ref` | Referencia catastral 2 | text | 2025 | |
| 2177 | an_b_inf_adc_rcince | `irpf_anexo_b_no_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2025 | |
| 2178 | an_b_inf_adc_rcince | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2025 | Per catastral slot 2 |
| 2180 | an_b_inf_adc_rcince | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2025 | Per entity slot 1 |
| 2182 | an_b_inf_adc_rcince | `irpf_anexo_b_investment_amount` | Importe de la inversión con derecho a deducción | (implied decimal) | 2025 | Per entity slot 2 |
| 2183 | an_b_inf_adc_rcince | `irpf_anexo_b_investment_amount_total` | Importe total de las cantidades invertidas con derecho a deducción | (implied decimal) | 2025 | |
| 2184 | an_b_inf_adc_rcince | `irpf_anexo_b_deduccion_autonomica` | Importe total de la deducción | (implied decimal) | 2025 | |
| 2185 | an_b_inf_adc_aav | `irpf_anexo_b_contributor_key` | Contribuyente con derecho a deducción | text | 2025 | |
| 2187 | an_b_inf_adc_aav | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2025 | Per provider slot 1 |
| 2189 | an_b_inf_adc_aav | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2025 | Per provider slot 2 |
| 2191 | an_b_inf_adc_aav | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2025 | Per provider slot 3 |
| 2193 | an_b_inf_adc_aav | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2025 | Per provider slot 4 |
| 2195 | an_b_inf_adc_aav | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2025 | Per provider slot 5 |
| 2197 | an_b_inf_adc_aav | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2025 | Per provider slot 6 |
| 2199 | an_b_inf_adc_aav | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2025 | Per provider slot 7 |
| 2201 | an_b_inf_adc_aav | `irpf_anexo_b_service_amount` | Importe anual satisfecho | (implied decimal) | 2025 | Per provider slot 8 |
| 2202 | an_b_inf_adc_aav | `irpf_anexo_b_aav_amount_current` | Importe total satisfecho en 2025 | (implied decimal) | 2025 | |
| 2203 | an_b_inf_adc_aav | `irpf_anexo_b_aav_amount_applied` | Importe satisfecho que se aplica en el ejercicio | (implied decimal) | 2025 | |
| 2204 | an_b_inf_adc_aav | `irpf_anexo_b_aav_amount_pending` | Importe satisfecho en 2025 pendiente de aplicación en ejercicios futuros | (implied decimal) | 2025 | |
| 2206 | an_b_inf_adc_arrvm | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [2205] NIF de otro país | boolean | 2025 | OQ-1 companion to 2205 |
| 2207 | an_b_inf_adc_arrvm | `irpf_anexo_b_rental_amount` | Cantidades satisfechas | (implied decimal) | 2025 | Per-slot arrendador 1 |
| 2209 | an_b_inf_adc_arrvm | `irpf_anexo_b_foreign_nif_flag` | Marque X si casilla [2208] NIF de otro país | boolean | 2025 | OQ-1 companion to 2208 |
| 2210 | an_b_inf_adc_arrvm | `irpf_anexo_b_rental_amount` | Cantidades satisfechas | (implied decimal) | 2025 | Per-slot arrendador 2 |
| 2211 | an_b_inf_adc_arrvm | `irpf_anexo_b_rental_amount_total` | Importe total satisfecho (suma [2207]+[2210]) | (implied decimal) | 2025 | |
| 2212 | an_b_inf_adc_arrvm | `irpf_anexo_b_rental_deduccion_eligibility` | Cantidades satisfechas con derecho a deducción | (implied decimal) | 2025 | |
| 2213 | an_b_inf_adc_arrvm | `irpf_anexo_b_deduccion_autonomica` | Importe de la deducción autonómica por arrendamiento | (implied decimal) | 2025 | |
| 2214 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_holder_key` | Titular de la cuenta | text | 2025 | |
| 2215 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_opening_date` | Fecha de apertura | text | 2025 | |
| 2216 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_identifier` | Identificación de la cuenta | text | 2025 | |
| 2217 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_foreign_flag` | Marque X si cuenta en entidad extranjera | boolean | 2025 | |
| 2218 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_balance_increase` | Incremento del saldo en el ejercicio | (implied decimal) | 2025 | |
| 2219 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_holder_key` | Titular de la cuenta | text | 2025 | Slot 2 |
| 2220 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_opening_date` | Fecha de apertura | text | 2025 | Slot 2 |
| 2221 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_identifier` | Identificación de la cuenta | text | 2025 | Slot 2 |
| 2222 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_foreign_flag` | Marque X si cuenta en entidad extranjera | boolean | 2025 | Slot 2 |
| 2223 | an_b_inf_ad_cm_viv_hab | `irpf_anexo_b_account_balance_increase` | Incremento del saldo en el ejercicio | (implied decimal) | 2025 | Slot 2 |

---

## New roles introduced in this classification

These role names are not present in the canonical taxonomy reference as of 2026-05-19 and
require appending after the bulk-apply commit lands:

| role | data_type | description |
|---|---|---|
| `irpf_anexo_b_foreign_nif_flag` | boolean | OQ-1 companion boolean: NIF consignado es de otro país |
| `irpf_anexo_b_catastral_ref` | text | Referencia catastral del inmueble |
| `irpf_anexo_b_no_catastral_flag` | boolean | Marcador de ausencia de referencia catastral |
| `irpf_anexo_b_rental_amount` | decimal | Cantidades satisfechas por slot de arrendador |
| `irpf_anexo_b_rental_amount_total` | decimal | Suma de cantidades satisfechas a todos los arrendadores |
| `irpf_anexo_b_rental_deduccion_eligibility` | decimal | Cantidades satisfechas con derecho a deducción |
| `irpf_anexo_b_deduccion_autonomica` | decimal | Importe final de la deducción autonómica en el sub-section |
| `irpf_anexo_b_investment_amount` | decimal | Importe de la inversión con derecho a deducción por slot de entidad |
| `irpf_anexo_b_investment_amount_total` | decimal | Total de cantidades invertidas con derecho a deducción |
| `irpf_anexo_b_service_amount` | decimal | Importe anual satisfecho por slot de proveedor de servicio |
| `irpf_anexo_b_service_amount_total` | decimal | Total de cantidades con derecho a deducción (servicio) |
| `irpf_anexo_b_device_purchase_amount` | decimal | Importe por adquisición de aparatos para suplir deficiencias físicas |
| `irpf_anexo_b_insurance_premium` | decimal | Primas de seguro de crédito por slot de arrendatario |
| `irpf_anexo_b_insurance_premium_total` | decimal | Total de primas de seguro con derecho a deducción |
| `irpf_anexo_b_contributor_key` | text | Contribuyente con derecho a deducción (key: D=declarante/C=cónyuge/A=ambos) |
| `irpf_anexo_b_carry_forward_pending` | decimal | Importe de año anterior pendiente de aplicación |
| `irpf_anexo_b_carry_forward_applied` | decimal | Importe de año anterior aplicado en el ejercicio corriente |
| `irpf_anexo_b_carry_forward_remaining` | decimal | Importe de año anterior pendiente para ejercicios futuros |
| `irpf_anexo_b_account_holder_key` | text | Titular de cuenta ahorro vivienda habitual |
| `irpf_anexo_b_account_opening_date` | text | Fecha de apertura de cuenta ahorro vivienda habitual |
| `irpf_anexo_b_account_identifier` | text | Identificación de la cuenta (número/IBAN) |
| `irpf_anexo_b_account_foreign_flag` | boolean | Cuenta en entidad financiera extranjera |
| `irpf_anexo_b_account_balance_increase` | decimal | Incremento del saldo en el ejercicio |
| `irpf_anexo_b_birth_deduction_amount` | decimal | Baleares deducción por nacimiento: importe de la deducción |
| `irpf_anexo_b_birth_advance_paid` | decimal | Baleares: importe del abono anticipado por nacimiento |
| `irpf_anexo_b_birth_pending_claim` | decimal | Baleares: importe pendiente a solicitar (nacimiento) |
| `irpf_anexo_b_birth_advance_regularize` | decimal | Baleares: importe cobro anticipado a regularizar |
| `irpf_anexo_b_adoption_deduction_amount` | decimal | Baleares deducción por adopción: importe de la deducción |
| `irpf_anexo_b_adoption_pending_claim` | decimal | Baleares: importe pendiente a solicitar (adopción) |
| `irpf_anexo_b_other_service_amount` | decimal | Otros gastos (aia section: accesibilidad inmueble arrendado) |
| `irpf_anexo_b_aav_amount_current` | decimal | Importe total satisfecho en el ejercicio (aav carry-forward) |
| `irpf_anexo_b_aav_amount_applied` | decimal | Importe aplicado en el ejercicio (aav carry-forward) |
| `irpf_anexo_b_aav_amount_pending` | decimal | Importe pendiente de aplicación en ejercicios futuros (aav) |

**33 new roles total.**

---

## Id-reuse hazards

### Minor: 1207, 1208 — `data_type` absent in 2021, present (text) in 2022+

| id | revision | data_type | label |
|---|---|---|---|
| 1207 | 2021 | (absent) | Referencia catastral 1 |
| 1207 | 2022–2025 | text | Referencia catastral 1 |
| 1208 | 2021 | (absent) | Referencia catastral 2 |
| 1208 | 2022–2025 | text | Referencia catastral 2 |

The semantic is identical across all revisions — this is a type-completeness gap in the 2021
file, not a semantic hazard. The proposed role `irpf_anexo_b_catastral_ref` applies to all
revisions. The cross-revision validator will emit a `data_type` consistency warning for these
two ids until the 2021 TOML files are updated to declare `data_type = "text"`.

### Structural note: inst_auto carry-forward ids

Casillas 1078, 1115–1120, 1185–1186, 1206, 1392, 1635, 1709 carry year-specific labels
(e.g., "satisfecho en 2018", "en 2020", "en 2021 y/o 2022"). The label text diverges across
revisions because each year adds a new trailing-year slot and retires old ones, but the
**semantic role** (`irpf_anexo_b_carry_forward_pending`, `_applied`, `_remaining`) is stable.
The cross-revision validator keys on `semantic_role`; section-drift and label-minor-variation
are not blocked. No action needed beyond confirming role consistency.

---

## Decimal/money divergences

All monetary casillas in this cluster have `data_type` **absent** (not explicitly set to
`"decimal"` or `"money"`). This is consistent with the M100 pattern for intermediate
computation fields: the registry infers `decimal` from context. The bulk-apply pass must
infer `decimal` (not `money`) to stay consistent with existing M100 monetary casillas
(`base_imponible_irpf` precedent). No cross-role decimal/money divergence exists within
this cluster.

The only explicit `data_type` declarations in this cluster are:
- `nif` — identity fields (already roled)
- `text` — catastral refs, account text fields, contributor keys, foreign NIF (text variant)
- `boolean` — flags

All amount roles map to **implied decimal** pending explicit confirmation at bulk-apply time.

---

## Recommendations

1. **Bulk-apply pass:** Apply proposed roles to all unroled ids listed above across all
   revisions where the id is present. Use `(id, revision)` keying; no per-revision
   role splits required for this cluster (no semantic hazards detected).

2. **Fix data_type on 1207, 1208 in 2021:** Add `data_type = "text"` to both TOML files
   in the 2021 revision to close the type-completeness gap. This is a TOML fix, not a
   role decision.

3. **Append 33 new roles to taxonomy reference:** After bulk-apply commit, append the
   new-roles table above to `2026-05-19-schema-hardening-role-taxonomy-reference.md`.

4. **Typo-twin expectation:** All 33 new roles introduced here will trigger the
   single-occurrence typo-twin warning at registry load for the first revision processed.
   These warnings are expected and documented here; they resolve naturally once the
   bulk-apply covers multiple revisions.

5. **OQ-1 companion flags:** The `irpf_anexo_b_foreign_nif_flag` role is a sub-category
   of OQ-1 deferred flags documented in the taxonomy. The nine deferred OQ-1 NIFs
   (`landlord_or_foreign_id_nif`) already have their role; the boolean companion flags
   are now given `irpf_anexo_b_foreign_nif_flag`. This is semantically correct because
   these booleans have no binding or calculation significance — they are pure UI/validation
   flags that travel with the NIF field.
