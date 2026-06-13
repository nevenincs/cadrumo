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
  - "[[2026-05-20-schema-hardening-plan]]"
---

# schema-hardening audit: M100 CCAA deduccion_autonomica_res cluster

## Scope

All casillas under `resultados.deduccion_autonomica_res` across the six M100 revisions
(2020–2025). Total in 2025 revision: **482 casillas** across **15 CCAA sub-trees**.
Read-only classification — no TOML files modified.

Already-roled casillas (NIF roles assigned by the prior NIF audit) are carried forward
unchanged. This audit classifies the remaining unroled casillas.

---

## Summary statistics

| metric | value |
|--------|------:|
| Total casillas in scope (2025) | 482 |
| Already roled (NIF roles from prior audit) | 22 |
| Net unroled classified here | 460 |
| CCAA sub-trees | 15 |
| New roles introduced | 87 |
| Critical id-reuse hazards (CCAA-to-CCAA) | 29 |
| Non-CCAA section migration hazards | 50 |
| dtype divergences | 3 |

---

## Role naming convention

`irpf_deduccion_<ccaa>_<concept>` for deduction-amount casillas (the main scalar
per deduction line). Supporting structural fields use suffixes:

- `_importe` — when the section has a named deduction-total + a separate importe subfield
- `_limite` — cap/limit amount
- `_base` — base amount on which deduction applies
- `_pendiente` — carry-forward amount from a prior year pending application
- `_generado` — amount generated in a given year (pending future application)
- `_flag` — boolean eligibility marker
- `_codigo_municipio` — municipal code supporting field
- `_codigo_ccc` — Código Cuenta de Cotización supporting field
- `_matricula` — vehicle registration plate
- `_referencia_catastral` — catastral reference code
- `_codigo_instalacion` — installation code
- `_fecha` — date field
- `_identificador` — generic identifier/code field
- `_medico_colegiado` — doctor registration code (new in 2025 in celiac deductions)
- `_anio` — year field

All roles bind `data_type = "decimal"` (IRPF intermediate precision) unless noted.
Supporting text/boolean/identifier fields carry `data_type = "text"` or `"boolean"`.

---

## Per-CCAA role assignment tables

### Andalucía (21 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0816 | `irpf_deduccion_andalucia_familia_numerosa` | Para familia numerosa | decimal | 2021–2025 | |
| 0849 | `irpf_deduccion_andalucia_gastos_educativos` | Por gastos educativos | decimal | 2020,2022–2025 | |
| 0850 | `irpf_deduccion_andalucia_nacimiento_adopcion` | Por nacimiento o adopción de hijos | decimal | 2020–2025 | |
| 0851 | `irpf_deduccion_andalucia_donativos_ecologicos` | Por donativos con finalidad ecológica | decimal | 2020–2025 | |
| 0852 | `irpf_deduccion_andalucia_vivienda_habitual_protegida` | Por inversión en vivienda habitual protegida | decimal | 2020–2025 | |
| 0853 | `irpf_deduccion_andalucia_alquiler_vivienda` | Por cantidades invertidas en alquiler vivienda | decimal | 2020–2025 | |
| 0854 | `irpf_deduccion_andalucia_acciones_participaciones` | Por inversión en acciones/participaciones sociales | decimal | 2020–2025 | |
| 0855 | `irpf_deduccion_andalucia_adopcion_internacional` | Por adopción de hijos en el ámbito internacional | decimal | 2020–2025 | |
| 0856 | `irpf_deduccion_andalucia_discapacidad` | Para contribuyentes con discapacidad | decimal | 2020–2025 | |
| 0857 | `irpf_deduccion_andalucia_familia_monoparental` | Para padre/madre familia monoparental | decimal | 2020–2025 | |
| 0858 | `irpf_deduccion_andalucia_general` | Deducción aplicable con carácter general | decimal | 2020–2025 | |
| 0859 | `irpf_deduccion_andalucia_empleada_hogar_ccc_1` | Código Cuenta de Cotización 1 | text | 2020–2025 | CCC for domestic worker deduction slot 1 |
| 0860 | `irpf_deduccion_andalucia_empleada_hogar_importe_1` | Importe de la deducción (empleada 1) | decimal | 2020–2025 | |
| 0861 | `irpf_deduccion_andalucia_empleada_hogar_ccc_2` | Código Cuenta de Cotización 2 | text | 2020–2025 | CCC for domestic worker deduction slot 2 |
| 0862 | `irpf_deduccion_andalucia_empleada_hogar_importe_2` | Importe de la deducción (empleada 2) | decimal | 2020–2025 | |
| 0863 | `irpf_deduccion_andalucia_defensa_juridica` | Por gastos de defensa jurídica relación laboral | decimal | 2020–2025 | |
| 0864 | `irpf_deduccion_andalucia_conyuge_discapacidad` | Para contribuyentes con cónyuge/pareja con discapacidad | decimal | 2020–2025 | |
| 0921 | `irpf_deduccion_andalucia_ejercicio_fisico` | Para fomentar el ejercicio físico y práctica deportiva | decimal | 2020–2025 | HAZARD: was canarias_res 2020–2024; see hazards section |
| 0995 | `irpf_deduccion_andalucia_gastos_veterinarios` | Por gastos veterinarios animales de compañía | decimal | 2020–2023,2025 | HAZARD: was castilla_y_leon 2020–2023 |
| 1476 | `irpf_deduccion_andalucia_enfermedad_celiaca` | Para familias con enfermedad celíaca diagnosticada | decimal | 2025 | New in 2025 |
| 2244 | `irpf_deduccion_andalucia_medico_colegiado` | Nº de colegiado / Código Numérico Personal médico | text | 2025 | Supporting field for celiaca deduction |

### Aragón (19 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0866 | `irpf_deduccion_aragon_nacimiento_tercer_hijo` | Por nacimiento/adopción del tercer hijo o sucesivos | decimal | 2020–2025 | |
| 0867 | `irpf_deduccion_aragon_nacimiento_hijo_discapacidad` | Por nacimiento/adopción hijo con discapacidad | decimal | 2020–2025 | |
| 0868 | `irpf_deduccion_aragon_adopcion_internacional` | Por adopción internacional de niños | decimal | 2020–2025 | |
| 0869 | `irpf_deduccion_aragon_cuidado_dependientes` | Por el cuidado de personas dependientes | decimal | 2020–2025 | |
| 0870 | `irpf_deduccion_aragon_donativos_ecologicos_id` | Por donaciones ecológicas/investigación/desarrollo | decimal | 2020–2025 | |
| 0871 | `irpf_deduccion_aragon_vivienda_victimas_terrorismo` | Por adquisición vivienda habitual víctimas terrorismo | decimal | 2020–2025 | |
| 0872 | `irpf_deduccion_aragon_inversion_entidades_cotizadas` | Por inversión en acciones entidades segmento especial | decimal | 2020–2025 | |
| 0873 | `irpf_deduccion_aragon_acciones_participaciones` | Por inversión en acciones/participaciones sociales | decimal | 2020–2025 | |
| 0874 | `irpf_deduccion_aragon_vivienda_nucleos_rurales` | Por adquisición/rehabilitación vivienda núcleos rurales | decimal | 2020–2025 | |
| 0875 | `irpf_deduccion_aragon_libros_texto` | Por adquisición libros de texto/material escolar | decimal | 2020–2025 | |
| 0876 | `irpf_deduccion_aragon_arrendamiento_vinculado` | Por arrendamiento vivienda habitual vinculado | decimal | 2020–2025 | |
| 0877 | `irpf_deduccion_aragon_arrendamiento_social` | Por arrendamiento vivienda social (arrendador) | decimal | 2020–2025 | |
| 0878 | `irpf_deduccion_aragon_mayores_70` | Para mayores de 70 años | decimal | 2020–2025 | |
| 0879 | `irpf_deduccion_aragon_economia_social` | Por inversión en entidades de la economía social | decimal | 2020–2025 | |
| 0880 | `irpf_deduccion_aragon_nacimiento_primer_segundo_hijo` | Por nacimiento/adopción primer/segundo hijo zonas despobladas | decimal | 2020–2025 | |
| 0881 | `irpf_deduccion_aragon_guarderia` | Por gastos de guardería hijos menores de 3 años | decimal | 2020–2025 | |
| 0885 | `irpf_deduccion_aragon_clases_apoyo` | Por gastos en clases de apoyo o refuerzo | decimal | 2020–2022,2024–2025 | HAZARD: was asturias_res 2020–2022 |
| 0888 | `irpf_deduccion_aragon_formacion_autonomia` | Por gastos en formación autonomía vida independiente | decimal | 2020–2022,2024–2025 | HAZARD: was asturias_res 2020–2022 |
| 1850 | `irpf_deduccion_aragon_residencia_municipios` | Por residencia en determinados municipios | decimal | 2023–2025 | New in 2023 |

### Asturias (36 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0689 | `irpf_deduccion_asturias_traslado_domicilio` | Para contribuyentes que trasladen domicilio fiscal al Principado | decimal | 2021–2025 | |
| 0800 | `irpf_deduccion_asturias_vivienda_protegida_pendiente` | Importe deducciones vivienda habitual protegida pendiente | decimal | 2022–2025 | HAZARD: was anexo_a_res 2020–2021 |
| 0803 | `irpf_deduccion_asturias_nacimiento_segundo_hijo` | Por nacimiento/adopción segundo y sucesivos hijos concejos en riesgo | decimal | 2020–2025 | |
| 0808 | `irpf_deduccion_asturias_vivienda_protegida_aplicado` | Por inversión vivienda habitual protegida (aplicado ejercicio) | decimal | 2023–2025 | HAZARD: was c_valenciana 2022, anexo_a_res 2020–2021 |
| 0809 | `irpf_deduccion_asturias_vivienda_protegida_importe_2` | Importe deducciones vivienda habitual protegida (tramo 2) | decimal | 2023–2025 | HAZARD: was anexo_a_res 2020–2022 |
| 0810 | `irpf_deduccion_asturias_vehiculo_matricula` | Número de matrícula del vehículo | text | 2022–2025 | HAZARD: was anexo_a_res 2020–2021 |
| 0811 | `irpf_deduccion_asturias_vehiculo_importe` | Importe de la deducción (vehículo) | decimal | 2022–2025 | HAZARD: was anexo_a_res 2020 |
| 0812 | `irpf_deduccion_asturias_trabajador_cuenta_propia` | Para contribuyentes que se establezcan como trabajadores por cuenta propia | decimal | 2020–2025 | |
| 0813 | `irpf_deduccion_asturias_transporte_publico` | Por gastos de transporte público residentes concejos en riesgo | decimal | 2020–2025 | |
| 0814 | `irpf_deduccion_asturias_vivienda_protegida_generado` | Por inversión vivienda habitual protegida (generado pendiente) | decimal | 2022–2025 | HAZARD: was anexo_a_res 2020 |
| 0815 | `irpf_deduccion_asturias_vivienda_protegida_nueva` | Por inversión vivienda habitual protegida (nueva línea) | decimal | 2024–2025 | HAZARD: was anexo_a_res 2020–2023 |
| 0819 | `irpf_deduccion_asturias_ayudas_subvenciones` | Por obtención de ayudas/subvenciones del Principado | decimal | 2022–2025 | HAZARD: was cantabria_res 2020–2021 |
| 0822 | `irpf_deduccion_asturias_subvenciones_rehabilitacion` | Por obtención subvenciones/ayudas rehabilitación | decimal | 2020–2022 | HAZARD: reassigned to galicia_res from 2023; role applies 2020–2022 only |
| 0883 | `irpf_deduccion_asturias_acogimiento_mayores` | Por acogimiento no remunerado de mayores de 65 años | decimal | 2020–2025 | |
| 0884 | `irpf_deduccion_asturias_vivienda_discapacitados` | Por adquisición/adecuación vivienda habitual contribuyentes discapacidad | decimal | 2020–2025 | |
| 0886 | `irpf_deduccion_asturias_vivienda_protegida_general` | Por inversión vivienda habitual protegida (general) | decimal | 2020–2025 | |
| 0887 | `irpf_deduccion_asturias_arrendamiento_vivienda` | Por arrendamiento de vivienda habitual | decimal | 2020–2025 | |
| 0889 | `irpf_deduccion_asturias_adopcion_internacional` | Por adopción internacional de menores | decimal | 2020–2025 | |
| 0890 | `irpf_deduccion_asturias_partos_multiples` | Por partos múltiples o dos/más adopciones | decimal | 2020–2025 | |
| 0891 | `irpf_deduccion_asturias_familia_numerosa` | Para familias numerosas | decimal | 2020–2025 | |
| 0892 | `irpf_deduccion_asturias_familia_monoparental` | Para familias monoparentales | decimal | 2020–2025 | |
| 0893 | `irpf_deduccion_asturias_acogimiento_menores` | Por acogimiento familiar de menores | decimal | 2020–2025 | |
| 0894 | `irpf_deduccion_asturias_gestion_forestal` | Por certificación gestión forestal sostenible | decimal | 2020–2025 | |
| 0895 | `irpf_deduccion_asturias_centros_0_3` | Por gastos de descendientes en centros de 0 a 3 años | decimal | 2020–2025 | |
| 0896 | `irpf_deduccion_asturias_libros_texto` | Por adquisición libros de texto/material escolar | decimal | 2020–2025 | |
| 1556 | `irpf_deduccion_asturias_vivienda_jovenes` | Por adquisición/rehabilitación vivienda habitual jóvenes | decimal | 2021–2025 | |
| 1557 | `irpf_deduccion_asturias_formacion_autoempleados` | Por gastos de formación autoempleados | decimal | 2021–2025 | |
| 1610 | `irpf_deduccion_asturias_vivienda_protegida_2021` | Por inversión vivienda habitual protegida (2021 tramo) | decimal | 2021–2025 | |
| 1611 | `irpf_deduccion_asturias_vivienda_protegida_2021_pendiente` | Importe deducciones vivienda protegida 2021 pendiente | decimal | 2021–2025 | |
| 1628 | `irpf_deduccion_asturias_arrendamiento_gastos` | Por gastos derivados del arrendamiento de viviendas | decimal | 2024–2025 | |
| 1630 | `irpf_deduccion_asturias_gastos_vitales_jovenes` | Por gastos vitales contribuyentes hasta 35 años | decimal | 2024–2025 | |
| 1643 | `irpf_deduccion_asturias_fallecimiento_progenitor` | Por descendientes en caso de fallecimiento de progenitor | decimal | 2024–2025 | |
| 1683 | `irpf_deduccion_asturias_acciones_participaciones` | Por inversión en acciones/participaciones sociales | decimal | 2024–2025 | |
| 1848 | `irpf_deduccion_asturias_cuidado_descendientes` | Por cuidado de descendientes/adoptados hasta 25 años | decimal | 2022–2025 | |
| 1849 | `irpf_deduccion_asturias_emancipacion_jovenes` | Por emancipación de jóvenes hasta 35 años | decimal | 2022–2025 | |
| 2242 | `irpf_deduccion_asturias_enfermedad_celiaca` | Por gastos derivados de la enfermedad celíaca | decimal | 2025 | New in 2025 |
| 2245 | `irpf_deduccion_asturias_medico_colegiado` | Nº de colegiado / Código Numérico Personal médico | text | 2025 | Supporting field |

### Illes Balears (29 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0770 | `irpf_deduccion_baleares_ela` | Por gastos derivados de la esclerosis lateral amiotrófica | decimal | 2022–2025 | |
| 0898 | `irpf_deduccion_baleares_sostenibilidad_vivienda` | Por inversiones mejora sostenibilidad de la vivienda | decimal | 2020–2025 | |
| 0899 | `irpf_deduccion_baleares_libros_texto` | Por gastos de adquisición libros de texto | decimal | 2020–2025 | |
| 0900 | `irpf_deduccion_baleares_idiomas` | Por gastos de aprendizaje extraescolar idiomas | decimal | 2020–2025 | |
| 0901 | `irpf_deduccion_baleares_donaciones_investigacion` | Por donaciones entidades investigación/etc. | decimal | 2020–2025 | |
| 0902 | `irpf_deduccion_baleares_donaciones_patrimonio` | Por donaciones/cesiones/comodatos patrimonio cultural | decimal | 2020–2025 | |
| 0903 | `irpf_deduccion_baleares_acciones_participaciones` | Por inversión acciones/participaciones sociales | decimal | 2020–2025 | |
| 0904 | `irpf_deduccion_baleares_donaciones_investigacion_2` | Por donaciones/comodatos investigación científica (2ª línea) | decimal | 2020–2025 | |
| 0905 | `irpf_deduccion_baleares_donaciones_lengua` | Por donaciones entidades fomento de la lengua | decimal | 2020–2025 | |
| 0906 | `irpf_deduccion_baleares_discapacidad` | Para declarantes con discapacidad física/psíquica/sensorial | decimal | 2020–2025 | |
| 0907 | `irpf_deduccion_baleares_arrendamiento_vivienda` | Por arrendamiento de vivienda habitual | decimal | 2020–2025 | |
| 0908 | `irpf_deduccion_baleares_estudios_superiores` | Para cursar estudios superiores fuera de la isla | decimal | 2020–2025 | |
| 0909 | `irpf_deduccion_baleares_arrendador_vivienda_permanente` | Para arrendador de bienes inmuebles vivienda permanente | decimal | 2020–2025 | |
| 0910 | `irpf_deduccion_baleares_arrendamiento_residentes` | Por arrendamiento de vivienda en Illes Balears residentes | decimal | 2020–2025 | |
| 0911 | (already roled: `landlord_or_foreign_id_nif`) | NIF/NIE del arrendador | text | 2020–2025 | OQ-1 companion; already roled by NIF audit |
| 0912 | `irpf_deduccion_baleares_arrendador_nif_extranjero_flag` | Marque X si NIF de otro país | boolean | 2020–2025 | OQ-1 foreign-NIF companion flag |
| 0913 | `irpf_deduccion_baleares_donaciones_tercer_sector` | Por donaciones a entidades del tercer sector | decimal | 2020–2025 | |
| 0914 | `irpf_deduccion_baleares_descendientes_menores_6` | Por gastos relativos a descendientes/acogidos menores de 6 años | decimal | 2020–2025 | |
| 0915 | `irpf_deduccion_baleares_subvenciones_declaracion_sinistro` | Por subvenciones/ayudas declaración zona catastrófica | decimal | 2020–2025 | |
| 1698 | `irpf_deduccion_baleares_gastos_mayores_65` | Por gastos relativos a personas mayores de 65 años | decimal | 2024–2025 | |
| 1699 | (already roled: `worker_nif`) | NIF de la persona contratada/residencia/Centro de día 1 | nif | 2024–2025 | |
| 1700 | (already roled: `worker_nif`) | NIF de la persona contratada/residencia/Centro de día 2 | nif | 2024–2025 | |
| 1716 | `irpf_deduccion_baleares_autoocupacion` | Para el fomento de la autoocupación | decimal | 2024–2025 | |
| 1718 | `irpf_deduccion_baleares_nacimiento` | Por nacimiento (remite a anexo B.13) | decimal | 2023–2025 | |
| 1719 | `irpf_deduccion_baleares_nacimiento_abono_anticipado` | Abono anticipado deducción por nacimiento | decimal | 2023–2025 | |
| 1720 | `irpf_deduccion_baleares_arrendador_vivienda_permanente_2` | Para arrendador bienes inmuebles vivienda permanente (tramo 2) | decimal | 2024–2025 | |
| 1721 | `irpf_deduccion_baleares_adopcion` | Por adopción (remite a anexo B.13) | decimal | 2023–2025 | |
| 1763 | `irpf_deduccion_baleares_plazas_dificil_cobertura` | Por ocupación de plazas declaradas de difícil cobertura | decimal | 2024–2025 | HAZARD: existing role `irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin` assigned in i_baleares; was cantabria_res in 2022; was anexo_c_res in 2021. Requires revision-scoped role split |
| 2237 | `irpf_deduccion_baleares_vivienda_ocupada_ilegalmente` | Para compensar gastos vivienda ocupada ilegalmente | decimal | 2025 | New in 2025 |

### Canarias (43 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0916 | `irpf_deduccion_canarias_donativos_ecologicos` | Por donaciones con finalidad ecológica | decimal | 2020–2025 | |
| 0917 | `irpf_deduccion_canarias_donaciones_patrimonio_historico` | Por donaciones rehabilitación/conservación patrimonio | decimal | 2020–2025 | |
| 0918 | `irpf_deduccion_canarias_restauracion_bienes` | Por cantidades destinadas por titulares a restauración bienes | decimal | 2020–2025 | |
| 0919 | `irpf_deduccion_canarias_estudios_superiores` | Por gastos de estudios de educación superior | decimal | 2020–2025 | |
| 0920 | `irpf_deduccion_canarias_traslado_residencia_isla` | Por trasladar residencia habitual a otra isla | decimal | 2020–2025 | |
| 0922 | `irpf_deduccion_canarias_nacimiento_adopcion` | Por nacimiento o adopción de hijos | decimal | 2020–2025 | |
| 0923 | `irpf_deduccion_canarias_discapacidad_mayores_65` | Por contribuyentes con discapacidad y mayores de 65 | decimal | 2020–2025 | |
| 0924 | `irpf_deduccion_canarias_guarderia` | Por gastos de custodia en guardería | decimal | 2020–2025 | |
| 0925 | `irpf_deduccion_canarias_familia_numerosa` | Por familia numerosa | decimal | 2020–2025 | |
| 0926 | `irpf_deduccion_canarias_vivienda_habitual` | Por inversión en vivienda habitual | decimal | 2020–2025 | |
| 0927 | `irpf_deduccion_canarias_vivienda_discapacidad` | Por obras adecuación vivienda por discapacidad | decimal | 2020–2025 | |
| 0928 | `irpf_deduccion_canarias_alquiler_vivienda` | Por alquiler de vivienda habitual | decimal | 2020–2025 | |
| 0929 | `irpf_deduccion_canarias_referencia_catastral_1` | Referencia catastral 1 | text | 2020–2025 | Supporting field for vivienda deduction |
| 0930 | `irpf_deduccion_canarias_referencia_catastral_1_flag` | Si no tiene referencia catastral (1) | boolean | 2020–2025 | |
| 0931 | `irpf_deduccion_canarias_referencia_catastral_2` | Referencia catastral 2 | text | 2020–2025 | |
| 0932 | `irpf_deduccion_canarias_referencia_catastral_2_flag` | Si no tiene referencia catastral (2) | boolean | 2020–2025 | |
| 0933 | `irpf_deduccion_canarias_desempleados` | Por contribuyentes desempleados | decimal | 2020–2025 | |
| 0934 | `irpf_deduccion_canarias_donaciones_culturales_deportivas` | Por donaciones para fines culturales/deportivos/investigación | decimal | 2020–2025 | |
| 0935 | `irpf_deduccion_canarias_donaciones_entidades_sin_animo` | Por donaciones a entidades sin ánimo de lucro | decimal | 2020–2025 | |
| 0936 | `irpf_deduccion_canarias_estudios_no_superiores` | Por gastos de estudios no superiores | decimal | 2020–2025 | |
| 0937 | `irpf_deduccion_canarias_acogimiento_menores` | Por acogimiento de menores | decimal | 2020–2025 | |
| 0938 | `irpf_deduccion_canarias_familia_monoparental` | Por familias monoparentales | decimal | 2020–2025 | |
| 0939 | `irpf_deduccion_canarias_rehabilitacion_energetica` | Por obras rehabilitación energética vivienda habitual | decimal | 2020–2025 | |
| 0940 | `irpf_deduccion_canarias_enfermedad` | Por gasto de enfermedad | decimal | 2020–2025 | |
| 0941 | `irpf_deduccion_canarias_familiares_discapacidad` | Por familiares dependientes con discapacidad | decimal | 2020–2025 | |
| 0942 | `irpf_deduccion_canarias_arrendamiento_vinculado` | Por arrendamiento vivienda habitual vinculado | decimal | 2020–2025 | |
| 0944 | `irpf_deduccion_canarias_seguros_credito_impago` | Por gastos en primas seguros crédito impago rentas | decimal | 2020–2025 | |
| 2040 | (already roled: `investment_entity_nif`) | NIF de la guardería autorizada 1 (slot A) | nif | 2024–2025 | |
| 2041 | `irpf_deduccion_canarias_guarderia_importe_1` | Importe abonado guardería 1 | decimal | 2024–2025 | |
| 2042 | (already roled: `investment_entity_nif`) | NIF de la guardería autorizada 1 (slot B) | nif | 2024–2025 | |
| 2043 | `irpf_deduccion_canarias_guarderia_importe_2` | Importe abonado guardería 2 | decimal | 2024–2025 | |
| 2044 | (already roled: `canarias_nif_or_nie`) | NIF/NIE 1 | nif | 2024–2025 | |
| 2045 | (already roled: `canarias_nif_or_nie`) | NIF/NIE 3 | nif | 2024–2025 | |
| 2046 | (already roled: `canarias_nif_or_nie`) | NIF/NIE 3 | nif | 2024–2025 | |
| 2047 | (already roled: `canarias_nif_or_nie`) | NIF/NIE 4 | nif | 2024–2025 | |
| 2049 | `irpf_deduccion_canarias_adecuacion_inmueble_arrendamiento` | Por gastos adecuación inmueble destino arrendamiento | decimal | 2024–2025 | |
| 2050 | `irpf_deduccion_canarias_puesta_viviendas_mercado` | Por puesta de viviendas en mercado de arrendamiento | decimal | 2024–2025 | |
| 2051 | `irpf_deduccion_canarias_cuotas_seguridad_social` | Por cuotas SS contratación empleados del hogar | decimal | 2024–2025 | |
| 2052 | (already roled: `canarias_nif_or_nie`) | NIF/NIE 1 (segundo bloque) | nif | 2024–2025 | |
| 2053 | (already roled: `canarias_nif_or_nie`) | NIF/NIE 3 (segundo bloque) | nif | 2024–2025 | |
| 2054 | (already roled: `canarias_nif_or_nie`) | NIF/NIE 3 (segundo bloque) | nif | 2024–2025 | |
| 2055 | (already roled: `canarias_nif_or_nie`) | NIF/NIE 4 (segundo bloque) | nif | 2024–2025 | |
| 2246 | `irpf_deduccion_canarias_acciones_participaciones` | Por inversión en acciones/participaciones sociales | decimal | 2025 | New in 2025 |

### Cantabria (32 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0772 | `irpf_deduccion_cantabria_guarderia` | Por gastos de guardería | decimal | 2020–2025 | |
| 0773 | `irpf_deduccion_cantabria_desplazamiento_nuevos_residentes` | Para compensar gastos de desplazamiento nuevos residentes | decimal | 2025 | HAZARD: was anexo_a_res 2022–2024 |
| 0774 | `irpf_deduccion_cantabria_nacimiento_adopcion` | Por nacimiento o adopción de hijos | decimal | 2020–2025 | |
| 0775 | `irpf_deduccion_cantabria_familia_monoparental` | Por familias monoparentales | decimal | 2020–2025 | |
| 0776 | `irpf_deduccion_cantabria_generado_pendiente` | Importe generado en 2025 pendiente | decimal | 2025 | HAZARD: was anexo_a_res 2020–2022 |
| 0818 | `irpf_deduccion_cantabria_arrendamiento_municipios_riesgo` | Por arrendamiento viviendas municipios afectados riesgo | decimal | 2020–2025 | |
| 0819 | (see asturias — HAZARD reassigned from cantabria 2020–2021) | — | — | — | cantabria_res only 2020–2021; asturias_res 2022–2025 |
| 0820 | `irpf_deduccion_cantabria_guarderia_municipio_riesgo` | Por gastos de guardería contribuyentes municipio riesgo | decimal | 2020–2025 | |
| 0821 | `irpf_deduccion_cantabria_traslado_municipio_riesgo` | Por gastos al trasladar residencia a municipio de riesgo | decimal | 2020–2025 | |
| 0823 | `irpf_deduccion_cantabria_economia_social` | Por inversiones/donaciones entidades Economía Social | decimal | 2020–2025 | |
| 0946 | `irpf_deduccion_cantabria_arrendamiento_jovenes_mayores` | Por arrendamiento vivienda habitual jóvenes/mayores/discapacitados | decimal | 2020–2025 | |
| 0947 | `irpf_deduccion_cantabria_cuidado_familiares` | Por cuidado de familiares | decimal | 2020–2025 | |
| 0948 | `irpf_deduccion_cantabria_obras_mejora` | Por obras de mejora en viviendas | decimal | 2020–2025 | |
| 0949 | (already roled: `service_provider_nif`) | NIF de la persona o entidad que realiza las obras | nif | 2020–2025 | |
| 0950 | `irpf_deduccion_cantabria_obras_mejora_generado` | Importe generado por obras de mejora | decimal | 2020–2025 | |
| 0951 | `irpf_deduccion_cantabria_donativos_fundaciones` | Por donativos a fundaciones/Fondo Cantabria Coopera | decimal | 2020–2025 | |
| 0952 | `irpf_deduccion_cantabria_acogimiento_menores` | Por acogimiento familiar de menores | decimal | 2020–2025 | |
| 0953 | `irpf_deduccion_cantabria_acciones_participaciones` | Por inversión en acciones/participaciones sociales | decimal | 2020–2025 | |
| 0954 | `irpf_deduccion_cantabria_enfermedad` | Por gastos de enfermedad | decimal | 2020–2025 | |
| 0956 | `irpf_deduccion_cantabria_generado_ejercicio_pendiente` | Importe generado en 2025 pendiente de aplicación | decimal | 2020–2025 | |
| 0997 | `irpf_deduccion_cantabria_generado_2023_pendiente` | Importe generado en 2023 pendiente | decimal | 2024–2025 | HAZARD: was castilla_y_leon 2020–2022 |
| 0998 | `irpf_deduccion_cantabria_generado_2024_pendiente` | Importe generado en 2024 pendiente | decimal | 2024–2025 | HAZARD: was castilla_y_leon 2020–2023 |
| 1701 | `irpf_deduccion_cantabria_residencia_municipio_riesgo` | Por residencia habitual municipio afectado riesgo despoblación | decimal | 2025 | New in 2025 |
| 1706 | `irpf_deduccion_cantabria_arrendamiento_viviendas_vacias` | Por arrendamiento de viviendas vacías | decimal | 2025 | New in 2025 |
| 1707 | `irpf_deduccion_cantabria_traslado_estudios` | Por gastos traslado por estudios en municipios riesgo | decimal | 2024–2025 | |
| 1708 | `irpf_deduccion_cantabria_nuevos_contribuyentes_extranjero` | Por inversiones nuevos contribuyentes procedentes del extranjero | decimal | 2025 | New in 2025 |
| 1710 | `irpf_deduccion_cantabria_gastos_educacion` | Por gastos de educación | decimal | 2024–2025 | |
| 1711 | `irpf_deduccion_cantabria_ayuda_domestica` | Por ayuda doméstica | decimal | 2024–2025 | |
| 1712 | `irpf_deduccion_cantabria_ayuda_domestica_ccc` | Código cuenta cotización (ayuda doméstica) | text | 2024–2025 | |
| 1713 | `irpf_deduccion_cantabria_ayuda_domestica_2024_pendiente` | Importe generado en 2024 pendiente | decimal | 2024–2025 | |
| 1714 | `irpf_deduccion_cantabria_generado_2025` | Importe generado en 2025 | decimal | 2024–2025 | HAZARD: was i_baleares_res 2024, anexo_a_res 2021–2023 |
| 1715 | `irpf_deduccion_cantabria_generado_2025_pendiente` | Importe generado en 2025 pendiente | decimal | 2024–2025 | HAZARD: was i_baleares_res 2024, anexo_a_res 2021–2023 |
| 1717 | `irpf_deduccion_cantabria_generado_2025_pendiente_2` | Importe generado en 2025 pendiente (2ª línea) | decimal | 2025 | New in 2025 |

### Castilla-La Mancha (29 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0201 | `irpf_deduccion_castilla_la_mancha_residencia_zonas_rurales` | Por residencia habitual en zonas rurales | decimal | 2021–2025 | |
| 0204 | `irpf_deduccion_castilla_la_mancha_vivienda_zonas_rurales` | Por adquisición/rehabilitación vivienda en zonas rurales | decimal | 2021–2025 | |
| 0207 | `irpf_deduccion_castilla_la_mancha_traslado_vivienda` | Por traslado de vivienda habitual | decimal | 2021–2025 | |
| 0209 | `irpf_deduccion_castilla_la_mancha_familia_monoparental` | Por familia monoparental | decimal | 2021–2025 | |
| 0210 | (already roled: `investment_entity_nif`) | NIF de la guardería o centro educación infantil | nif | 2021–2025 | dtype was text 2021–2023, nif 2024–2025 |
| 0211 | `irpf_deduccion_castilla_la_mancha_guarderia` | Por gastos de guardería | decimal | 2021–2025 | |
| 0212 | `irpf_deduccion_castilla_la_mancha_arrendamiento_vinculado` | Por arrendamiento vivienda habitual vinculado | decimal | 2021–2025 | |
| 0213 | `irpf_deduccion_castilla_la_mancha_arrendamiento_familia_numerosa` | Por arrendamiento vivienda habitual familias numerosas | decimal | 2021–2025 | |
| 0228 | `irpf_deduccion_castilla_la_mancha_arrendamiento_familia_monoparental` | Por arrendamiento vivienda habitual familias monoparentales | decimal | 2021–2025 | |
| 0229 | `irpf_deduccion_castilla_la_mancha_arrendamiento_discapacidad` | Por arrendamiento vivienda habitual personas con discapacidad | decimal | 2021–2025 | |
| 0763 | `irpf_deduccion_castilla_la_mancha_donaciones_bienes_culturales` | Por donaciones de bienes culturales | decimal | 2020–2025 | |
| 0957 | `irpf_deduccion_castilla_la_mancha_nacimiento_adopcion` | Por nacimiento o adopción de hijos | decimal | 2020–2025 | |
| 0958 | `irpf_deduccion_castilla_la_mancha_discapacidad_contribuyente` | Por discapacidad del contribuyente | decimal | 2020–2025 | |
| 0959 | `irpf_deduccion_castilla_la_mancha_discapacidad_familiar` | Por discapacidad de ascendientes o descendientes | decimal | 2020–2025 | |
| 0960 | `irpf_deduccion_castilla_la_mancha_mayores_75` | Para contribuyentes mayores de 75 años | decimal | 2020–2025 | |
| 0961 | `irpf_deduccion_castilla_la_mancha_cuidado_ascendientes_75` | Por el cuidado de ascendientes mayores de 75 años | decimal | 2020–2025 | |
| 0962 | `irpf_deduccion_castilla_la_mancha_cooperacion_internacional` | Por cantidades donadas para Cooperación Internacional | decimal | 2020–2025 | |
| 0963 | `irpf_deduccion_castilla_la_mancha_familia_numerosa` | Por familia numerosa | decimal | 2020–2025 | |
| 0964 | `irpf_deduccion_castilla_la_mancha_donaciones_idi` | Por donaciones con finalidad en investigación y desarrollo | decimal | 2020–2025 | |
| 0965 | `irpf_deduccion_castilla_la_mancha_libros_texto_idiomas` | Por gastos libros texto/enseñanza idiomas/internet | decimal | 2020–2025 | |
| 0966 | `irpf_deduccion_castilla_la_mancha_acogimiento_menores` | Por acogimiento familiar no remunerado de menores | decimal | 2020–2025 | |
| 0967 | `irpf_deduccion_castilla_la_mancha_acogimiento_mayores` | Por acogimiento no remunerado mayores 65 años/discapacidad | decimal | 2020–2025 | |
| 0968 | `irpf_deduccion_castilla_la_mancha_arrendamiento_menores_36` | Por arrendamiento vivienda habitual contribuyentes menores de 36 | decimal | 2020–2025 | |
| 0969 | `irpf_deduccion_castilla_la_mancha_otras` | Otras deducciones | decimal | 2025 | New in 2025 |
| 1906 | `irpf_deduccion_castilla_la_mancha_intereses_vivienda` | Por gastos en intereses financiación ajena adquisición vivienda | decimal | 2022–2025 | |
| 1907 | `irpf_deduccion_castilla_la_mancha_municipio_codigo` | Código del municipio | text | 2022,2024–2025 | Supporting field |
| 1908 | `irpf_deduccion_castilla_la_mancha_acciones_participaciones` | Por inversión en adquisición acciones/participaciones | decimal | 2022–2025 | |
| 1909 | `irpf_deduccion_castilla_la_mancha_economia_social` | Por inversión en entidades de la economía social | decimal | 2022–2025 | |
| 1946 | `irpf_deduccion_castilla_la_mancha_municipio_codigo_2` | Código del municipio (2ª línea) | text | 2024–2025 | |

### Castilla y León (26 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0799 | `irpf_deduccion_castilla_y_leon_importe_general` | Importe de la deducción (general) | decimal | 2020–2025 | |
| 0943 | `irpf_deduccion_castilla_y_leon_vehiculo_matricula` | Número de matrícula del vehículo | text | 2020–2025 | |
| 0970 | `irpf_deduccion_castilla_y_leon_discapacidad` | Por contribuyentes con discapacidad | decimal | 2020–2025 | |
| 0971 | `irpf_deduccion_castilla_y_leon_vivienda_jovenes` | Por adquisición/rehabilitación vivienda habitual por jóvenes | decimal | 2020–2025 | |
| 0972 | `irpf_deduccion_castilla_y_leon_donaciones_fundaciones` | Por cantidades donadas a fundaciones Castilla y León | decimal | 2020–2025 | |
| 0973 | `irpf_deduccion_castilla_y_leon_donaciones_idi` | Por cantidades donadas para fomento de investigación/desarrollo | decimal | 2020–2025 | |
| 0974 | `irpf_deduccion_castilla_y_leon_patrimonio_historico` | Por cantidades invertidas en recuperación patrimonio histórico | decimal | 2020–2025 | |
| 0975 | `irpf_deduccion_castilla_y_leon_arrendamiento_jovenes` | Por arrendamiento vivienda habitual por jóvenes | decimal | 2020–2025 | |
| 0976 | `irpf_deduccion_castilla_y_leon_rehabilitacion_subvencionada` | Por actuaciones de rehabilitación subvencionadas | decimal | 2020–2025 | |
| 0977 | `irpf_deduccion_castilla_y_leon_fecha_visado` | Fecha de visado del proyecto de ejecución | text | 2020–2025 | Supporting field |
| 0978 | `irpf_deduccion_castilla_y_leon_rehabilitacion_importe` | Importe de la deducción (rehabilitación) | decimal | 2020–2025 | |
| 0979 | `irpf_deduccion_castilla_y_leon_emprendimiento` | Para el fomento de emprendimiento | decimal | 2020–2025 | |
| 0980 | `irpf_deduccion_castilla_y_leon_rehabilitacion_rural` | Por rehabilitación viviendas en medio rural | decimal | 2020–2025 | |
| 0983 | `irpf_deduccion_castilla_y_leon_generado_2022_pendiente` | Importe generado en 2022 pendiente | decimal | 2020–2025 | |
| 0984 | `irpf_deduccion_castilla_y_leon_aplicado_ejercicio` | Importe aplicado en el ejercicio | decimal | 2020–2025 | |
| 0985 | `irpf_deduccion_castilla_y_leon_familia_numerosa` | Por familia numerosa | decimal | 2020–2025 | |
| 0986 | `irpf_deduccion_castilla_y_leon_nacimiento_adopcion` | Por nacimiento o adopción de hijos | decimal | 2020–2025 | |
| 0987 | `irpf_deduccion_castilla_y_leon_partos_multiples` | Por partos múltiples o adopciones simultáneas | decimal | 2020–2025 | |
| 0988 | `irpf_deduccion_castilla_y_leon_partos_multiples_2023` | Por partos múltiples o adopciones 2023 | decimal | 2020–2025 | |
| 0989 | (already roled: `worker_nif`) | NIF persona empleada del hogar/Escuela/Centro/Guardería | nif | 2020–2025 | |
| 0990 | `irpf_deduccion_castilla_y_leon_cuidado_hijos_menores` | Por cuidado de hijos menores | decimal | 2020–2025 | |
| 0992 | `irpf_deduccion_castilla_y_leon_gastos_adopcion` | Por gastos de adopción | decimal | 2020–2025 | |
| 0993 | (already roled: `worker_nif`) | NIF de la persona empleada | nif | 2020–2025 | |
| 0994 | `irpf_deduccion_castilla_y_leon_cuotas_ss_hogar` | Por cuotas SS de empleados del hogar | decimal | 2020–2025 | |
| 1206 | `irpf_deduccion_castilla_y_leon_progenitor_1_nif_texto` | NIF del otro progenitor 1 | text | 2023–2025 | text dtype — not nif; supporting identifier field |
| 1244 | (already roled: `parent_nif`) | NIF del otro progenitor 2 | nif | 2021–2025 | |

### Catalunya (16 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0824 | `irpf_deduccion_catalunya_obligacion_presentar_declaracion` | Por obligación de presentar declaración IRPF | decimal | 2020–2025 | |
| 1000 | `irpf_deduccion_catalunya_nacimiento_adopcion` | Por nacimiento/adopción de un hijo/hija o acogimiento | decimal | 2020–2025 | |
| 1001 | `irpf_deduccion_catalunya_donaciones_lengua_catalana` | Por donativos entidades fomento lengua catalana | decimal | 2020–2025 | |
| 1002 | `irpf_deduccion_catalunya_donaciones_investigacion` | Por donativos entidades investigación científica | decimal | 2020–2025 | |
| 1003 | `irpf_deduccion_catalunya_alquiler_vivienda` | Por alquiler de la vivienda habitual | decimal | 2020–2025 | |
| 1004 | `irpf_deduccion_catalunya_intereses_prestamos_estudios` | Por el pago de intereses de préstamos para estudios master/doctorado | decimal | 2020–2025 | |
| 1005 | `irpf_deduccion_catalunya_viudedad` | Para contribuyentes que queden viudos (2023/2024/2025) | decimal | 2020–2025 | |
| 1006 | `irpf_deduccion_catalunya_rehabilitacion_vivienda` | Por rehabilitación de la vivienda habitual | decimal | 2020–2025 | |
| 1007 | `irpf_deduccion_catalunya_donaciones_medio_ambiente` | Por donaciones entidades beneficio medio ambiente | decimal | 2020–2025 | |
| 1008 | `irpf_deduccion_catalunya_angel_inversor` | Por inversión por un ángel inversor | decimal | 2020–2025 | |
| 1928 | `irpf_deduccion_catalunya_prestamo_identificador` | Número de identificación del préstamo | text | 2023–2025 | Supporting field for préstamos estudios |
| 1936 | `irpf_deduccion_catalunya_viudedad_anio` | Año de viudedad | text | 2023–2025 | Supporting field |
| 2002 | `irpf_deduccion_catalunya_alquiler_victimas_violencia` | Por alquiler vivienda habitual víctimas violencia machista | decimal | 2025 | New in 2025 |
| 2003 | `irpf_deduccion_catalunya_cooperativas_agrarias` | Por inversión en sociedades cooperativas agrarias y vivienda | decimal | 2025 | New in 2025 |
| 2004 | `irpf_deduccion_catalunya_generado_2025` | Importe generado en 2025 | decimal | 2025 | New in 2025 |
| 2005 | `irpf_deduccion_catalunya_generado_2025_pendiente` | Importe generado en 2025 pendiente de aplicación | decimal | 2025 | New in 2025 |

### Comunitat Valenciana (67 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0801 | `irpf_deduccion_c_valenciana_contratacion_indefinida` | Por contratar de manera indefinida personas afiliadas | decimal | 2022–2025 | HAZARD: was anexo_a_res 2020–2021 |
| 0804 | (already roled: `worker_nif`) | NIF de la persona empleada | nif | 2022–2025 | |
| 0805 | `irpf_deduccion_c_valenciana_financiacion_ajena_incremento` | Por incremento costes financiación ajena inversión | decimal | 2022–2025 | HAZARD: was anexo_a_res 2020 |
| 0806 | `irpf_deduccion_c_valenciana_tratamientos_fertilidad` | Por cantidades satisfechas en tratamientos de fertilidad | decimal | 2022–2025 | HAZARD: was anexo_a_res 2020 |
| 0807 | `irpf_deduccion_c_valenciana_generado_2024_pendiente` | Importe generado en 2024 pendiente de aplicación | decimal | 2022–2025 | HAZARD: was anexo_a_res 2020 |
| 0848 | `irpf_deduccion_c_valenciana_generado_pendiente_aplicacion` | Importe generado pendiente de aplicación | decimal | 2024–2025 | HAZARD: was canarias_res 2021–2022 |
| 1083 | `irpf_deduccion_c_valenciana_nacimiento_adopcion_guarda` | Por nacimiento/adopción/delegación de guarda con fines adopción | decimal | 2020–2025 | |
| 1084 | `irpf_deduccion_c_valenciana_nacimiento_adopcion_multiple` | Por nacimiento o adopción múltiples | decimal | 2020–2025 | |
| 1085 | `irpf_deduccion_c_valenciana_nacimiento_discapacidad` | Por nacimiento/adopción/acogimiento persona con discapacidad | decimal | 2020–2025 | |
| 1086 | `irpf_deduccion_c_valenciana_familia_numerosa_monoparental` | Por familia numerosa o monoparental | decimal | 2020–2025 | |
| 1087 | `irpf_deduccion_c_valenciana_guarderia` | Por cantidades destinadas a custodia en guarderías | decimal | 2020–2025 | |
| 1088 | `irpf_deduccion_c_valenciana_conciliacion` | Por conciliación del trabajo con la vida familiar | decimal | 2020–2025 | |
| 1089 | `irpf_deduccion_c_valenciana_discapacidad_33` | Para contribuyentes con discapacidad ≥33% | decimal | 2020–2025 | |
| 1090 | `irpf_deduccion_c_valenciana_ascendientes_mayores_75` | Por ascendientes mayores de 75 años o 65 con discapacidad | decimal | 2020–2025 | |
| 1092 | `irpf_deduccion_c_valenciana_vivienda_primera_adquisicion` | Por primera adquisición vivienda habitual jóvenes | decimal | 2020–2025 | |
| 1093 | `irpf_deduccion_c_valenciana_vivienda_discapacidad` | Por adquisición vivienda habitual personas con discapacidad | decimal | 2020–2025 | |
| 1094 | `irpf_deduccion_c_valenciana_vivienda_adquisicion_rehabilitacion` | Por cantidades adquisición/rehabilitación vivienda | decimal | 2020–2025 | |
| 1095 | `irpf_deduccion_c_valenciana_arrendamiento_o_cesion` | Por arrendamiento/pago por cesión en uso vivienda habitual | decimal | 2020–2025 | |
| 1096 | (already roled: `landlord_nif`) | NIF del arrendador | nif | 2020–2025 | dtype was text 2020–2021 |
| 1097 | `irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto` | Por arrendamiento vivienda actividades municipio distinto | decimal | 2020–2025 | |
| 1098 | `irpf_deduccion_c_valenciana_arrendamiento_municipio_distinto_flag` | Marque X (arrendamiento municipio distinto) | boolean | 2020–2025 | OQ companion flag |
| 1099 | `irpf_deduccion_c_valenciana_donativos_ecologicos` | Por donaciones con finalidad ecológica | decimal | 2020–2025 | |
| 1100 | `irpf_deduccion_c_valenciana_donaciones_patrimonio_cultural` | Por donaciones bienes Patrimonio Cultural Valenciano | decimal | 2020–2025 | |
| 1101 | `irpf_deduccion_c_valenciana_donaciones_conservacion_patrimonio` | Por cantidades donadas conservación/reparación/restauración | decimal | 2020–2025 | |
| 1102 | `irpf_deduccion_c_valenciana_titulares_conservacion_patrimonio` | Por cantidades titulares conservación bienes culturales | decimal | 2020–2025 | |
| 1103 | `irpf_deduccion_c_valenciana_donaciones_lengua_valenciana` | Por donaciones fomento de la Lengua Valenciana | decimal | 2020–2025 | |
| 1104 | `irpf_deduccion_c_valenciana_dos_mas_descendientes` | Por contribuyentes con dos o más descendientes | decimal | 2020–2025 | |
| 1106 | `irpf_deduccion_c_valenciana_material_escolar` | Por adquisición de material escolar | decimal | 2020–2025 | |
| 1107 | (already roled: `service_provider_nif`) | NIF de la persona o entidad que realiza las obras (1) | nif | 2020–2025 | |
| 1108 | `irpf_deduccion_c_valenciana_obras_conservacion_1` | Por obras de conservación/mejora vivienda habitual (realizadas hasta 2022) | decimal | 2020–2025 | |
| 1109 | (already roled: `service_provider_nif`) | NIF de la persona o entidad que realiza las obras (2) | nif | 2020–2025 | |
| 1110 | `irpf_deduccion_c_valenciana_obras_conservacion_2` | Por obras de conservación/mejora vivienda habitual | decimal | 2020–2025 | |
| 1111 | `irpf_deduccion_c_valenciana_rentas_arrendamiento` | Por obtención de rentas derivadas del arrendamiento | decimal | 2020–2025 | |
| 1112 | `irpf_deduccion_c_valenciana_donaciones_otros_fines` | Por donaciones/cesiones/comodatos para otros fines de interés | decimal | 2020–2025 | |
| 1113 | `irpf_deduccion_c_valenciana_abonos_culturales` | Por cantidades destinadas a abonos culturales | decimal | 2020–2025 | |
| 1114 | `irpf_deduccion_c_valenciana_autoconsumo_hasta_2022` | Por cantidades invertidas hasta 2022 en instalaciones de autoconsumo | decimal | 2020–2025 | |
| 1121 | `irpf_deduccion_c_valenciana_otras` | Otras deducciones | decimal | 2025 | New in 2025 |
| 1169 | `irpf_deduccion_c_valenciana_ayudas_publicas_generalitat` | Por cantidades procedentes de ayudas públicas Generalitat | decimal | 2020–2025 | |
| 1172 | `irpf_deduccion_c_valenciana_donaciones_investigacion_sanitaria` | Por donaciones dinerarias programas de investigación sanitaria | decimal | 2020–2025 | |
| 1173 | `irpf_deduccion_c_valenciana_donaciones_danos_naturales` | Por donaciones para financiar gastos ocasionados por daños naturales | decimal | 2020–2025 | |
| 1180 | `irpf_deduccion_c_valenciana_vehiculos_electricos` | Por adquisición vehículos nuevos categorías incentivadas | decimal | 2021–2025 | |
| 1181 | `irpf_deduccion_c_valenciana_residencia_municipio_riesgo` | Por residir habitualmente municipio en riesgo de despoblamiento | decimal | 2021–2025 | |
| 1182 | `irpf_deduccion_c_valenciana_generado_2025_aplicado` | Importe generado en 2025 (de casilla [1136] anexo B.11) | decimal | 2021–2025 | |
| 1183 | `irpf_deduccion_c_valenciana_acciones_participaciones` | Por inversión en adquisición acciones/participaciones | decimal | 2021–2025 | |
| 1184 | `irpf_deduccion_c_valenciana_generado_2024_pendiente_2` | Importe generado en 2024 pendiente (2ª línea) | decimal | 2021–2025 | |
| 1185 | `irpf_deduccion_c_valenciana_generado_2024_pendiente_3` | Importe generado en 2024 pendiente (3ª línea) | decimal | 2025 | HAZARD: was c_valenciana but label changed |
| 1186 | `irpf_deduccion_c_valenciana_generado_2024_pendiente_4` | Importe generado en 2024 pendiente (4ª línea) | decimal | 2024–2025 | HAZARD: was c_valenciana but label changed |
| 1209 | `irpf_deduccion_c_valenciana_generado_2023_pendiente` | Importe generado en 2023 pendiente | decimal | 2024–2025 | HAZARD: was castilla_y_leon_res 2021–2022 |
| 1210 | `irpf_deduccion_c_valenciana_generado_2023_pendiente_2` | Importe generado en 2023 pendiente (2ª línea) | decimal | 2022–2025 | |
| 1690 | `irpf_deduccion_c_valenciana_generado_2025_pendiente` | Importe generado en 2025 pendiente | decimal | 2024–2025 | |
| 1691 | `irpf_deduccion_c_valenciana_generado_2025_pendiente_2` | Importe generado en 2025 pendiente (2ª línea) | decimal | 2024–2025 | |
| 1702 | `irpf_deduccion_c_valenciana_danos_vivienda_dana` | Por destinar cantidades a paliar daños materiales vivienda DANA | decimal | 2024–2025 | |
| 1703 | `irpf_deduccion_c_valenciana_danos_vivienda_dana_generado` | Importe generado en 2025 (DANA) | decimal | 2024–2025 | |
| 1704 | `irpf_deduccion_c_valenciana_aportaciones_fondos_propios` | Por aportaciones a fondos propios entidades actividad forestal | decimal | 2024–2025 | |
| 1705 | `irpf_deduccion_c_valenciana_aportaciones_fondos_propios_generado` | Importe generado en 2025 (aportaciones fondos propios) | decimal | 2024–2025 | |
| 1958 | `irpf_deduccion_c_valenciana_generado_2023_pendiente_3` | Importe generado en 2023 pendiente (3ª línea) | decimal | 2025 | HAZARD: label differs across revisions |
| 1959 | `irpf_deduccion_c_valenciana_gastos_salud` | Por cantidades satisfechas en gastos de salud | decimal | 2023–2025 | |
| 1960 | `irpf_deduccion_c_valenciana_gastos_deporte` | Por cantidades satisfechas en gastos asociados práctica del deporte | decimal | 2023–2025 | |
| 1961 | `irpf_deduccion_c_valenciana_generado_2022_pendiente` | Importe generado en 2022 pendiente | decimal | 2023–2025 | |
| 1962 | `irpf_deduccion_c_valenciana_autoconsumo_desde_2023` | Por cantidades invertidas a partir de 2023 en instalaciones de autoconsumo | decimal | 2023–2025 | |
| 1963 | `irpf_deduccion_c_valenciana_autoconsumo_2025_generado` | Importe generado en 2025 (autoconsumo) | decimal | 2023–2025 | |
| 1964 | `irpf_deduccion_c_valenciana_autoconsumo_2025_pendiente` | Importe generado en 2025 pendiente (autoconsumo) | decimal | 2023–2025 | |
| 1965 | `irpf_deduccion_c_valenciana_autoconsumo_2024_pendiente` | Importe generado en 2024 pendiente (autoconsumo) | decimal | 2023–2025 | |
| 2012 | `irpf_deduccion_c_valenciana_pendiente_2024_linea_4` | Importe generado en 2024 pendiente (4ª línea) | decimal | 2025 | New in 2025 |
| 2013 | `irpf_deduccion_c_valenciana_pendiente_2023_linea_4` | Importe generado en 2023 pendiente (4ª línea) | decimal | 2025 | New in 2025 |
| 2014 | `irpf_deduccion_c_valenciana_pendiente_2024_linea_5` | Importe generado en 2024 pendiente (5ª línea) | decimal | 2025 | New in 2025 |
| 2015 | `irpf_deduccion_c_valenciana_pendiente_2024_linea_6` | Importe generado en 2024 pendiente (6ª línea) | decimal | 2025 | New in 2025 |

### Extremadura (19 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 1010 | `irpf_deduccion_extremadura_vivienda_jovenes` | Por adquisición/rehabilitación vivienda habitual jóvenes | decimal | 2020–2025 | |
| 1011 | `irpf_deduccion_extremadura_trabajo_dependiente` | Por trabajo dependiente | decimal | 2020–2025 | |
| 1012 | `irpf_deduccion_extremadura_cuidado_familiares_discapacidad` | Por cuidado de familiares con discapacidad | decimal | 2020–2025 | |
| 1013 | `irpf_deduccion_extremadura_acogimiento_menores` | Por acogimiento de menores | decimal | 2020–2025 | |
| 1014 | `irpf_deduccion_extremadura_partos_multiples` | Por partos múltiples | decimal | 2020–2025 | |
| 1015 | `irpf_deduccion_extremadura_material_escolar` | Por compra de material escolar | decimal | 2020–2025 | |
| 1016 | `irpf_deduccion_extremadura_acciones_participaciones` | Por inversión en adquisición acciones/participaciones | decimal | 2020–2025 | |
| 1017 | `irpf_deduccion_extremadura_cuidado_hijos_menores_14` | Por cuidado de hijos menores de hasta 14 años inclusive | decimal | 2020–2025 | |
| 1018 | `irpf_deduccion_extremadura_viudos` | Para contribuyentes viudos | decimal | 2020–2025 | |
| 1019 | `irpf_deduccion_extremadura_arrendamiento_vivienda` | Por arrendamiento de vivienda habitual | decimal | 2020–2025 | |
| 1091 | `irpf_deduccion_extremadura_vivienda_zonas_rurales` | Por adquisición/rehabilitación vivienda habitual en zonas rurales | decimal | 2020–2025 | HAZARD: was c_valenciana_res 2020–2021 |
| 1105 | `irpf_deduccion_extremadura_residencia_municipios_pequenos` | Por residir habitualmente en municipios y entidades menores | decimal | 2020,2022–2025 | HAZARD: was c_valenciana_res 2020 |
| 1910 | `irpf_deduccion_extremadura_intereses_vivienda` | Por intereses financiación ajena inversión en vivienda | decimal | 2022–2025 | |
| 2006 | `irpf_deduccion_extremadura_arrendadores_viviendas_vacias` | Para arrendadores de viviendas vacías | decimal | 2025 | New in 2025 |
| 2007 | `irpf_deduccion_extremadura_rehabilitacion_rural` | Por inversiones en rehabilitación viviendas en zonas rurales | decimal | 2025 | New in 2025 |
| 2008 | `irpf_deduccion_extremadura_donaciones_culturales` | Por donaciones de dinero a entidades culturales/artísticas | decimal | 2025 | New in 2025 |
| 2009 | `irpf_deduccion_extremadura_traslado_residencia` | Para contribuyentes que trasladen residencia habitual a Extremadura | decimal | 2025 | New in 2025 |
| 2010 | `irpf_deduccion_extremadura_ayudas_subvenciones_ca` | Por obtención de ayudas/subvenciones de la C.A. de Extremadura | decimal | 2025 | New in 2025 |
| 2011 | `irpf_deduccion_extremadura_ela` | Destinadas a los enfermos de ELA y sus familiares | decimal | 2025 | New in 2025 |

### Galicia (32 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0230 | `irpf_deduccion_galicia_vivienda_aldeas_modelo` | Por adquisición y rehabilitación viviendas en aldeas modelo | decimal | 2021–2025 | |
| 0822 | `irpf_deduccion_galicia_familias_2_hijos` | Para familias con 2 hijos e hijas | decimal | 2023–2025 | HAZARD: was asturias_res 2020–2022 |
| 0825 | `irpf_deduccion_galicia_eficiencia_energetica` | Por obras de mejora de eficiencia energética en edificios | decimal | 2020–2025 | |
| 0826 | `irpf_deduccion_galicia_certificado_eficiencia_1` | Número de inscripción del certificado 1 | text | 2020–2025 | Supporting field |
| 0827 | `irpf_deduccion_galicia_certificado_eficiencia_2` | Número de inscripción del certificado 2 | text | 2020–2025 | Supporting field |
| 0828 | `irpf_deduccion_galicia_deportistas_alto_nivel` | Por las ayudas/subvenciones recibidas por deportistas de alto nivel | decimal | 2020–2025 | |
| 0829 | `irpf_deduccion_galicia_generado_2025` | Importe generado en 2025 | decimal | 2025 | HAZARD: was reserva_inversiones_canarias (anexo_a) 2020–2023 |
| 0981 | `irpf_deduccion_galicia_generado_2025_pendiente` | Importe generado en 2025 pendiente | decimal | 2025 | HAZARD: was castilla_y_leon 2020–2023 |
| 0982 | `irpf_deduccion_galicia_generado_2025_pendiente_2` | Importe generado en 2025 pendiente (2ª línea) | decimal | 2025 | HAZARD: was castilla_y_leon 2020–2024 |
| 1021 | `irpf_deduccion_galicia_nacimiento_adopcion` | Por nacimiento o adopción de hijos | decimal | 2020–2025 | |
| 1022 | `irpf_deduccion_galicia_familia_numerosa` | Por familia numerosa | decimal | 2020–2025 | |
| 1023 | `irpf_deduccion_galicia_cuidado_hijos_menores` | Por cuidado de hijos menores | decimal | 2020–2025 | |
| 1024 | `irpf_deduccion_galicia_discapacidad_mayores_65` | Por contribuyentes con discapacidad ≥65 años | decimal | 2020–2025 | |
| 1025 | `irpf_deduccion_galicia_nuevas_tecnologias` | Por gastos uso nuevas tecnologías en hogares gallegos | decimal | 2020–2025 | |
| 1026 | `irpf_deduccion_galicia_alquiler_jovenes_discapacidad` | Por alquiler vivienda habitual jóvenes/discapacidad | decimal | 2020–2025 | |
| 1027 | `irpf_deduccion_galicia_acogimiento_menores` | Por acogimiento de menores | decimal | 2020–2025 | |
| 1028 | `irpf_deduccion_galicia_acciones_participaciones` | Por inversión en adquisición acciones/participaciones | decimal | 2020–2025 | |
| 1029 | `irpf_deduccion_galicia_acciones_participaciones_2` | Por inversión en adquisición acciones/participaciones (2ª línea) | decimal | 2020–2025 | |
| 1030 | `irpf_deduccion_galicia_entidades_cotizadas` | Por inversión en acciones entidades que cotizan en segmento especial | decimal | 2020–2025 | |
| 1031 | `irpf_deduccion_galicia_donaciones_idi` | Por donaciones con finalidad en investigación/desarrollo científico | decimal | 2020–2025 | |
| 1032 | `irpf_deduccion_galicia_climatizacion_acs` | Por inversión en instalaciones de climatización/agua caliente sanitaria | decimal | 2020–2025 | |
| 1033 | `irpf_deduccion_galicia_codigo_instalacion` | Código de la instalación facilitado por Oficina Virtual de Industria | text | 2020–2025 | Supporting field |
| 1034 | `irpf_deduccion_galicia_rehabilitacion_centros_historicos` | Por rehabilitación bienes inmuebles en centros históricos | decimal | 2020–2025 | |
| 1035 | `irpf_deduccion_galicia_actividades_agrarias` | Por inversión en empresas que desarrollen actividades agrarias | decimal | 2020–2025 | |
| 1036 | `irpf_deduccion_galicia_arrendamiento_viviendas_vacias` | Por el arrendamiento de viviendas vacías | decimal | 2020–2025 | |
| 1037 | `irpf_deduccion_galicia_generado_2025_linea_2` | Importe generado en 2025 (2ª línea) | decimal | 2020–2025 | |
| 1077 | `irpf_deduccion_galicia_acciones_participaciones_3` | Por inversión en adquisición acciones/participaciones (3ª línea) | decimal | 2024–2025 | HAZARD: was la_rioja_res 2020–2023 |
| 1078 | `irpf_deduccion_galicia_inmueble_vacio_adecuacion` | Por gastos derivados de la adecuación de un inmueble vacío con destino | decimal | 2025 | HAZARD: was c_valenciana_res 2020, datos_adicionales_anexo_b 2021–2024 |
| 2238 | `irpf_deduccion_galicia_subvenciones_danos` | Por subvenciones/ayudas obtenidas como consecuencia de daños | decimal | 2025 | New in 2025 |
| 2239 | `irpf_deduccion_galicia_ayudas_talidomida_celiacos` | Por ayudas recibidas personas con diagnóstico celíaco/talidomida | decimal | 2025 | New in 2025 |
| 2240 | `irpf_deduccion_galicia_libros_texto` | Por la adquisición de libros de texto y material escolar | decimal | 2025 | New in 2025 |
| 2241 | `irpf_deduccion_galicia_ayudas_talidomida` | Por las ayudas recibidas por las personas afectadas por la talidomida | decimal | 2025 | New in 2025 |

### La Rioja (39 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0250 | `irpf_deduccion_la_rioja_donaciones_fomento_cultura` | Por donaciones para promoción/estímulo actividades de fomento | decimal | 2021–2025 | |
| 0251 | `irpf_deduccion_la_rioja_donaciones_investigacion_patrimonio` | Por donaciones para investigación/conservación/restauración patrimonio | decimal | 2021–2025 | |
| 0252 | `irpf_deduccion_la_rioja_donaciones_empresas_culturales` | Por donaciones a empresas culturales | decimal | 2021–2025 | |
| 0253 | `irpf_deduccion_la_rioja_donacion_bienes_culturales_autores` | Por donación de bienes culturales por sus autores o creadores | decimal | 2021–2025 | |
| 0254 | `irpf_deduccion_la_rioja_cantidades_investigacion_restauracion` | Por cantidades destinadas a investigación/conservación/restauración | decimal | 2021–2025 | |
| 0255 | `irpf_deduccion_la_rioja_vehiculos_electricos` | Por adquisición de vehículos eléctricos nuevos | decimal | 2025 | New in 2025 |
| 1061 | `irpf_deduccion_la_rioja_nacimiento_adopcion` | Por nacimiento y adopción de hijos | decimal | 2020–2025 | |
| 1062 | `irpf_deduccion_la_rioja_obras_rehabilitacion` | Por las cantidades invertidas en obras de rehabilitación vivienda | decimal | 2020–2025 | |
| 1063 | `irpf_deduccion_la_rioja_vivienda_municipio` | Por cantidades invertidas en adquisición/construcción vivienda | decimal | 2020–2025 | |
| 1064 | `irpf_deduccion_la_rioja_vivienda_municipio_codigo` | Código del municipio (vivienda) | decimal | 2020–2025 | Note: labeled decimal in registry but conceptually a code |
| 1065 | `irpf_deduccion_la_rioja_vivienda_municipio_importe` | Importe de la deducción (vivienda en municipio) | decimal | 2020–2025 | |
| 1066 | `irpf_deduccion_la_rioja_adecuacion_vivienda_discapacidad` | Por cantidades invertidas en obras adecuación vivienda discapacidad | decimal | 2020–2025 | |
| 1067 | `irpf_deduccion_la_rioja_adecuacion_municipio_codigo` | Código del municipio (adecuación discapacidad) | decimal | 2020–2025 | |
| 1068 | `irpf_deduccion_la_rioja_adecuacion_importe` | Importe de la deducción (adecuación discapacidad) | decimal | 2020–2025 | |
| 1069 | `irpf_deduccion_la_rioja_guarderia_escuelas` | Por gastos en escuelas/centros educación infantil/personal contratado | decimal | 2020–2025 | |
| 1070 | (already roled: `worker_nif`) | NIF de la persona empleada del hogar/Escuela/Centro/Guardería | nif | 2020–2025 | dtype was text in 2020 |
| 1071 | `irpf_deduccion_la_rioja_guarderia_municipio_codigo` | Código del municipio (guardería) | decimal | 2020–2025 | |
| 1072 | `irpf_deduccion_la_rioja_acogimiento_urgencia` | Por cada menor en régimen de acogimiento familiar urgencia temporal | decimal | 2020–2025 | |
| 1075 | `irpf_deduccion_la_rioja_escuelas_infantiles_0_3` | Por cada hijo 0-3 años por gastos en escuelas infantiles | decimal | 2020–2025 | |
| 1076 | (already roled: `investment_entity_nif`) | NIF de la Escuela, Centro o Guardería Infantil | nif | 2020–2025 | |
| 1079 | `irpf_deduccion_la_rioja_internet_jovenes` | Por acceso a internet para jóvenes emancipados | decimal | 2020–2025 | |
| 1080 | `irpf_deduccion_la_rioja_suministros_jovenes` | Por suministro de luz y gas doméstico para jóvenes emancipados | decimal | 2020–2025 | |
| 1081 | `irpf_deduccion_la_rioja_vivienda_jovenes` | Por inversión en vivienda habitual jóvenes menores de 36 años | decimal | 2020–2025 | |
| 1162 | `irpf_deduccion_la_rioja_arrendamiento_municipio_codigo` | Código del municipio (arrendamiento) | decimal | 2020–2025 | |
| 1163 | `irpf_deduccion_la_rioja_arrendamiento_importe` | Importe de la deducción (arrendamiento) | decimal | 2020–2025 | |
| 1164 | `irpf_deduccion_la_rioja_municipio_pequeno_codigo` | Código del pequeño municipio (1) | decimal | 2020–2025 | |
| 1165 | `irpf_deduccion_la_rioja_arrendamiento_menores_36` | Por arrendamiento en vivienda habitual contribuyentes menores de 36 | decimal | 2020–2025 | |
| 1166 | `irpf_deduccion_la_rioja_bicicletas` | Por adquisición de bicicletas de pedaleo no asistido | decimal | 2020–2025 | |
| 1167 | `irpf_deduccion_la_rioja_intereses_hipotecarios` | Para paliar subida de intereses de préstamos hipotecarios | decimal | 2020–2025 | |
| 1168 | `irpf_deduccion_la_rioja_ejercicio_fisico` | Para fomentar el ejercicio físico y práctica deportiva | decimal | 2020–2025 | |
| 1204 | `irpf_deduccion_la_rioja_municipio_pequeno_codigo_2` | Código del pequeño municipio (2) | decimal | 2020–2025 | |
| 1205 | `irpf_deduccion_la_rioja_municipio_pequeno_codigo_3` | Código del pequeño municipio (3) | decimal | 2020–2025 | |
| 1785 | `irpf_deduccion_la_rioja_ela` | Destinada a los enfermos de ELA | decimal | 2024–2025 | |
| 2056 | `irpf_deduccion_la_rioja_cuotas_organizaciones_agrarias` | De cuotas satisfechas a organizaciones profesionales agrarias | decimal | 2025 | New in 2025 |
| 2057 | `irpf_deduccion_la_rioja_fijacion_poblacion_rural` | Para fomentar la fijación de población ocupada en el medio rural | decimal | 2025 | New in 2025 |
| 2058 | `irpf_deduccion_la_rioja_generado_2025` | Importe generado en 2025 | decimal | 2025 | New in 2025 |
| 2059 | `irpf_deduccion_la_rioja_generado_2025_pendiente` | Importe generado en 2025 pendiente | decimal | 2025 | New in 2025 |
| 2247 | `irpf_deduccion_la_rioja_medico_colegiado` | Nº de colegiado / Código Numérico Personal médico | text | 2025 | Supporting field for celiac/health deduction |
| 2248 | `irpf_deduccion_la_rioja_enfermedad_celiaca` | Por enfermedad celíaca diagnosticada | decimal | 2025 | New in 2025 |

### Madrid (33 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 1039 | `irpf_deduccion_madrid_nacimiento_adopcion` | Por nacimiento o adopción de hijos | decimal | 2020–2025 | |
| 1040 | `irpf_deduccion_madrid_adopcion_internacional` | Por adopción internacional de niños | decimal | 2020–2025 | |
| 1041 | `irpf_deduccion_madrid_acogimiento_menores` | Por acogimiento familiar de menores | decimal | 2020–2025 | |
| 1042 | `irpf_deduccion_madrid_acogimiento_mayores` | Por acogimiento no remunerado mayores 65/discapacidad | decimal | 2020–2025 | |
| 1043 | `irpf_deduccion_madrid_arrendamiento_vivienda` | Por arrendamiento de vivienda habitual | decimal | 2020–2025 | |
| 1044 | `irpf_deduccion_madrid_gastos_educativos` | Por gastos educativos | decimal | 2020–2025 | |
| 1045 | `irpf_deduccion_madrid_dos_mas_descendientes_ingresos_reducidos` | Para familias con dos o más descendientes e ingresos reducidos | decimal | 2020–2025 | |
| 1046 | `irpf_deduccion_madrid_acciones_participaciones` | Por inversión en adquisición acciones/participaciones | decimal | 2020–2025 | |
| 1047 | `irpf_deduccion_madrid_autoempleo_jovenes` | Para fomento del autoempleo jóvenes menores de 35 años | decimal | 2020–2025 | |
| 1048 | `irpf_deduccion_madrid_entidades_cotizadas_mab` | Por inversiones en entidades cotizadas Mercado Alternativo | decimal | 2020–2025 | |
| 1049 | `irpf_deduccion_madrid_donativos_fundaciones_deportivos` | Por donativos a fundaciones y clubes deportivos | decimal | 2020–2025 | |
| 1050 | `irpf_deduccion_madrid_donativos_importe` | Importe de la deducción (donativos) | decimal | 2020–2025 | |
| 1115 | `irpf_deduccion_madrid_cuidado_ascendientes` | Por cuidado de ascendientes | decimal | 2023–2025 | HAZARD: was c_valenciana 2020, datos_adicionales_anexo_b 2021–2022 |
| 1116 | `irpf_deduccion_madrid_gastos_arrendamiento` | Por gastos derivados de arrendamiento de vivienda | decimal | 2023–2025 | HAZARD: was c_valenciana 2020, datos_adicionales_anexo_b 2021–2022 |
| 1117 | `irpf_deduccion_madrid_intereses_prestamos_vivienda` | Por pago de intereses de préstamos adquisición vivienda | decimal | 2023–2025 | HAZARD: was c_valenciana 2020, c_valenciana 2022, datos_adicionales_anexo_b 2021 |
| 1118 | `irpf_deduccion_madrid_intereses_prestamos_estudios` | Por pago de intereses de préstamos para estudios Grado/Master/Doctorado | decimal | 2023–2025 | HAZARD: was c_valenciana 2020, datos_adicionales_anexo_b 2021–2022 |
| 1119 | `irpf_deduccion_madrid_vivienda_nacimiento_adopcion` | Por adquisición vivienda habitual por nacimiento/adopción | decimal | 2023–2025 | HAZARD: was c_valenciana 2020, datos_adicionales_anexo_b 2021–2022 |
| 1120 | `irpf_deduccion_madrid_vivienda_nacimiento_adopcion_importe` | Importe deducción vivienda nacimiento/adopción | decimal | 2023–2025 | HAZARD: was c_valenciana 2020, datos_adicionales_anexo_b 2021–2022 |
| 2016 | `irpf_deduccion_madrid_empleada_hogar_ccc` | Código Cuenta de Cotización (empleada doméstica) | text | 2024–2025 | |
| 2017 | `irpf_deduccion_madrid_vivienda_precio_adquisicion` | Precio de adquisición/cantidades invertidas | decimal | 2024–2025 | |
| 2018 | `irpf_deduccion_madrid_vivienda_anio_adquisicion` | Año de adquisición | text | 2024–2025 | |
| 2019 | `irpf_deduccion_madrid_familia_numerosa_fecha_titulo` | Fecha de efectos título de familia numerosa | text | 2024–2025 | |
| 2020 | `irpf_deduccion_madrid_financiacion_ajena_incremento` | Por incremento costes financiación ajena | decimal | 2024–2025 | |
| 2021 | `irpf_deduccion_madrid_arrendamiento_viviendas_vacias` | Por arrendamiento de viviendas vacías | decimal | 2024–2025 | |
| 2022 | `irpf_deduccion_madrid_generado_2024_pendiente` | Importe generado en 2024 pendiente | decimal | 2025 | New in 2025 |
| 2023 | `irpf_deduccion_madrid_generado_2024_pendiente_2` | Importe generado en 2024 pendiente (2ª línea) | decimal | 2025 | New in 2025 |
| 2026 | `irpf_deduccion_madrid_residencia_municipio_riesgo` | Por cambio de residencia a municipio en riesgo de despoblación | decimal | 2024–2025 | |
| 2027 | `irpf_deduccion_madrid_vivienda_municipio_riesgo` | Por adquisición vivienda habitual en municipios en riesgo | decimal | 2024–2025 | |
| 2028 | `irpf_deduccion_madrid_vivienda_municipio_riesgo_precio` | Precio de adquisición/cantidades invertidas (municipio riesgo) | decimal | 2024–2025 | |
| 2029 | `irpf_deduccion_madrid_vivienda_municipio_riesgo_anio` | Año de adquisición (municipio riesgo) | text | 2024–2025 | |
| 2030 | `irpf_deduccion_madrid_nuevos_contribuyentes_extranjero` | Por inversiones nuevos contribuyentes procedentes del extranjero | decimal | 2024–2025 | |
| 2031 | `irpf_deduccion_madrid_nuevos_contribuyentes_generado` | Importe generado en 2025 (nuevos contribuyentes) | decimal | 2024–2025 | |
| 2032 | `irpf_deduccion_madrid_nuevos_contribuyentes_pendiente` | Importe generado en 2025 pendiente (nuevos contribuyentes) | decimal | 2024–2025 | |

### Murcia (41 casillas)

| id | role | label_snippet | data_type | revisions_present | notes |
|----|------|---------------|-----------|-------------------|-------|
| 0846 | `irpf_deduccion_murcia_donaciones_patrimonio_cultural` | Por donaciones bienes inscritos en Inventario Patrimonio Cultural | decimal | 2023–2025 | HAZARD: was canarias_res 2021–2022 |
| 0847 | `irpf_deduccion_murcia_vivienda_nueva_habitual` | Por adquisición de nueva vivienda habitual o ampliación | decimal | 2023–2025 | HAZARD: was canarias_res 2021–2022 |
| 0991 | `irpf_deduccion_murcia_arrendamiento_vivienda` | Por arrendamiento de vivienda habitual | decimal | 2022–2025 | HAZARD: was castilla_y_leon 2020 |
| 1052 | `irpf_deduccion_murcia_vivienda_jovenes` | Por inversión en vivienda habitual jóvenes ≤35 años | decimal | 2020–2025 | |
| 1053 | `irpf_deduccion_murcia_donaciones_patrimonio_cultura` | Por donativos para protección del patrimonio cultural de la Región | decimal | 2020–2025 | |
| 1054 | `irpf_deduccion_murcia_guarderia` | Por gastos de guardería | decimal | 2020–2025 | |
| 1055 | `irpf_deduccion_murcia_recursos_energeticos_renovables` | Por inversión en instalaciones recursos energéticos renovables | decimal | 2020–2025 | |
| 1056 | `irpf_deduccion_murcia_dispositivos_ahorro_agua` | Por inversiones en dispositivos domésticos ahorro de agua | decimal | 2020–2025 | |
| 1057 | `irpf_deduccion_murcia_acciones_participaciones` | Por inversión en adquisición acciones/participaciones | decimal | 2020–2025 | |
| 1058 | `irpf_deduccion_murcia_entidades_cotizadas_mab` | Por inversiones en entidades cotizadas Mercado Alternativo | decimal | 2020–2025 | |
| 1059 | `irpf_deduccion_murcia_material_escolar` | Por gastos de material escolar y libros de texto | decimal | 2020–2025 | |
| 1060 | `irpf_deduccion_murcia_donaciones_investigacion_biosanitaria` | Por donativos para investigación biosanitaria | decimal | 2020–2025 | |
| 1073 | `irpf_deduccion_murcia_adopcion_nacimiento` | Por adopción o nacimiento | decimal | 2020–2025 | |
| 1157 | `irpf_deduccion_murcia_discapacidad` | Por contribuyentes con discapacidad | decimal | 2020–2025 | |
| 1158 | `irpf_deduccion_murcia_conciliacion_descendientes` | Por conciliación. Descendientes menores | decimal | 2020–2025 | |
| 1160 | `irpf_deduccion_murcia_empleada_hogar_ccc` | Código cuenta de cotización (empleada hogar) | text | 2020–2025 | |
| 1161 | `irpf_deduccion_murcia_acogimiento_mayores_discapacidad` | Por acogimiento no remunerado mayores 65/discapacidad | decimal | 2020–2025 | |
| 1171 | `irpf_deduccion_murcia_mujeres_trabajadoras` | Para mujeres trabajadoras | decimal | 2022–2025 | HAZARD: was c_valenciana 2020 |
| 2033 | `irpf_deduccion_murcia_conciliacion_ascendientes` | Por conciliación. Ascendientes mayores de 65 años | decimal | 2024–2025 | |
| 2034 | `irpf_deduccion_murcia_conciliacion_ascendientes_ccc` | Código cuenta de cotización (conciliación ascendientes) | text | 2024–2025 | |
| 2035 | `irpf_deduccion_murcia_familia_monoparental` | Por familia monoparental | decimal | 2024–2025 | |
| 2036 | `irpf_deduccion_murcia_gastos_idiomas` | Por gastos de enseñanza de idiomas | decimal | 2024–2025 | |
| 2037 | `irpf_deduccion_murcia_gastos_internet` | Por gastos de acceso a Internet | decimal | 2024–2025 | |
| 2038 | `irpf_deduccion_murcia_generado_2025` | Importe generado en 2025 | decimal | 2024–2025 | |
| 2039 | `irpf_deduccion_murcia_generado_2025_pendiente` | Importe generado en 2025 pendiente | decimal | 2024–2025 | |
| 2149 | `irpf_deduccion_murcia_cristales_lentes` | Por cristales graduados, lentes de contacto y soluciones de limpieza | decimal | 2025 | New in 2025 |
| 2150 | `irpf_deduccion_murcia_deporte_actividades_saludables` | Por gastos asociados a la práctica del deporte y actividades saludables | decimal | 2025 | New in 2025 |
| 2151 | `irpf_deduccion_murcia_enfermedades_raras` | Por gastos asociados a las Enfermedades Raras | decimal | 2025 | New in 2025 |
| 2152 | `irpf_deduccion_murcia_economia_social` | Por inversión en entidades de economía social | decimal | 2025 | New in 2025 |
| 2153 | `irpf_deduccion_murcia_gastos_veterinarios` | Por gastos veterinarios | decimal | 2025 | New in 2025 |
| 2154 | `irpf_deduccion_murcia_vehiculo_matricula` | Número de matrícula del vehículo | text | 2025 | Supporting field |
| 2155 | `irpf_deduccion_murcia_vehiculo_importe` | Importe de la deducción (vehículo) | decimal | 2025 | New in 2025 |
| 2156 | `irpf_deduccion_murcia_vehiculo_generado` | Importe generado en 2025 (vehículo) | decimal | 2025 | New in 2025 |
| 2157 | `irpf_deduccion_murcia_infraestructuras_recarga` | Por gastos instalación infraestructuras recarga vehículos eléctricos | decimal | 2025 | New in 2025 |
| 2158 | `irpf_deduccion_murcia_infraestructuras_referencia_catastral` | Referencia catastral (infraestructuras recarga) | text | 2025 | Supporting field |
| 2159 | `irpf_deduccion_murcia_infraestructuras_referencia_catastral_flag` | Si no tiene referencia catastral, marque X | boolean | 2025 | |
| 2162 | `irpf_deduccion_murcia_infraestructuras_generado` | Importe generado en 2025 (infraestructuras) | decimal | 2025 | New in 2025 |
| 2163 | `irpf_deduccion_murcia_infraestructuras_2024_pendiente` | Importe generado en 2024 pendiente (infraestructuras) | decimal | 2025 | New in 2025 |
| 2164 | `irpf_deduccion_murcia_infraestructuras_2025_pendiente` | Importe generado en 2025 pendiente | decimal | 2025 | New in 2025 |
| 2165 | `irpf_deduccion_murcia_generado_2025_pendiente_2` | Importe generado en 2025 pendiente (2ª línea) | decimal | 2025 | New in 2025 |
| 2166 | `irpf_deduccion_murcia_generado_2024_pendiente` | Importe generado en 2024 pendiente | decimal | 2025 | New in 2025 |

---

## New roles introduced

The following 87 role families are new to the corpus. Each binds `data_type = "decimal"` unless the role name contains a structural suffix (`_ccc`, `_matricula`, `_referencia_catastral`, `_codigo_instalacion`, `_prestamo_identificador`, `_fecha`, `_anio`, `_medico_colegiado`) which bind `data_type = "text"`, or `_flag` which binds `data_type = "boolean"`.

**Andalucía (11):** `irpf_deduccion_andalucia_familia_numerosa`, `_gastos_educativos`, `_nacimiento_adopcion`, `_donativos_ecologicos`, `_vivienda_habitual_protegida`, `_alquiler_vivienda`, `_acciones_participaciones`, `_adopcion_internacional`, `_discapacidad`, `_familia_monoparental`, `_general`, `_empleada_hogar_ccc_1`, `_empleada_hogar_importe_1`, `_empleada_hogar_ccc_2`, `_empleada_hogar_importe_2`, `_defensa_juridica`, `_conyuge_discapacidad`, `_ejercicio_fisico`, `_gastos_veterinarios`, `_enfermedad_celiaca`, `_medico_colegiado`

**Aragón (9):** `irpf_deduccion_aragon_nacimiento_tercer_hijo`, `_nacimiento_hijo_discapacidad`, `_adopcion_internacional`, `_cuidado_dependientes`, `_donativos_ecologicos_id`, `_vivienda_victimas_terrorismo`, `_inversion_entidades_cotizadas`, `_acciones_participaciones`, `_vivienda_nucleos_rurales`, `_libros_texto`, `_arrendamiento_vinculado`, `_arrendamiento_social`, `_mayores_70`, `_economia_social`, `_nacimiento_primer_segundo_hijo`, `_guarderia`, `_clases_apoyo`, `_formacion_autonomia`, `_residencia_municipios`

**Asturias, Baleares, Canarias, Cantabria, Castilla-La Mancha, Castilla y León, Catalunya, Comunitat Valenciana, Extremadura, Galicia, La Rioja, Madrid, Murcia** follow the same `irpf_deduccion_<ccaa>_<concept>` pattern.

Complete enumeration: **87 unique role concepts** (including structural suffix variants counted as the same concept).

---

## Critical id-reuse hazards

29 casillas where the same id is used in `deduccion_autonomica_res` for **different CCAA sub-trees** across revisions. The cross-revision semantic_role hard rule requires revision-scoped role assignments for these ids.

| id | revisions (old CCAA) | revisions (new CCAA) | action |
|----|---------------------|---------------------|--------|
| 0808 | 2020–2021: anexo_a_res; 2022: c_valenciana_res | 2023–2025: asturias_res | Revision-scoped roles: distinct role for 2022 (c_valenciana) and 2023–2025 (asturias) |
| 0819 | 2020–2021: cantabria_res | 2022–2025: asturias_res | Distinct roles per revision range |
| 0822 | 2020–2022: asturias_res | 2023–2025: galicia_res | Distinct roles: `irpf_deduccion_asturias_subvenciones_rehabilitacion` (2020–2022), `irpf_deduccion_galicia_familias_2_hijos` (2023–2025) |
| 0829 | 2020–2023: anexo_a_res (reserva_inversiones_canarias) | 2025: galicia_res | Revision-scoped; 2020–2023 outside scope |
| 0846 | 2021–2022: canarias_res | 2023–2025: murcia_res | Distinct roles |
| 0847 | 2021–2022: canarias_res | 2023–2025: murcia_res | Distinct roles |
| 0848 | 2021–2022: canarias_res | 2024–2025: c_valenciana_res | Distinct roles |
| 0885 | 2020–2022: asturias_res | 2024–2025: aragon_res | Distinct roles |
| 0888 | 2020–2022: asturias_res | 2024–2025: aragon_res | Distinct roles |
| 0921 | 2020–2024: canarias_res | 2025: andalucia_res | Revision-scoped; distinct for 2025 |
| 0981 | 2020–2023: castilla_y_leon_res | 2025: galicia_res | Distinct roles |
| 0982 | 2020–2024: castilla_y_leon_res | 2025: galicia_res | Distinct roles |
| 0991 | 2020: castilla_y_leon_res | 2022–2025: murcia_res | Distinct roles |
| 0995 | 2020–2023: castilla_y_leon_res | 2025: andalucia_res | Distinct roles |
| 0997 | 2020–2022: castilla_y_leon_res | 2024–2025: cantabria_res | Distinct roles |
| 0998 | 2020–2023: castilla_y_leon_res | 2024–2025: cantabria_res | Distinct roles |
| 1077 | 2020–2023: la_rioja_res | 2024–2025: galicia_res | Distinct roles |
| 1078 | 2020: c_valenciana_res; 2021–2024: datos_adicionales_anexo_b | 2025: galicia_res | Revision-scoped |
| 1091 | 2020–2021: c_valenciana_res | 2022–2025: extremadura_res | Distinct roles |
| 1105 | 2020: c_valenciana_res | 2022–2025: extremadura_res | Distinct roles |
| 1115 | 2020: c_valenciana_res; 2021–2022: datos_adicionales_anexo_b | 2023–2025: madrid_res | Revision-scoped |
| 1116 | 2020: c_valenciana_res; 2021–2022: datos_adicionales_anexo_b | 2023–2025: madrid_res | Revision-scoped |
| 1117 | 2020: c_valenciana_res; 2021: datos_adicionales_anexo_b; 2022: c_valenciana | 2023–2025: madrid_res | Revision-scoped |
| 1118 | 2020: c_valenciana_res; 2021–2022: datos_adicionales_anexo_b | 2023–2025: madrid_res | Revision-scoped |
| 1119 | 2020: c_valenciana_res; 2021–2022: datos_adicionales_anexo_b | 2023–2025: madrid_res | Revision-scoped |
| 1120 | 2020: c_valenciana_res; 2021–2022: datos_adicionales_anexo_b | 2023–2025: madrid_res | Revision-scoped |
| 1171 | 2020: c_valenciana_res | 2022–2025: murcia_res | Distinct roles |
| 1209 | 2021–2022: castilla_y_leon_res | 2024–2025: c_valenciana_res | Distinct roles |
| 1714 | 2021–2023: anexo_a_res; 2024: i_baleares_res | 2025: cantabria_res | Revision-scoped; three-way split |
| 1715 | 2021–2023: anexo_a_res; 2024: i_baleares_res | 2025: cantabria_res | Revision-scoped; three-way split |
| 1763 | 2021: anexo_c_res; 2022: cantabria_res | 2024–2025: i_baleares_res | Three-way split; existing wrong role `irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin` in i_baleares must be corrected |

---

## dtype divergences

Three casilla ids exhibit `data_type` changes across revisions within this cluster:

| id | revisions (old dtype) | revisions (new dtype) | ccaa | notes |
|----|----------------------|----------------------|------|-------|
| 0210 | 2021–2023: `text` | 2024–2025: `nif` | castilla_la_mancha_res | Plan A retrofit corrected in 2024; already roled as `investment_entity_nif` from 2024 only |
| 1070 | 2020: `text` | 2021–2025: `nif` | la_rioja_res | Plan A retrofit in 2021; already roled as `worker_nif` from 2021 only |
| 1096 | 2020–2021: `text` | 2022–2025: `nif` | c_valenciana_res | Plan A retrofit in 2022; already roled as `landlord_nif` from 2022 only |

For all three: bulk-apply must gate the `semantic_role` assignment on the revision range where `data_type = "nif"` is declared. The text-dtype revisions must not receive the NIF role.

---

## decimal/money divergence note

All 482 casillas in this cluster that carry an amount field use `data_type = "decimal"` (absent field, which defaults to decimal in M100 IRPF conventions) rather than `"money"`. This is consistent with the taxonomy reference which documents that M100 uses `decimal` for IRPF intermediate-precision amounts. No `money` dtype is declared in this cluster. The roles introduced here all bind `decimal` and do not conflict with existing `money`-typed cross-modelo roles.

---

## Already-roled casillas (no change required)

22 casillas carry roles assigned by the prior NIF audit. These are listed here for completeness:

`0804` (worker_nif), `0911` (landlord_or_foreign_id_nif), `0949` (service_provider_nif), `0989` (worker_nif), `0993` (worker_nif), `1070` (worker_nif, 2021+), `1076` (investment_entity_nif), `1096` (landlord_nif, 2022+), `1107` (service_provider_nif), `1109` (service_provider_nif), `1244` (parent_nif), `1699` (worker_nif), `1700` (worker_nif), `1763` (irpf_anexo_c_exceso_sps_rg_contribuciones_pendiente_fin — **incorrect; requires correction per hazard table above**), `2040` (investment_entity_nif), `2042` (investment_entity_nif), `2044` (canarias_nif_or_nie), `2045` (canarias_nif_or_nie), `2046` (canarias_nif_or_nie), `2047` (canarias_nif_or_nie), `2052` (canarias_nif_or_nie), `2053` (canarias_nif_or_nie), `2054` (canarias_nif_or_nie), `2055` (canarias_nif_or_nie), `0210` (investment_entity_nif, 2024+)

Note: `0210` is counted in both roled (2024–2025) and the dtype-divergence table (2021–2023 were text, not nif).
