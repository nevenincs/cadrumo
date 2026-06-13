---
tags:
  - "#research"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-05-31'
related: []
---

# trabajador-del-mar research: IRPF axis

Research to ground the trabajador-del-mar registry axis for issue #555.
Examines every BOE provision affecting workers in the Spanish merchant marine and fishing
sector: source-of-income rules, per-diem exemptions, vessel-based incentives, and the
cross-modelo wiring required in Modelo 100, Modelo 130, and Modelo 111.

---

## CRITICAL PRELIMINARY FINDING -- Issue brief contains a factual error

The task description cites DA 24 (Disposicion adicional 24): dietas a bordo exemption.

This is incorrect. Confirmed via direct inspection of Ley 35/2006 and AEAT 2024 guidance:

- DA 24 LIRPF is titled Retenciones sobre rendimientos del trabajo correspondientes a
  enero de 2015 (withholding on employment income for January 2015). It is a transitional
  withholding rule for the 2015 reform and has no maritime content whatsoever.

- The maritime dieta treatment does NOT live in a numbered LIRPF disposicion adicional.
  It flows from Art. 17.1.d) LIRPF (rendimientos del trabajo exceptuados de gravamen)
  plus Art. 9 RIRPF (Reglamento del IRPF, Real Decreto 439/2007).

- There is no named dietas a bordo provision with a fixed per-diem for civilian maritime
  workers in Ley 35/2006. The special naval dietas treatment that has been litigated is
  for military Navy personnel (Armada) -- and the TEAC has ruled those do NOT
  qualify as Art. 9.A.3.b) RIRPF dietas.

Implication: Any ADR authored from this task brief must re-scope away from DA 24 as the
legal grounding. The real legal framework is documented below.
## Findings

### 1. Art. 11.2 LIRPF -- Income Individualisation Rule

Source: Ley 35/2006, Art. 11.2 | BOE-A-2006-20764

Confirmed statutory text (via Supercontable.com annotation and DGT cross-references):
Los rendimientos del trabajo se atribuiran exclusivamente a quien haya generado el
derecho a su percepcion.

This is the general income individualisation rule for employment income.
It is NOT a maritime-specific norm. Its relevance to trabajadores del mar is structural:
because income is attributed to the person who earned it (not to the vessel or employer),
the vessel flag, registry, and waters of navigation determine which further provision
(Art. 7.p, REBECA, DA 41) applies -- but Art. 11.2 contains no maritime carve-out.

### 2. Art. 7.p) LIRPF -- Work Performed Abroad Exemption

Source: Ley 35/2006, Art. 7.p) | BOE-A-2006-20764

The primary maritime worker exemption pathway. Requirements:

- Work must be effectively performed outside Spanish territory (international waters count
  for foreign-flagged vessels in AEAT accepted practice).
- The foreign entity receiving the services must be non-resident in Spain OR have a
  permanent establishment abroad.
- The territory must have an equivalent income tax or CDI with Spain. Flags from France,
  Ireland, and UK typically qualify.
- Annual cap: 60,100 EUR.

Calculation: annual salary divided by 365, multiplied by qualifying days abroad.

Confirmed active for 2024 and 2025. Supreme Court doctrine (April 2025) extended this to
military Navy personnel in NATO/UN sea operations. TEAR Galicia (December 2024) confirmed
this exemption valid for Galician fishing crew.

### 3. REBECA -- Registro Especial de Buques y Empresas Navieras de Canarias

Source: Ley 19/1994, Arts. 73.2, 73.3, 75.1, 75.3 | BOE-A-1994-16100

For crew members (IRPF taxpayers) of vessels enrolled in REBECA, or vessels on regular
scheduled routes between the Canary Islands and mainland Spain:

- 50% exemption on gross employment income accrued from navigation.
- Since 1 January 2021: extended to crews of vessels from REBECA-registered shipping
  companies that are themselves registered in another EU/EEA member state vessel registry.

This flows through the Canary Islands special regime statute (Ley 19/1994), not a LIRPF
disposicion adicional. The exempt 50% is excluded from the withholding base in Modelo 111.

### 4. DA 41 LIRPF -- Tuna Fishing Fleet Crew (pending EU clearance, inactive 2024)

Source: Ley 35/2006, Disposicion adicional cuadragésima primera | BOE-A-2006-20764
Added by Ley 6/2018 (Presupuestos Generales del Estado 2018).

Scope: crew members (IRPF taxpayers) of Spanish-flagged fishing vessels:
- Registered in the community fishing fleet register.
- Fishing exclusively tuna or related species outside EU waters AND at least 200 nautical
  miles from member state baselines.
- Shipowning company in the Special Register of Spanish Fishing Vessel Companies.

Benefit: 50% exemption on employment income from navigation in qualifying vessels.

Status: NOT applicable in 2024 or 2025. Requires prior EU state-aid clearance which has
not been granted. AEAT confirms non-applicability in official 2024 guidance.
### 5. Art. 17.1.d) LIRPF + Art. 9 RIRPF -- General Dietas Framework

Source: Ley 35/2006, Art. 17.1.d) | BOE-A-2006-20764
Source: Real Decreto 439/2007, Art. 9 | BOE-A-2007-6820

Art. 17.1.d) excludes from gross income dietas and travel expense allowances for
displacement from a habitual workplace, within limits set by Art. 9 RIRPF.

Daily caps (current, per Orden HFP/792/2023, BOE-A-2023-16461):
- National territory, no overnight stay: 26.67 EUR/day
- National territory, with overnight stay: 53.34 EUR/day
- Abroad, no overnight stay: 48.08 EUR/day
- Abroad, with overnight stay: 91.35 EUR/day

Key limitation for maritime workers: The TEAC has ruled that allowances paid to Armada
military personnel for being at sea do NOT qualify as Art. 9.A.3.b) RIRPF dietas because
they compensate for the nature of the job rather than for displacement from a fixed habitual
workplace. The same reasoning applies to civilian mariners whose workplace IS the vessel.
Dietas a bordo paid to crew whose enrolment vessel is their ordinary workplace are ordinary
employment income under this doctrine.

Burden of proof: STS 954/2020 and STS 3185/2021 confirmed the employer (not the employee)
bears responsibility for proving paid amounts correspond to actual work-related displacement.

### 6. Modelo 100 / Modelo 130 / Modelo 111 Wiring

Modelo 100 (annual IRPF declaration):
- Gross employment income (rendimientos del trabajo integros) includes all maritime wages
  before any exemption. No standalone maritime-specific casilla exists in the current form.
- Art. 7.p) exemption: declared in the rentas exentas section via the pro-rated days method.
- REBECA 50% exemption: exempt 50% excluded from rendimientos integros at source.
- All maritime exemption pathways flow through the existing renta exenta framework.

Modelo 130 (fractional payment, actividades economicas):
Modelo 130 is for self-employed workers under estimacion directa. Salaried crew
(tripulantes por cuenta ajena) are not within its scope. Only fishing vessel owners
operating as autonomos interact with Modelo 130. Art. 30.2.5.c LIRPF gastos de
manutencion caps (26.67/48.08 EUR daily) apply to their deductible expenses.

Modelo 111 (employer withholding returns):
Employers of maritime crew file quarterly. Where REBECA applies, employer withholds on only
50% of gross pay. Where Art. 7.p) applies, the exemption is typically claimed by the worker
on Modelo 100 rather than reducing the employer withholding at source.

### 7. Profile Fact Extension -- Scope Assessment

A profile fact worker_class: trabajador_del_mar would gate the binding selector at:
- Art. 7.p) eligibility: vessel_flag != ES AND waters == international
- REBECA eligibility: vessel_registry == REBECA OR scheduled_canary_route
- DA 41 eligibility (future, inactive): tuna_fleet AND pending EU clearance
- Mandatory filing obligation: RETMAR registration overrides standard income thresholds
- Art. 9 RIRPF dietas applicability: conditional on actual displacement from enrolment
  vessel, with TEAC-confirmed restriction that aboard-vessel allowances may not qualify

The most tractable and legally grounded binding variation is the Art. 7.p) pathway.

### 8. Social Security Regime Interaction

RETMAR (Regimen Especial de la Seguridad Social de los Trabajadores del Mar), governed
by Ley 47/2015 (BOE-A-2015-11346): since January 2023, all workers registered in RETMAR
must file an IRPF declaration regardless of income level. Standard thresholds do not apply.
This affects profile completeness requirements but has no direct impact on casilla wiring.
---

## Legal Reference Inventory (BOE-grounded)

| Provision | Subject | BOE reference |
|---|---|---|
| Ley 35/2006, Art. 11.2 | Income individualisation: work income attributed to earner | BOE-A-2006-20764 |
| Ley 35/2006, Art. 7.p) | Work abroad exemption, annual cap 60,100 EUR | BOE-A-2006-20764 |
| Ley 35/2006, Art. 17.1.d) | Dietas exceptuadas de gravamen (employment income) | BOE-A-2006-20764 |
| Ley 35/2006, DA 24 | Withholding on January 2015 work income (NOT maritime) | BOE-A-2006-20764 |
| Ley 35/2006, DA 41 | Tuna fleet crew 50% exemption (pending EU, inactive 2024) | BOE-A-2006-20764 |
| Real Decreto 439/2007, Art. 9 | Daily dieta caps: 26.67/53.34 national, 48.08/91.35 abroad | BOE-A-2007-6820 |
| Ley 19/1994, Arts. 73-75 | REBECA 50% exemption for Canary Islands vessel crews | BOE-A-1994-16100 |
| Ley 47/2015 | RETMAR: mandatory IRPF filing for all registered sea workers | BOE-A-2015-11346 |
| Ley 26/2014 | Reform of LIRPF introducing current Art. 11 structure | BOE-A-2014-12327 |
| Real Decreto 142/2024 | 2024 RIRPF amendments on withholding | BOE-A-2024-2249 |
| Orden HFP/792/2023 | Revised daily dieta amounts (effective 1 August 2023) | BOE-A-2023-16461 |
| STS 954/2020 | Dietas: employer bears proof burden | Tribunal Supremo |
| STS 3185/2021 | Dietas: employer bears proof burden (confirmed) | Tribunal Supremo |
| TEAR Galicia, Dec 2024 | Art. 7.p) valid for Galician fishing crew | Regional TEAR |
| TEAC ruling | Armada naval allowances do NOT qualify as Art. 9 RIRPF dietas | TEAC |

---

## Conclusion -- Recommended ADR Scope

1. DA 24 is not a valid axis anchor. The task description contains a labelling error.
   No ADR should assert DA 24 establishes a maritime dieta exemption.

2. The tractable new registry axis is a worker_class profile fact that gates:
   - Art. 7.p) exemption eligibility (vessel flag + waters combination).
   - REBECA 50% exemption eligibility (Canary Islands vessel registry).
   - Mandatory filing obligation (RETMAR registration, since January 2023).

3. DA 41 can be modelled as a future binding variant, clearly marked as inactive pending
   EU clearance, with legal_refs preserved for when it becomes operative.

4. Casilla wiring for Modelo 100 flows through the existing renta exenta framework. No
   new casilla exists specifically for maritime workers. The profile fact changes which
   exemption pathway the engine evaluates, not the casilla identifier.

5. The campaign must NOT claim to implement dietas a bordo as a distinct exemption with
   a fixed statutory per-diem. No such provision exists in any currently applicable LIRPF
   disposicion adicional. The Art. 9 RIRPF caps apply generically to qualifying
   displacement, and the TEAC has narrowed their scope for workers whose workplace is the
   vessel itself.