---
tags:
  - "#adr"
  - "#trabajador-del-mar"
date: "2026-05-31"
modified: '2026-06-29'
related:
  - "[[2026-05-31-trabajador-del-mar-research]]"
---

# trabajador-del-mar adr: maritime-worker-irpf-axis | (**status:** accepted)

## Problem Statement

The AEAT IRPF engine has no mechanism to vary exemption pathways or mandatory-filing
rules for workers in the Spanish merchant marine and fishing sector (trabajadores del
mar). Three legally distinct provisions can reduce or exempt income for this worker
class, and since January 2023 all workers registered in RETMAR must file an IRPF
declaration regardless of income level. The engine currently treats all employment
income identically, producing incorrect casilla selections for maritime taxpayers.

The task brief cites DA 24 LIRPF as the governing provision. This is incorrect:
DA 24 LIRPF is "Retenciones sobre rendimientos del trabajo correspondientes a enero
de 2015" -- a transitional withholding rule with no maritime content. The correct
legal anchors are Art. 7.p) LIRPF, REBECA (Ley 19/1994 Arts. 73-75), and DA 41
LIRPF (inactive). This ADR re-scopes accordingly.

## Considerations

### Active legal provisions for 2024/2025

**Art. 7.p) LIRPF (Ley 35/2006, BOE-A-2006-20764)**
Primary exemption pathway. Conditions:
- Work effectively performed outside Spanish territory (international waters qualify
  for foreign-flagged vessels in AEAT accepted practice).
- Foreign entity receiving services is non-resident in Spain or has a permanent
  establishment abroad.
- Territory has an equivalent income tax or CDI with Spain.
- Annual cap: 60,100 EUR.
- Calculation: annual salary / 365 x qualifying days abroad.
- Confirmed by TEAR Galicia December 2024 for Galician fishing crew.
- Extended April 2025 by Supreme Court doctrine to military Navy in NATO/UN sea ops.

**REBECA -- 50% exemption (Ley 19/1994, Arts. 73.2, 73.3, 75.1, 75.3, BOE-A-1994-15794)**
For crew of vessels enrolled in the Canary Islands special shipping register or on
scheduled routes between the Canary Islands and mainland Spain:
- 50% exemption on gross employment income from navigation.
- Since 1 January 2021: extended to crews of REBECA-registered company vessels in
  other EU/EEA member state registries.
- Exempt 50% is excluded from the Modelo 111 withholding base by the employer.

**DA 41 LIRPF (Ley 35/2006, added by Ley 6/2018, BOE-A-2006-20764) -- INACTIVE**
50% exemption for tuna fleet crew on Spanish-flagged fishing vessels:
- Registered in the community fishing fleet register.
- Fishing exclusively tuna or related species outside EU waters AND at least 200
  nautical miles from member state baselines.
- Shipowning company in the Special Register of Spanish Fishing Vessel Companies.
- Status: requires prior EU state-aid clearance; not granted as of 2024/2025.
- AEAT confirms non-applicability in official 2024 guidance.
- Must be modelled as a future binding variant, clearly marked inactive.

**RETMAR mandatory filing (Ley 47/2015, BOE-A-2015-11346)**
Since January 2023, all RETMAR-registered workers must file IRPF regardless of
income level. This affects profile completeness gates, not casilla wiring.

### Provisions that do NOT apply

**Art. 11.2 LIRPF**: General income individualisation rule. Maritime-relevant only
structurally (vessel flag and waters determine which further provision applies), but
contains no maritime carve-out or exemption. Not a binding axis anchor.

**Art. 17.1.d) LIRPF + Art. 9 RIRPF (dietas framework)**: Daily caps apply
(26.67/53.34 EUR national, 48.08/91.35 EUR abroad, per Orden HFP/792/2023,
BOE-A-2023-16461). However the TEAC has ruled that aboard-vessel allowances paid to
crew whose ordinary workplace IS the vessel do NOT qualify as Art. 9.A.3.b) RIRPF
dietas. Employer bears proof burden per STS 954/2020 and STS 3185/2021. No special
maritime per-diem exists in any currently applicable LIRPF disposicion adicional.

**DA 24 LIRPF**: Transitional January 2015 withholding rule. Zero maritime content.
Must not be cited as a maritime exemption anchor in any registry or code artefact.

## Constraints

- No new casilla identifiers exist for maritime workers in Modelo 100. All exemption
  pathways flow through the existing renta exenta framework. The profile fact changes
  which exemption pathway the engine evaluates, not the casilla identifier.
- DA 41 must not be treated as active. Modelling it as a future variant preserves
  legal_refs for when EU clearance is granted; activating it prematurely would produce
  incorrect tax output.
- The dietas a bordo framing in the task brief cannot be honoured: no such statutory
  per-diem exists in any currently applicable LIRPF provision. The Art. 9 RIRPF caps
  apply generically and the TEAC has narrowed their scope for aboard-vessel workers.
- RETMAR mandatory filing is a profile completeness rule, not a calculation axis.
  It must not affect casilla values or formula execution paths.
- legal_refs and source_refs must be carried through every domain boundary per the
  aeat-calculation-grounding rule. No typed observation may drop provenance.
- Edits are constrained to: _data/registry/, domain/renta/, application/calculations/.
  No other module boundaries may be crossed.
## Implementation

### 1. Profile-fact schema extension

A new profile fact worker_class with value trabajador_del_mar gates the binding
selector at the three active exemption axes:
- art_7p_eligible: vessel_flag != ES AND waters == international
- rebeca_eligible: vessel_registry == REBECA OR scheduled_canary_route
- da41_eligible (future, inactive): tuna_fleet AND pending_eu_clearance
- retmar_mandatory_filing: RETMAR registration overrides standard income thresholds

The profile fact is declared in the registry profiles TOML. The binding selector
resolves the correct exemption pathway from the fact tuple.

### 2. Registry binding wiring

Registry TOML additions under _data/registry/aeat/categories/:
- A trabajador_del_mar category grouping the three exemption variants.
- Art. 7.p) binding entry: daily_rate = annual_salary / 365, cap = 60100,
  legal_refs = ["Ley 35/2006 Art. 7.p) BOE-A-2006-20764"].
- REBECA binding entry: exempt_fraction = 0.50,
  legal_refs = ["Ley 19/1994 Arts. 73.2 73.3 75.1 75.3 BOE-A-1994-15794"].
- DA 41 binding entry: exempt_fraction = 0.50, status = inactive_pending_eu_clearance,
  legal_refs = ["Ley 35/2006 DA 41 BOE-A-2006-20764", "Ley 6/2018 BOE-A-2018-9268"].

### 3. Calculation engine integration

In domain/renta/, the exemption engine receives the resolved binding and produces
a CasillaObservation for the applicable renta exenta casilla. Typed observations must
carry legal_refs and source_refs from the registry entry to the CLI surface.

Art. 7.p) calculation: exempt_amount = min(annual_salary / 365 * qualifying_days, 60100)
REBECA calculation: exempt_amount = gross_navigation_income * 0.50

DA 41 calculation is defined but gated: the engine raises a domain error if
da41_eligible resolves to True (since it is legally inactive and must not silently
produce an incorrect result).

### 4. Modelo 100 / Modelo 111 casilla wiring

Modelo 100: Art. 7.p) and REBECA exemptions flow through the existing renta exenta
section. No new casilla slug is created. The existing exempt income casilla receives
a CasillaObservation with the relevant legal_refs.

Modelo 111: Where REBECA applies, the employer-side registry entry flags that
withholding applies to 50% of gross pay. This is wired through the Modelo 111
binding entry, not a new casilla.

### 5. Locales

New locale keys for the worker class selector and each exemption variant. Locale
scaffolding via python -m aeat.locales scaffold per project convention.
## Rationale

Art. 7.p) is the primary and most tractable axis: it has a clear statutory formula,
an annual cap, an active Supreme Court / TEAR Galicia confirmation trail, and maps
directly to the existing renta exenta casilla path.

REBECA is the second active axis: the 50% exempt fraction is statutory, employer-side
wiring through Modelo 111 is confirmed in AEAT guidance, and the 2021 extension to
EU/EEA sister-registry vessels is documented in Ley 19/1994.

DA 41 is modelled but gated inactive. Its legal_refs are preserved so that when EU
clearance is granted, activation requires only a status flip and a test, not a schema
change.

The dietas a bordo framing is explicitly rejected. There is no statutory per-diem
for civilian maritime workers in any currently applicable LIRPF provision. Building
an exemption axis on a non-existent norm would produce legally incorrect output and
expose the system to compliance liability.

## Consequences

- The worker_class profile fact introduces a new selector dimension. Existing
  taxpayer profiles without this fact are unaffected (selector falls through to
  the standard employment income path).
- DA 41 must be re-visited when EU state-aid clearance is granted. A follow-up
  task must be raised at that point to flip the inactive status and add oracle-backed
  tests.
- RETMAR mandatory filing is surfaced as a profile completeness warning, not a
  blocking validation. Downstream CLI output must communicate the mandatory-filing
  status to the operator.
- The dietas a bordo axis from the task brief is formally closed as legally
  unfounded. The research document 2026-05-31-trabajador-del-mar-research.md
  records the full evidentiary basis for this decision.
- All new CasillaObservation rows produced by this axis must pass the
  aeat-calculation-grounding provenance requirement: legal_refs and source_refs
  populated from the registry binding entry, carried through to CLI JSON emit.
