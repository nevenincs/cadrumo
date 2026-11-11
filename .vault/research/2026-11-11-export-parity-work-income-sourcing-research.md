---
tags:
  - '#research'
  - '#export-parity'
date: '2026-11-11'
modified: '2026-11-11'
body_schema: 'body-v2'
body_hash: 'sha256:8ec25f88e07a1b85669d3cb04230d99bc87ef3b3fc0211444148f2e2e7458124'
related:
  - "[[2026-11-11-export-parity-work-income-sourcing-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #research) and one feature tag.
     Replace export-parity with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown [label](path) links in the document body.
     - Cite external sources as bare URLs. Cite code, commits, packages, and
       standards as inline backtick locators: `src/module.py:42`, commit
       `abc1234`, `package@1.2.3`, RFC 9110. -->

<!-- DOCUMENT BOUNDARY:
     Research grounds; the ADR decides. Frame the option space with evidence
     and trade-offs; at most name the option the evidence favors and what
     the ADR must settle. Never record the decision here - a decision
     outside the ADR forks and goes stale when the ADR chooses otherwise. -->

# `export-parity` research: `Modelo 100 work income sourcing`

## Findings

Root: X:/code/cadrumo-wt-calc-pagos (paths are repo-relative). Line numbers are 1-based. Read-only research; no recommendations.

### 1. Manual chapter (Capitulo 3, Rendimientos del trabajo)

Editions (src/cadrumo/_data/corpus/manuals/renta/<year>/part1/source.pdf.extracted.md):
- 2020: chapter body 5897-8366; worked example 8330-8362 (pp. 222-223).
- 2021: chapter body 5941-8530.
- 2022: chapter body 6113-8793.
- 2023: chapter body 7477-10725; art. 20 table 10477-10482.
- 2024: chapter body 7780-11146; art. 20 table 10868-10874; worked example 11118-11142.
- 2025: chapter body 7792-11390; Esquema general p. 231 at 9818-9862; Fase 2 (gastos) pp. 232-258 at 10848-11087; Fase 3 (reduccion) pp. 259-260 at 11088-11125.
- Part 2 (deducciones autonomicas) exists for 2024 and 2025 only; not relevant to 0003-0025.
- The manual never names casillas 0003-0025. The only casilla number in chapter 3 is "casilla [0002]" (2025 md:11249). Casilla-to-concept mapping is therefore registry-only.

Structure (2025 md:9825-9858, p. 231, "Esquema general"):
- Fase 1 (integro): (+) importe integro devengado, retribuciones dinerarias (md:9825-9835); (+) valoracion fiscal mas ingreso a cuenta no repercutido, retribuciones en especie; (+) contribuciones empresariales a sistemas de prevision social (importes imputados); (+) aportaciones al patrimonio protegido; (-) reducciones (periodo de generacion superior a 2 anos; notoriamente irregulares; prestaciones publicas; prestaciones privadas regimen transitorio; actividades artisticas excepcionales) = rendimiento integro.
- Fase 2 (neto previo): (-) gastos deducibles: cotizaciones SS o mutualidades obligatorias de funcionarios; detracciones por derechos pasivos; cotizaciones a colegios de huerfanos; cuotas a sindicatos y colegios profesionales de colegiacion obligatoria (colegios limit 500 euros, art. 10 RIRPF, md ~10866-10875); gastos de defensa juridica en litigios con el empleador = neto previo (md:10848-10880).
- Fase 2 otros gastos (art. 19.2.f): (a) cuantia fija general 2.000 euros anuales (md:10896-10897, p. 255); (b) incremento por movilidad geografica, +2.000 con requisitos (md:10897-10937); (c) incremento trabajador activo con discapacidad: 3.500 (33 a 64 por ciento) or 7.750 (>= 65 por ciento, or ayuda de terceros / movilidad reducida) (md ~10960-10975). Limit: rendimiento integro that generated them, net of other expenses (md:11037-11051). Worked example md:11061-11085 (2.000 + 3.500 = 5.500; limit 1.800).
- Fase 3 (neto reducido): (-) reduccion Copa America (md:11089-11100); (-) reduccion general art. 20 (md:11101-11125); = rendimiento neto reducido (md:9856-9858).
- Art. 19.2.f expenses apply per unidad familiar in tributacion conjunta (md:10888-10890).

Art. 20 reduccion general, by manual edition:
- 2020 (md:8153-8161; example 8343-8361; ceiling text md:7360): 5.565 if RNT <= 13.115; 5.565 - 1,5 x (RNT - 13.115) for RNT 13.115-16.825; ceiling 16.825. Example RNT 14.630 gives 3.292,50.
- 2021 (md:8318-8326): same as 2020 (5.565; 13.115; 16.825).
- 2022 (md:8581-8589): same as 2020 (5.565; 13.115; 16.825).
- 2023 (novedad md:633-638: "pasa de 5.565 a 6.498", "de 16.825 a 19.747,5"; table md:10477-10482): 6.498 if RNT <= 14.047,5; 6.498 - 1,14 x (RNT - 14.047,5) for 14.047,5-19.747,5; ceiling 19.747,5.
- 2024 (novedad md:513-516: "pasa de 6.498 a 7.302"; table md:10868-10874): 7.302 if RNT <= 14.852; 7.302 - 1,75 x (RNT - 14.852) for 14.852-17.673,52; 2.364,34 - 1,14 x (RNT - 17.673,52) for 17.673,52-19.747,5. Example md:11118-11142 (RNT 13.640 gives reduction 7.302; reducido 838).
- 2025 (table md:11101-11119; ceiling and 6.500 other-income gate md:11104-11106): identical table to 2024. RNT = integro minus art. 19.2 letters a) to e) expenses (md:11110-11111, 11119-11120), i.e. excludes the 19.2.f otros gastos.
- 2025 md:9857 repeats the 19.747,50 ceiling in the Fase 3 summary.
- Separate, not art. 20: cuota deduction "por obtencion de rendimientos del trabajo" for integros < 18.276 euros (2025 md:787-800). Not a casilla in 0003-0025.

Worked examples in the manual:
- 2020 (md:8330-8362): integros 18.300; reduccion 18.2 3.060; SS 610; otros 2.000 + 3.500 disabled; RNT 14.630; reduccion 3.292,50; reducido 5.837,50.
- 2024 (md:11118-11142): integros 20.300; SS 3.600; otros 2.000 + 3.500; reduccion 7.302; reducido 838. The 2025 manual repeats the same example (md ~11370-11384).
- 2025 caso practico L.M.H. (md:11280-11300): retribuciones 10.100; indemnizacion 75.000; SS 3.600; exempt 64.800; excess 10.200 reduced 30 por ciento; text "Los datos facilitados por la empresa en el correspondiente certificado de retenciones e ingresos a cuenta" at md:11285-11287.

Stated versus computed, as read from the manual (the manual prescribes arithmetic; it does not label fields stated or computed):
- Stated (taxpayer or payer input): 0003 (md:9825-9835); 0004, 0005, 0006 (md:9007-9010 valoracion plus ingreso a cuenta no repercutido; md:8988-8996 region on ingreso a cuenta on payments in kind); 0008-0010 (Fase 1 bullets); 0011 (Fase 1 reducciones); 0013-0016 (Fase 2 bullets, md:10860-10880); 0020, 0021 (md:10897-10975); 0023 (art. 20 table md:11101-11125).
- Arithmetic in the manual: 0012 (sum of Fase 1 lines), 0017, 0018, 0022 (= neto), 0025 (= reducido); 0019 is limited by the 2.000 general amount and by the integro limit (md:11037-11051); 0007 (= valoracion + ingreso a cuenta no repercutido, md:9010).

### 2. Registry: Modelo 100 casillas 0003-0025

Storage pattern:
- 2020 authors the casillas (src/cadrumo/_data/registry/aeat/modelos/100/revisions/2020/casillas/0001-declarations.toml): 0003 at :19, 0004 :26, 0005 :33, 0006 :40, 0007 :47, 0008 :56, 0009 :63, 0010 :70, 0011 :77, 0012 :85, 0013 :95, 0014 :102, 0015 :109, 0016 :116, 0017 :123, 0018 :133, 0019 :143, 0020 :151, 0021 :158, 0022 :165, 0023 :175, 0025 :182. No 0024 in 2020.
- 2021, 2023, 2024, 2025 do not redeclare casillas 0003-0025 in their casillas files. They inherit through casilla_overrides blocks in revision.toml with a selector to the previous revision (2021 from revision.toml:64; 2022 from :67; 2023 from :66; 2024 from :66; 2025 from :83).
- 2022 casillas file adds 0024 (revisions/2022/casillas/0001-declarations.toml:2).
- No label attribute exists on any casilla record; the human name is semantic_role. Labels appear only in continuity evolutions (label_evolved). Form placement: revisions/<y>/form_layouts/0001-form-layout.toml (2020 line 17: casilla_id = "0003", kind = "on_form", box_number = "0003").
- Kind: the attribute is input_kind; absence means input.

Per casilla (2020 base; input = no input_kind):
- 0003 continuidad_id irpf-rendimiento-trabajo-importe-integro-dinerario; role irpf_rendimiento_trabajo_importe_integro_dinerario; input; section toma_datos_ampliada/rdto_trabajo (2025 section rendimientos_trabajo).
- 0004 irpf-rendimiento-trabajo-especie-valoracion; role irpf_rendimiento_trabajo_especie_valoracion; input.
- 0005 irpf-rendimiento-trabajo-especie-ingreso-cuenta; input.
- 0006 irpf-rendimiento-trabajo-especie-ingreso-cuenta-repercutido; input.
- 0007 irpf-rendimiento-trabajo-especie-importe-integro; computed; formula renta-trabajo-especie-importe-integro.
- 0008 irpf-rendimiento-trabajo-contribucion-empresarial-prevision; input.
- 0009 irpf-rendimiento-trabajo-contribucion-empresarial-seguro-dependencia; input.
- 0010 irpf-rendimiento-trabajo-aportacion-patrimonio-protegido; input.
- 0011 irpf-rendimiento-trabajo-reduccion; input; data_type decimal.
- 0012 irpf-rendimiento-trabajo-total-ingresos-integros; computed; formula renta-trabajo-total-ingresos-integros-computables.
- 0013 irpf-rendimiento-trabajo-gasto-ss-mutualidad; input.
- 0014 irpf-rendimiento-trabajo-gasto-sindicato; input.
- 0015 irpf-rendimiento-trabajo-gasto-colegio-profesional; input.
- 0016 irpf-rendimiento-trabajo-gasto-defensa-juridica; input.
- 0017 irpf-rendimiento-trabajo-rendimiento-neto-previo; computed; formula renta-trabajo-rendimiento-neto-previo.
- 0018 irpf-rendimiento-trabajo-suma-rendimientos-netos-previos; computed; formula renta-trabajo-suma-rendimientos-netos-previos.
- 0019 irpf-rendimiento-trabajo-gasto-otros; input in 2020; computed from 2021 (override revisions/2021/revision.toml:136-138, formula renta-trabajo-otros-gastos).
- 0020 irpf-rendimiento-trabajo-incremento-traslado-residencia; input.
- 0021 irpf-rendimiento-trabajo-incremento-discapacitado-activo; input.
- 0022 irpf-rendimiento-trabajo-rendimiento-neto; computed; formula renta-trabajo-rendimiento-neto.
- 0023 irpf-rendimiento-trabajo-reduccion-gastos-generales; input; no formula targets it in any edition.
- 0024 (2022 onward) irpf-rendimiento-trabajo-aportacion-empresa-decision-trabajador; role irpf_rendimiento_trabajo_aportacion_empresa_decision_trabajador; input.
- 0025 irpf-rendimiento-trabajo-rendimiento-neto-reducido; computed; formula renta-trabajo-rendimiento-neto-reducido.

Formulas (revisions/<y>/formulas/0001-declarations.toml):
- 2020: 0007 at line 562; 0017 at 579; 0018 at 596; 0022 at 607; 0012 at 942; 0025 at 960. Expressions: 0007 = 0004 + 0005 - 0006; 0012 = 0003 + 0007 + 0008 + 0009 + 0010 - 0011; 0017 = 0012 - 0013 - 0014 - 0015 - 0016; 0018 = copy of 0017; 0022 = 0018 - 0019 - 0020 - 0021; 0025 = 0022 - 0023. Nothing targets 0019 or 0023 in 2020.
- 2021: adds renta-trabajo-otros-gastos (target 0019; formulas/0001-declarations.toml:17-22): min(literal 2000, max(literal 0, casilla 0018)). Listed in revision.toml:6654 (sequence_additions) and :7037.
- 2022: no formula touches 0003-0025.
- 2023 and 2024: 2 formulas each; none touch 0003-0025.
- 2025: 6 formulas; none touch 0003-0025 (targets 2232, 2211, 0512, 1039, 0159, trabajo-mar-renta-exenta).
- 2021-2025 do not restate the 2020 formulas; continuity depends on engine inheritance of formulas (not verified in code here).

Overrides and evolutions by edition:
- 2021 (revisions/2021/revision.toml from line 64): overrides for 0003-0025 (0024 did not exist yet) with metadata only (continuidad_origin, continuidad_evidence, source_refs), except 0019 (computed plus formula).
- 2022 (revision.toml from :67): metadata overrides for 0003-0023 and 0025. Override at revision.toml:2256-2259 sets 0596 input_kind "bound" and binding "renta-retencion-soportada-trabajo" (selector 2021/0596).
- 2023 (revision.toml from :66): metadata overrides only for 0003-0025. Label evolutions for 0003 (revisions/2023/casilla_continuidad_evolutions/0001-declarations.toml:1363), 0017 (:1211), 0025 (:1219).
- 2024 (revision.toml from :66): metadata overrides only for 0003-0025. Label evolution for 0012 (revisions/2024/casilla_continuidad_evolutions/0001-declarations.toml:2219).
- 2025 (revision.toml from :83): overrides for 0003-0025 that change section to ["rendimientos_trabajo"] (plus metadata). Label and section evolutions for each of 0003-0025 in revisions/2025/casilla_continuidad_evolutions/0001-declarations.toml (e.g. 0003 at :4019-4027; 0007 at :2387-2395; 0011 at :3411-3419; 0012 at :2419-2427; 0017 at :2435-2443; 0019 at :3443-3451; 0023 at :3507-3515; 0024 at :1259-1267; 0025 at :2451-2459).
- Editions that change the content of a casilla: 2020 (authoring), 2021 (0019 computed plus 2000 literal), 2022 (new 0024; 0596 bound to retention binding), 2025 (sections only). 2023 and 2024 change labels only.

Bindings (revisions/<y>/bindings/0001-declarations.toml):
- 2020 (10 bindings): none targets 0003-0025 (profile, modelo 130/131 prefill, minimo descendientes).
- 2021 (1): estimacion directa; none targets 0003-0025.
- 2022 (82): renta-retencion-soportada-trabajo at bindings/0001-declarations.toml:203 (provider kind retencion_soportada, income_class trabajo, quantity pago_a_cuenta). Feeds 0596 (irpf_retencion_trabajo, revisions/2020/casillas/0001-declarations.toml:4136-4139) through the 2022 override. None targets 0003-0025.
- 2023 (2), 2024 (1), 2025 (6): none targets 0003-0025.
- 2020 casillas 0003-0025 carry no binding attribute (verified).
- Total pagos a cuenta: 0609 (irpf_total_pagos_cuenta) at 2020 casillas:4212-4215.

### 3. Parameters and facts (art. 19.2.f and art. 20)

- No parameters entry holds the 2.000 (art. 19.2.f) amount or any art. 20 threshold or amount in any Modelo 100 revision. The only unrelated match: 2020 renta-estimacion-directa-simplificada-gastos-dificil-justificacion-cap = 2000 (revisions/2020/parameters/0001-declarations.toml:1039-1050, rd-439-2007:art-30, estimacion directa, not trabajo).
- The 2000 is a literal inside formula renta-trabajo-otros-gastos (revisions/2021/formulas/0001-declarations.toml:17-22).
- Fact src/cadrumo/_data/registry/aeat/facts/0038-lirpf-art-20-trabajo-reduccion-rnt-ceiling.toml (fact_id lirpf-art-20-trabajo-reduccion-rnt-ceiling, family scalar; the RNT ceiling):
  - variant 2022-01-01 (valid_to 2022-12-31): 16825.00; source aeat-renta-2022-manual-parte1; required text "Entre 13.115,1 y 16.825 euros" (lines 6-24).
  - variant 2023-01-01 (valid_to 2023-12-31): 19747.50; source aeat-renta-2023-manual-parte1 (lines 24-42); required text "Entre 14.047,5 y 19.747,5 euros".
  - variant 2024-01-01 (no valid_to): 19747.50; source boe-lirpf-statutory-facts; required text "19.747,5 euros" (line 42 onward).
  - No variant for 2020, 2021 or 2025 (2025 covered by the open-ended 2024 variant, by inference).
  - The reduction amounts (5.565, 6.498, 7.302) and thresholds 13.115, 14.047,5, 14.852 are not facts; they appear only in manual text and in the BOE legal block below.
- Fact src/cadrumo/_data/registry/aeat/facts/2025/mapping/0087-2025-lirpf-art20-reduction-verification-mapping.toml: maps the RNT role irpf_rendimiento_trabajo_rendimiento_neto and the reduction role irpf_rendimiento_trabajo_reduccion_gastos_generales (0023) to the ceiling fact, predicate positive_rnt_below_ceiling_and_zero_reduction, source_kind verification_advisory. Advisory only; it does not compute.
- Fact src/cadrumo/_data/registry/aeat/facts/0036-lirpf-work-income-general-declaration-limit.toml: 22000 euros from 2007-01-01 (ley-35-2006:art-96). Obligation threshold, not a casilla.
- Legal blocks in src/cadrumo/_data/registry/aeat/legal/irpf.toml: art. 19 at lines 5973-5990, effective 2015-01-01, required text "2.000 euros anuales" at line 5987; art. 20 at lines 5995-6010, effective 2024-01-01 (RDL 4/2024 art. 3.1), required text includes "rendimientos netos del trabajo inferiores a 19.747,5 euros", "iguales o inferiores a 14.852 euros: 7.302 euros anuales", "multiplicar por 1,75 la diferencia", "multiplicar por 1,14 la diferencia".
- revisions/2025/constructs/0001-declarations.toml:175 lists renta-trabajo-otros-gastos in a construct.

### 4. Suffered-withholding binding and stored record

Binding module src/cadrumo/domain/calculations/registry/retencion_soportada_bindings.py (301 lines):
- Lines 55-56: TOTAL_PAGOS_A_CUENTA_ROLE = "irpf_total_pagos_cuenta".
- Lines 58-92: RETENCION_SOPORTADA_CREDIT_ROLES. TRABAJO (line 60) admits only irpf_retencion_trabajo (casilla 0596). Each class has one credit role; both urban-rental classes share one.
- Lines 94-101: RETENCION_SOPORTADA_NON_CREDIT_ROLES is an empty frozenset for every class (dict.fromkeys over the enum). Docstring lines 99-100: no income casilla is admitted until a decision names it, so every quantity other than pago_a_cuenta is refused wherever it is bound.
- Lines 104-111: RetencionSoportadaProvider {kind, income_class, quantity}.
- Lines 114-137: validator; money, decimal channel, sum aggregation only.
- Lines 165-182: credit_casilla_ids = operands of formulas that target the total-pagos role.
- Lines 185-197: _target_casilla_ids = direct or formula-operand targets.
- Lines 221-237: _target_failures. pago_a_cuenta must land in the credit set with an admitted role; any other quantity is refused, because NON_CREDIT is empty.
- Consequence: no income class admits any income casilla (0003-0025) for any quantity. Only the credit (0596 in practice) can be fed.

Core enums src/cadrumo/core/retencion_soportada.py:
- RetencionSoportadaClase (class at line 21): TRABAJO = "trabajo" (line 35); also capital_mobiliario, arrendamiento_inmueble_urbano and _actividad, actividad_economica, ganancia_patrimonial, atribucion_*, imputacion_aie_ute, imputacion_derechos_imagen.
- RetencionSoportadaCantidad (class at line 54): pago_a_cuenta (line 64), retencion, ingreso_a_cuenta, ingreso_a_cuenta_repercutido, importe_integro (line 68). Docstring: credit = retencion plus whole ingreso a cuenta; repercusion never reduces the credit.

Stored record src/cadrumo/domain/renta/retencion_soportada.py (RetencionSoportadaRecord, payload schema v1):
- Fields: ejercicio (line 61), payer_tax_id (line 63, encrypted payload), payer_legal_name (line 64, optional), payer_ref (line 65, keyed digest), income_class (line 67), importe_integro_dinerario (line 68), valoracion_especie (line 69), retencion (line 70), ingreso_a_cuenta (line 71), ingreso_a_cuenta_repercutido (line 72), origin (line 73: payer_certificate or operator_declaration), evidence_fingerprint (line 74), replaces_evidence_fingerprint (line 76), captured_at (line 83).
- Validators: repercutido must not exceed ingreso a cuenta (lines 87-90); payer_certificate requires a fingerprint (lines 92-97).
- Derived: pago_a_cuenta = retencion + ingreso_a_cuenta (lines 105-113); importe_integro = importe_integro_dinerario + valoracion_especie + ingreso_a_cuenta - ingreso_a_cuenta_repercutido (lines 116-128).
- Not present on the record: cotizaciones a la Seguridad Social (casilla 0013), sindicato (0014), colegio profesional (0015), defensa juridica (0016), contribuciones empresariales (0008, 0009), aportaciones patrimonio protegido (0010), reduccion (0011, 0023), otros gastos and increments (0019-0021), and any split of integro between 0003 and 0007 (only dinerario and especie combined in the derived importe_integro).
- Request model src/cadrumo/application/retencion_soportada_certificado/requests.py lines 36-63 mirrors the same fields plus source_path, source_directory and expected_revision_id. No cotizaciones field anywhere in the record or the request.
- Of the quantities, only pago_a_cuenta has a permitted target today (binding rules above).

### 5. Personas (dev/fixtures/personas/)

asalariada-familia:
- persona.toml lines 84-91 `[[withholding_certificates]]`: payer asalariada.empleador, ejercicio horizon-1, income_class trabajo, origin operator_declaration (not payer_certificate), importe_integro 36000.00, retencion 5412.00, cotizaciones_seguridad_social 2332.80. Comment lines 82-83: the taxpayer transcribes the certificate; the catalogue holds no certificate document.
- cotizaciones_seguridad_social has no counterpart in RetencionSoportadaRecord.
- documents.toml line 3: documents = [] (no certificate document).
- expectations.toml:
  - lines 4-11: Modelo 100 applicable (36000 above the 22000 limit, art. 96.2).
  - lines 31-46: values casillas {"0596" = "5412.00"}; not_sourced {"0003" = "36000.00", "0013" = "2332.80"}; concepts rendimiento_neto_previo_trabajo 33667.20, otros_gastos_trabajo 2000.00, reduccion_rendimientos_trabajo 0.00, rendimiento_neto_reducido_trabajo 31667.20; grounding verified; reason at line 46 says the application does not source 0003 or 0013 from the certificate (application gap pending a decision).
  - lines 48-62: other values (minimo_*), not work income.
- No expectation asserts 0003-0025 as casillas; 0003 and 0013 are listed as not_sourced.

arrendador-jubilado:
- persona.toml lines 44-52 `[[withholding_certificates]]`: payer arrendador.pagador-pension, ejercicio horizon-1, income_class trabajo (a pension), origin operator_declaration, importe_integro 21840.00, retencion 2180.00. No cotizaciones field.
- persona.toml line 31: irpf-income-categories includes "pension", which is not a RetencionSoportadaClase token.
- documents.toml line 3: documents = [].
- expectations.toml:
  - lines 40-51: values casillas {"0596" = "2180.00"}; concepts pension_integra 21840.00, otros_gastos_trabajo 2000.00, rendimiento_neto_trabajo 19840.00, reduccion_rendimientos_trabajo 0.00; grounding verified; no not_sourced entry.
  - lines 86-98: second block governed_by ley-35-2006:art-23-2021; same work-income concepts and 0596 2180.00; grounding verified.
  - lines 4-11: Modelo 100 applicable (pension under 22000, but capital inmobiliario is not exempt).
  - lines 53-68 and 100-125: capital inmobiliario values (not work income); grounding unverified for the application path.
- The 2.000 is deducted with no social-security deduction, because the certificate carries no cotizaciones (persona.toml lines 44-52).

## 6. The accepted schemas ADR on income quantities

- `.vault/adr/2026-11-01-export-parity-suffered-withholding-schemas-adr.md:60-80` defines the quantities `importe_integro` and `retencion` "for income casillas and cross-checks" and restricts credit casillas to `pago_a_cuenta`; income roles are left to a later decision.

### Corrections made while drafting the ADR

- The 2020 manual's art. 20 table is at md:8155-8162 (the locator above is off).
- The support floor is 2022 (`src/cadrumo/_data/registry/aeat/legal/supported-filing-years.toml`), so the 2020 and 2021 Modelo 100 editions are below it; the baseline for new bindings is the edition that declares `renta-retencion-soportada-trabajo` (2022).

## Sources

- Bundled Manual práctico de Renta, Capítulo 3, editions 2020-2025 under `src/cadrumo/_data` (locators per finding above).
- Modelo 100 registry editions `src/cadrumo/_data/registry/aeat/modelos/100/revisions/*`.
- `src/cadrumo/domain/calculations/registry/retencion_soportada_bindings.py:94-101`; `src/cadrumo/domain/renta/retencion_soportada.py:61-83`.
- Personas `dev/fixtures/personas/asalariada-familia`, `dev/fixtures/personas/arrendador-jubilado`.
