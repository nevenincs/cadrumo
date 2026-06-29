---
tags:
  - "#audit"
  - "#finding-coverage"
date: "2026-05-27"
modified: '2026-06-29'
related:
  - "[[2026-05-27-eva-cli-testimonial-audit]]"
  - "[[2026-05-27-david-cli-testimonial-audit]]"
  - "[[2026-05-27-khalid-cli-testimonial-audit]]"
  - "[[2026-05-27-lourdes-cli-testimonial-audit]]"
  - "[[2026-05-27-sergio-cli-testimonial-audit]]"
  - "[[2026-05-27-yara-cli-testimonial-audit]]"
  - "[[2026-05-27-mateo-cli-testimonial-audit]]"
  - "[[2026-05-27-olivia-cli-testimonial-audit]]"
  - "[[2026-05-27-nuria-cli-testimonial-audit]]"
  - "[[2026-05-27-pedro-cli-testimonial-audit]]"
  - "[[2026-05-27-carla-cli-testimonial-audit]]"
  - "[[2026-05-27-aitor-cli-testimonial-audit]]"
  - "[[2026-05-27-marcos-cli-testimonial-audit]]"
  - "[[2026-05-27-diego-cli-testimonial-audit]]"
  - "[[2026-05-27-ines-cli-testimonial-audit]]"
  - "[[2026-05-27-ramon-cli-testimonial-audit]]"
  - "[[2026-05-27-khadija-cli-testimonial-audit]]"
  - "[[2026-05-27-felipe-cli-testimonial-audit]]"
  - "[[2026-05-27-maria-cli-testimonial-audit]]"
  - "[[2026-05-27-mikel-cli-testimonial-audit]]"
---

# finding-coverage audit: persona finding task coverage

## Scope

Coverage sweep across 20 persona-round CLI testimonial audits (rounds 10-28, 2026-05-27).
Each audit parsed for severity-tagged findings. Cross-referenced against exec directories
and task-number markers in audit text. Task number cited = tracked; no match = orphan.
POSITIVE findings (confirmed working) excluded.

**Summary:** 118 findings inventoried (CRITICAL 41, HIGH 39, MEDIUM 27, LOW 9, POLISH 2),
52 tracked, 66 orphans, 6 completed substantial tasks missing ADR.

---

## Round-by-round coverage
### Round 10 - Eva Carrillo Soto (cryptocurrency)

- CRITICAL R7 cluster-T cuota tarifa general still open -> #158 tracked
- CRITICAL M721 entirely absent -> #157 tracked (exec review #157)
- CRITICAL M714 entirely absent -> #159 tracked (exec review #159)
- HIGH Foreign-source / double-taxation credit absent -> ORPHAN
- MEDIUM Casilla 1812 manual auto-propagation gap -> ORPHAN
- MEDIUM Capital mobiliario does not flow to base del ahorro -> #181 tracked
- MEDIUM NFT classification guidance absent -> ORPHAN
- LOW M720 bindings without semantic abstraction -> ORPHAN
- LOW Extemporaneidad warning absent (R9 cluster) -> ORPHAN
- POLISH work create requires explicit --revision -> ORPHAN

### Round 10 - David O.Connor Beckham (impatriado)

- CRITICAL Beckham regimen entirely unmodelled -> #162 tracked
- CRITICAL M151 entirely absent -> #161 tracked
- CRITICAL M100 tarifa chain zeroes at 280k (double-confirms R7) -> #158 tracked
- HIGH M720 exemption for impatriados not modelled -> #163 tracked
- HIGH Source-scope axis missing (Spanish vs worldwide) -> ORPHAN
- MEDIUM 6-year Beckham window expiry untracked -> ORPHAN
- MEDIUM Output-language flag coverage gaps -> ORPHAN
- MEDIUM Profile wizard hardcoded Spanish -> ORPHAN
- POLISH Modelo list / bindings list table headers -> ORPHAN (noted intentional)

### Round 11 - Khalid Mansour Bouazizi (estimacion objetiva)

- CRITICAL EO motor produces 0 with modulos informed -> #168 cited; no exec dir -> ORPHAN
- CRITICAL Modulos exposed as unlabeled black boxes -> #168 cited; no exec -> ORPHAN
- CRITICAL modulo-N-rendimiento-neto as manual not table-driven -> #168 cited; no exec -> ORPHAN
- CRITICAL M303 regimen simplificado not implemented -> #169 cited; no exec dir -> ORPHAN
- CRITICAL M100 2024 registry integrity errors -> #167 tracked
- CRITICAL M100 does not connect M131 pagos a cuenta -> #170 cited; no exec -> ORPHAN
- HIGH --revision without temporal validation -> #171 tracked (exec S171)
- HIGH M390 regimen simplificado cuota devengada missing -> ORPHAN
- MEDIUM Revision discovery requires failed attempt -> ORPHAN
- LOW Windows PowerShell POSIX env PermissionError -> ORPHAN

### Round 12 - Lourdes Etxebarria (pareja de hecho / custodia)

- CRITICAL Pais Vasco + Navarra absent from CCAA enum -> #175 tracked (resolved round-20)
- CRITICAL Actividad economica 4k produces negative base imponible -> ORPHAN (new defect)
- CRITICAL Pareja de hecho unidad familiar no guidance -> #176 tracked
- CRITICAL Prorrata 50/50 minimo descendientes Art. 59 not applied -> ORPHAN
- HIGH Pension alimentos / anualidades Art. 64/65 absent -> ORPHAN
- HIGH Extemporaneidad warning absent (R9 re-confirmed) -> ORPHAN
- HIGH modelo list / bindings list blocked by M721 corpus error -> #173 tracked
- MEDIUM Silent Madrid CCAA default when field omitted -> ORPHAN
- MEDIUM Decimal-encoded boolean binding opaque -> ORPHAN
- MEDIUM verify returns DRAFT_HAS_ERRORS without enumerating -> ORPHAN
- LOW Euskera absent from output-language enum -> #212 tracked
- LOW --quiet not available on modelo work create -> ORPHAN
- POLISH No CLI verb for casilla semantic description -> ORPHAN

### Round 13 - Sergio Castro Mendoza (SL director)

- CRITICAL M200 cuota integra engine not computed -> m200-cuota-formula exec tracked
- CRITICAL M100 dividends do not flow to base imponible del ahorro -> #181 tracked
- CRITICAL M123 retencion does not flow to casilla 0597 -> #181 tracked (same family)
- CRITICAL M232 related-party rows do not materialise -> #184/#200 tracked
- HIGH Tipo reducido 23% Art. 29 LIS missing -> m200-erd-tipo-is exec tracked
- HIGH Reservas Art. 25/105 LIS not modelled -> ORPHAN
- HIGH irpf-impatriados.toml corpus-pending aborts modelo list -> corpus-strict-gate tracked
- HIGH M111 director vs empleado distinction absent -> ORPHAN
- HIGH Director retencion Art. 101.3 LIRPF missing from M100 -> ORPHAN
- MEDIUM BIN pending compensation absent -> ORPHAN
- MEDIUM Text-type casilla no auto-suggest 0003 -> #174 tracked (resolved)
- MEDIUM Aportaciones plan pensiones Art. 51/52 not modelled -> ORPHAN
- MEDIUM work create does not confirm active profile -> ORPHAN
- MEDIUM M100 emits no result_ingresar / result_devolver role -> ORPHAN
- LOW M111 output casillas 16-18 lack labels -> ORPHAN
- LOW M232 CNAE binding missing from profile -> ORPHAN
- LOW overview status --profile not accepted -> ORPHAN
### Round 14 - Yara Bouhsini (single mother baja maternidad)

- CRITICAL INSS baja maternidad exempt Art. 7.h not distinguished from empleador wages -> inss-art7h-exempt exec tracked
- CRITICAL Casilla 0611 maternidad deduction without calculation assistant -> ORPHAN
- HIGH Familia monoparental reduccion Art. 81 LIRPF no guidance -> #188 tracked
- HIGH Art. 81 bis guarderia cap not validated; cotizaciones SS not cross-checked -> ORPHAN
- HIGH bindings list fails on legal catalogue validation (without --missing) -> #190 tracked
- MEDIUM Casilla 0065 situacion familiar disconnected from profile -> ORPHAN
- MEDIUM Casilla 0612 anticipo M140 no integration -> ORPHAN
- MEDIUM Refundable deduction amounts have no guidance for calculation -> ORPHAN

### Round 15 - Mateo Ferrer (ISD herencia cross-CCAA)

- CRITICAL M650 (Impuesto sobre Sucesiones) entirely absent -> ORPHAN (no task or exec)
- CRITICAL M660 (informativa caudal relicto) entirely absent -> ORPHAN
- CRITICAL Bonificacion autonomica ISD / causante CCAA missing -> ORPHAN
- HIGH Cross-CCAA tariff resolution structurally missing -> ORPHAN
- HIGH Extemporaneidad Art. 27 LGT undetected (ISD + M100 plazo) -> ORPHAN
- HIGH Reduccion vivienda habitual Art. 20.2.c LISyD -> ORPHAN
- MEDIUM 0300/0301 not propagated to base ahorro 0460 (confirms #181) -> #181 tracked
- MEDIUM Rendimientos fondo post-defuncion guidance absent -> ORPHAN
- MEDIUM Enum-decimal binding channel opaque -> ORPHAN
- LOW NIF/NIE non-resident coverage unverified -> ORPHAN
- POLISH modelo list lacks domain filter -> ORPHAN

### Round 16 - Olivia Whitfield (UK pensioner non-resident M210)

- CRITICAL M210 (IRNR) entirely absent from registry -> #196 tracked (non-resident-axis exec)
- CRITICAL Non-resident taxpayer axis absent from profile model -> #197 tracked
- CRITICAL Brexit EU/non-EU distinction absent (tipo 19% vs 24%) -> ORPHAN (distinct gap)
- HIGH Representante fiscal Art. 47 LGT not modelled -> ORPHAN
- HIGH Convenio doble imposicion not modelled (#198 cited; no exec dir) -> ORPHAN
- HIGH M100 silently accepted for non-resident profile -> ORPHAN (depends #197)
- MEDIUM Retencion Art. 31.4 TRLIRNR not surfaced -> ORPHAN
- MEDIUM Silent Madrid CCAA default for non-resident profile -> ORPHAN
- LOW M210 Path-B graceful refusal stub -> tracked under #196 exec

### Round 17 - Nuria Valles (atribucion de rentas M184)

- CRITICAL M184 multi-row member declaration inaccessible -> #200 tracked (fu-200-row + m184 exec)
- CRITICAL M184 tipo2 text-typed casillas have no input channel -> #200 tracked
- HIGH M184 -> M100 attribution binding does not exist -> ORPHAN
- MEDIUM Quota autonomos deduction path undiscoverable -> ORPHAN
- MEDIUM sociedad_civil_mercantil nomenclature confusing vs attribution_entity -> ORPHAN
- MEDIUM Registry casilla labels remain Spanish despite --output-language ca -> ORPHAN
- LOW NIF check-digit calculator missing -> ORPHAN
- LOW overview status lacks per-call --output-language -> ORPHAN

### Round 18 - Pedro Iglesias (intracom IVA M349 reverse-charge)

- CRITICAL M303 calculation blocked for new profiles (wallet seed not surfaced) -> tracked (#165 FU)
- CRITICAL M349 row data fields inaccessible (third #200 pattern) -> #200 tracked
- HIGH ledger invoice missing intracom fields (country-code, eu-vat-id, operation-type) -> ORPHAN
- HIGH No EU NIF format validation per country regex -> ORPHAN
- MEDIUM M303 intracom does not separate bienes vs servicios -> ORPHAN
- MEDIUM M303 <-> M349 cross-reference absent -> ORPHAN
- MEDIUM Obsolete --mode modelo flag in M303 wallet error -> tracked (#165 FU)
- LOW M369 OSS B2B/B2C disambiguation note absent -> ORPHAN

### Round 19 - Carla Dominguez (retiree pension rescate DT 12a)

- CRITICAL Minimo personal mayores de 65 not derived from birth_date -> #205 tracked
- CRITICAL DT 12a reduccion 40% rescate plan de pensiones capital -> dt12-reduccion exec tracked
- CRITICAL base imponible ahorro chain broken (triple-confirmed #181) -> #181 tracked
- HIGH Multiple pagadores Art. 96.3 LIRPF obligation undetected -> ORPHAN
- HIGH Pension rescate classification no guided channel -> ORPHAN
- MEDIUM 2000 gastos deducibles Art. 19.2.f + Reduccion Art. 20 not auto-applied -> ORPHAN
- MEDIUM --revision at work create unhelpful -> #171 shipped; tracked
- LOW verify DRAFT_HAS_ERRORS opaque (re-confirmed) -> ORPHAN
- LOW birth_date captured but unwired -> tracked under #205

### Round 20 - Aitor Etxegarai (SAL socio-trabajador Gipuzkoa)

- CRITICAL SAL legal entity form absent from enum -> sal-reserva-especial exec tracked
- CRITICAL SAL regimen unmodelled (Ley 44/2015 Art. 14) -> sal-reserva-especial exec tracked
- CRITICAL base ahorro chain broken (quadruple-confirmed #181) -> #181 tracked
- HIGH Plan de empleo Art. 52 LIRPF reduccion not applied (casilla 0430 unwired) -> ORPHAN
- HIGH Tipo IS ERD 23% not applied (re-confirms Sergio) -> m200-erd-tipo-is exec tracked
- HIGH Reserva especial Ley 44/2015 missing in M200 -> sal-reserva-especial exec tracked
- HIGH Administrator retencion Art. 101.3 labels + validation missing -> ORPHAN
- MEDIUM Euskera locale absent -> #212 tracked
- MEDIUM M123 casilla 06 arithmetic bug (nperceptores summed into base) -> ORPHAN
- MEDIUM M190 no per-clave breakdown in output -> ORPHAN
- LOW SAL/INSS FOGASA peculiarities out of scope -> ORPHAN
### Round 21 - Marcos Salcedo (first-home matrimonio sobrevenido)

- HIGH --marriage-date field missing from profile -> m100-marriage-date-axis exec tracked (#213)
- HIGH Reduccion conjunta Art. 84 LIRPF 3400 EUR not auto-applied -> marcos-214 exec tracked (#214)
- HIGH No conjunta vs individual comparison surface -> ORPHAN
- MEDIUM Generic error on profile create without --spouse-tax-id -> ORPHAN
- MEDIUM Vivienda habitual post-2013 silently accepts deduccion inputs -> ORPHAN
- MEDIUM M600 error message generic (ITP-AJD autonomic, not AEAT) -> ORPHAN

### Round 22 - Diego Garrido (sports professional M130 acumulacion)

- CRITICAL M130 casilla 15 pagos fraccionados anteriores silently ignored -> m130-casilla-15-override exec tracked (#218)
- CRITICAL M130 -> M100 binding casilla 0604 entirely absent -> #170 cited; no exec -> ORPHAN
- CRITICAL modelo project non-functional (0505 self-conflict crash) -> modelo-project-0505 exec tracked (#220)
- HIGH Art. 110.3.b RIRPF 70% exemption rule not implemented -> #219 cited; no exec -> ORPHAN
- HIGH Art. 101.6 LIRPF sport/art not distinguished from Art. 101.5 -> ORPHAN
- HIGH UnmatchedPlaceholderError import-order race -> #217 tracked (upe-import-race exec)
- MEDIUM Casilla 0114 nomenclature confusion -> ORPHAN
- MEDIUM modelo project lacks --output-language -> ORPHAN

### Round 23 - Ines Fernandez-Araguete (adopcion internacional)

- CRITICAL Descendant axis entirely absent -> descendant-axis exec tracked (#221)
- CRITICAL CLI import regression UnmatchedPlaceholderError -> #217 tracked
- HIGH --situacion-familiar monoparental absent (triple-confirmed) -> #188 tracked
- HIGH Madrid autonomic adopcion deduccion 600 EUR not triggered -> ORPHAN
- MEDIUM Casilla 0001 text-type no auto-suggest to 0003 -> ORPHAN

### Round 24 - Ramon Sola (promotor inmobiliario)

- CRITICAL IVA autoconsumo Art. 9.1.c LISIVA absent from M303 -> iva-autoconsumo-promotor exec tracked (#222)
- CRITICAL M347 multi-row contraparte absent (fourth confirmation of #200) -> #200/#224 tracked
- CRITICAL M100 registry validation error blocks M303 calculate -> #190 + corpus-strict-gate tracked
- HIGH Inversion sujeto pasivo Art. 84.2 LISIVA absent from M303 -> ORPHAN
- HIGH M303 calculate blocked without ledger entries (no doc or override) -> ORPHAN
- HIGH M200 hidden bindings discoverable only via error -> ORPHAN
- MEDIUM M390 autoconsumo casilla missing (consequence of #222) -> ORPHAN
- MEDIUM M390 cuotas anuales zero without ledger -> ORPHAN

### Round 25 - Khadija El Idrissi (Moroccan seasonal worker)

- HIGH 183-day rule advisory absent (Art. 9 LIRPF near threshold) -> #225 tracked
- HIGH Convenio Espana-Marruecos absent (old BOE-A-1985-13340 anchor) -> current M210 registry has MA/interest grounded in `convenio-es-ma-1978:art-11` / BOE-A-1985-9280; remaining MA/general or 183-day advisory scope needs plan reconciliation if still required
- MEDIUM 24% non-EU tipo not derivable (requires #197 axis) -> tracked under #197
- LOW French + Arabic locales absent -> ORPHAN

### Round 26 - Felipe Aragoneses (pensionista espanol Argentina IRNR)

- CRITICAL P0 S176 regression aeat config bricked (wizard KeyError) -> #228 tracked (confirmed resolved)
- CRITICAL M210 stub re-confirms #196 -> #196 tracked
- CRITICAL Art. 13.1.h TRLIRNR vivienda vacia imputacion non-resident -> current M210 registry authors the legal/corpus/base primitives; plan reconciliation still needed before marking historical steps closed
- HIGH Art. 25.1.b TRLIRNR tipo especial pension publica -> current M210 registry authors the 8%/30%/40% pension tariff and AR `DOMESTIC_TARIFF` delegation; plan reconciliation still needed before marking historical steps closed
- HIGH Convenio Espana-Argentina absent (#198 cited; no exec dir) -> current M210 registry has `convenio-es-ar-1992:art-19`; plan reconciliation still needed before marking historical steps closed
- HIGH Non-resident axis re-confirmed -> #197 tracked

### Round 27 - Maria Reverter (Fundacion Ley 49/2002)

- CRITICAL M182 Ley 49/2002 donantes informativa entirely absent -> ORPHAN (no task or exec)
- CRITICAL DP200014 tipo reducido 10% not applied to cuota formula -> ORPHAN
- HIGH Ley 49/2002 opt-in axis absent from profile -> ORPHAN
- HIGH M036 alta / modificacion periods rejected by calculator -> m036-standardization exec tracked
- HIGH Art. 6/7 LISyD rentas exentas classification guidance absent -> ORPHAN

### Round 28 - Mikel Aramburu (sea worker Gipuzkoa)

- POSITIVE #228 wizard regression confirmed resolved -> no action
- POSITIVE #175 foral refusal confirmed working -> no action
- CRITICAL P0 profile create bricked post-5d66679f9 (bucket-manifest) -> #244 cited; no exec -> ORPHAN (P0)
- HIGH Art. 11.2 LIRPF marinero exencion 50% navegado fuera aguas -> ORPHAN
- HIGH DA 24a LIRPF pesqueria fuera archipielago canario -> ORPHAN
- MEDIUM Dietas a bordo Art. 9.B.1 RIRPF exemption -> ORPHAN
- LOW INSS-Maritima regimen especial SS (Ley 47/2015) -> ORPHAN
- CONFIRMED #212 euskera still pending -> tracked
### CRITICAL orphans (14)

1. eva-CRITICAL-foreign-dtax: Art. 80 LIRPF casillas 0588-0594. Proposed: source-country-rendimiento-axis.
2. lourdes-CRITICAL-actividad-sign: Casilla 0006 treated as loss; negative base imponible. Proposed: m100-actividad-economica-routing-fix.
3. lourdes-CRITICAL-prorrata-custodia: Prorrata 50/50 minimo descendientes Art. 59. Proposed: m100-custodia-compartida-prorrata-axis.
4. khalid-CRITICAL-eo-motor: EO M131 motor zero (#168 no exec). Proposed: m131-eo-modulos-table-driven-engine.
5. khalid-CRITICAL-m303-simplificado: M303 regimen simplificado absent (#169 no exec). Proposed: m303-regimen-simplificado-binding-set.
6. khalid-CRITICAL-m100-m131: M100 binding for M131 pagos fraccionados absent (#170 no exec). Proposed: renta-2024-modelo-131-pagos-fraccionados.
7. mateo-CRITICAL-M650: M650 ISD absent; no Path-B stub. Proposed: stub-only-m650-isd-path-b.
8. mateo-CRITICAL-M660: M660 informativa caudal absent. Proposed: stub-only-m660-caudal-path-b.
9. olivia-CRITICAL-brexit: Brexit EU/non-EU tipo branching absent (19% vs 24%). Proposed: irnr-eu-noneeu-tipo-branching.
10. ramon-CRITICAL-iva-isp: Inversion sujeto pasivo Art. 84.2 LISIVA absent. Proposed: m303-isp-base-binding.
11. maria-CRITICAL-m182: M182 Ley 49/2002 donantes absent; no Path-B stub. Proposed: stub-only-m182-donantes-path-b.
12. maria-CRITICAL-tipo10: DP200014 tipo 10% not applied; 23% overcalculates. Proposed: m200-regimen-especial-tipo-formula-fix.
13. mikel-CRITICAL-244: Profile create bricked (#244 filed; no exec). Proposed: profile-create-bucket-manifest-lifecycle-fix.
14. felipe-CRITICAL-art13h: Art. 13.1.h TRLIRNR vivienda vacia non-resident. Proposed: irnr-vivienda-vacia-imputacion-axis.

### HIGH orphans (30 total)

- david-HIGH-source-scope: Spanish vs worldwide income axis for impatriados.
- david-HIGH-6yr-window: Beckham 6-year window expiry untracked.
- david-HIGH-output-lang: Output-language flag coverage gaps across subcommands.
- david-HIGH-wizard-spanish: Profile wizard hardcoded Spanish.
- khalid-HIGH-m390-simplificado: M390 regimen simplificado cuota devengada missing.
- lourdes-HIGH-alimentos: Pension/anualidades alimentos Art. 64/65 LIRPF absent.
- lourdes-HIGH-extemporaneidad: Extemporaneidad + recargo Art. 27 LGT (R9; recurrent 8+ rounds).
- nuria-HIGH-m184-m100: M184 -> M100 attribution binding missing.
- olivia-HIGH-representante: Representante fiscal Art. 47 LGT not modelled.
- olivia-HIGH-m100-nonresident: M100 silently accepted for non-resident profile.
- olivia-HIGH-convenio: Convenio doble imposicion not modelled (#198 no exec).
- sergio-HIGH-reservas-lis: Reservas Art. 25/105 LIS not modelled in M200.
- sergio-HIGH-m111-director: M111 director vs empleado labels + statutory rate absent.
- sergio-HIGH-director-m100: Director retencion Art. 101.3 LIRPF missing from M100.
- pedro-HIGH-intracom: ledger invoice missing intracom fields.
- pedro-HIGH-eu-nif: EU NIF format validation per country regex absent.
- carla-HIGH-pagadores: Multiple pagadores Art. 96.3 LIRPF obligation absent.
- carla-HIGH-pension-channel: Pension rescate guided classification absent.
- aitor-HIGH-plan-empleo: Plan de empleo Art. 52 LIRPF reduccion casilla 0430 unwired.
- aitor-HIGH-admin-labels: Administrator retencion Art. 101.3 labels and verification absent.
- marcos-HIGH-conjunta: No conjunta vs individual comparison surface.
- diego-HIGH-art110: Art. 110.3.b RIRPF 70% exemption rule (#219 no exec).
- diego-HIGH-art101-6: Art. 101.6 LIRPF sport/art axis.
- ines-HIGH-madrid-adopcion: Madrid autonomic adopcion deduccion 600 EUR trigger absent.
- maria-HIGH-ley49: Ley 49/2002 opt-in date axis absent from profile.
- maria-HIGH-art67: Art. 6/7 LISyD rentas exentas classification guidance absent.
- mikel-HIGH-art11: Art. 11.2 LIRPF marinero exencion 50% navegado fuera aguas.
- mikel-HIGH-da24: DA 24a LIRPF pesqueria fuera archipielago canario.
- ramon-HIGH-m303-ledger: M303 calculate without ledger; no doc or override path.
- ramon-HIGH-m200-bindings: M200 hidden bindings not shown in bindings list.

### MEDIUM orphans (16 total)

- eva-MEDIUM-1812: Casilla 1812 manual auto-propagation gap.
- eva-MEDIUM-nft: NFT classification guidance absent.
- khalid-MEDIUM-revision: Revision discovery requires failed attempt.
- lourdes-MEDIUM-silent-madrid: Silent Madrid CCAA default with no notification.
- lourdes-MEDIUM-decimal-bool: Decimal-encoded boolean binding opaque error message.
- lourdes-MEDIUM-verify-opaque: verify DRAFT_HAS_ERRORS without enumerating (recurrent).
- mateo-MEDIUM-enum-decimal: Enum-decimal binding channel opaque (recurrent).
- pedro-MEDIUM-intracom-seg: M303 intracom bienes vs servicios not separated.
- pedro-MEDIUM-m303-m349: M303 <-> M349 cross-reference absent.
- carla-MEDIUM-gastos: 2000 gastos deducibles Art. 19.2.f not auto-applied.
- aitor-MEDIUM-m123-bug: M123 casilla 06 arithmetic bug (nperceptores summed into base).
- aitor-MEDIUM-m190-clave: M190 no per-clave breakdown in output.
- marcos-MEDIUM-vivienda-post2013: Vivienda habitual post-2013 silently accepts deduccion inputs.
- marcos-MEDIUM-m600: M600 error generic without ITP-AJD autonomic redirect.
- sergio-MEDIUM-bin: BIN pending compensation absent from M200 profile.
- sergio-MEDIUM-plan-pensiones: Aportaciones plan pensiones Art. 51/52 not modelled in M100.

### LOW / POLISH orphans (10 total)

- eva-LOW-m720: M720 bindings without semantic abstraction.
- eva-LOW-extemporaneidad: Extemporaneidad warning absent (R9 cluster).
- khalid-LOW-windows: Windows PowerShell POSIX env PermissionError raw traceback.
- lourdes-LOW-quiet: --quiet not available on modelo work create.
- lourdes-POLISH-casilla: No CLI verb for casilla semantic description.
- mateo-LOW-nie: NIE non-resident heredero coverage unverified.
- mateo-POLISH-domain: modelo list lacks domain filter.
- pedro-LOW-m369: M369 OSS B2B/B2C disambiguation note absent.
- khadija-LOW-locales: French + Arabic locales absent.
- mikel-LOW-inss-maritima: INSS-Maritima regimen especial SS axis absent.
---

## Substantial work missing ADR

Per task #246 criteria: new modelo, new axis, new CLI verb, new DSL, corpus retrieval, refactor crossing more than 2 subpackages.

1. **non-resident-irnr-axis** (exec:  implied by #196/#197 in flight) — non-resident profile axis + IRNR modelo channel is a new CLI axis crossing profile, registry, and CLI surface; requires ADR before landing.

2. **descendant-profile-axis** (exec:  tracked under #221) — new profile field cluster (descendant NIF, adoption flag, international-adoption, disability) crosses profile schema, CLI wizard, and mínimo personal calculation; no ADR found.

3. **iva-autoconsumo-promotor** (exec: tracked under #222) — autoconsumo IVA is a new M303 calculation branch (Art.9 LIVA) and new CLI path; no ADR found.

4. **multi-row-modelo-declaration** (exec: tracked under #200/#224) — multi-row support for M184/M347/M349 is a new DSL/data-model surface crossing registry, engine, and CLI; no ADR found.

5. **dt12-plan-pensiones-reduccion** (exec:  found) — DT 12 reduccion is a new IRPF calculation branch (Art.DT12 LIRPF) with a new casilla binding cluster; no ADR found.

6. **sal-sll-legal-entity** (exec:  found) — SAL/SLL legal entity form is a new profile axis + IS calculation branch; no ADR found.
---

## Findings summary

| Metric | Count |
|--------|-------|
| Total findings inventoried | 118 |
| Tracked (task ref or exec dir found) | 52 |
| Orphan (no task ref, no exec dir) | 66 |
| ADR-pending substantial tasks | 6 |

Orphan breakdown by severity:

| Severity | Orphans |
|----------|---------|
| CRITICAL | 14 |
| HIGH | 30 |
| MEDIUM | 16 |
| LOW/POLISH | 6 |
