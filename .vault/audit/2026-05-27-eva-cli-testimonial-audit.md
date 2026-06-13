---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-26-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-10 Eva Carrillo Soto cryptocurrency operator`

## Scope

Tenth testimonial round, focused on cryptocurrency operator persona. Eva
Carrillo Soto, asalariada with €52k gross salary plus crypto/DeFi/NFT
operations on foreign exchanges (Binance, Kraken, Aave) above the
€50k informativa threshold. Exercises M100 ganancias patrimoniales
cripto path (casillas 1804-1814), M720 foreign-asset declaration,
M721 cryptocurrency informativa, M714 patrimonio. Re-runs R7
cluster-T and R8/R9 spot-checks.

## Findings

### CRITICAL — R7 cluster-T cuota tarifa general STILL OPEN

Casillas 0532/0533 (cuota base liquidable general estatal / autonómica)
return `0.00` even though `0500 = 52000` (base liquidable general
correctly populated from €52k salary). The progressive tarifa is NOT
applied to the general base. Casillas 0545/0546 (cuota íntegra) carry
only the ahorro portion ~€305 each. Effective tax rate on €52k salary
computes as 0% on the general portion, confirming the R7 cluster-T
finding is still entirely open. Affects every M100 filer with salary
income; likely the upstream root cause of the S361 chain emptiness.

### CRITICAL — Modelo 721 (criptomonedas extranjero) entirely absent

`aeat app modelo work create --modelo 721` fails with `Invalid value:
Modelo desconocido 721`. M721 is the cryptocurrency informativa
introduced by Orden HFP/887/2023, obligatory from FY2023 for foreign-
exchange balances above €50k. Régimen sancionador severo (multa
mínima €5.000 per undeclared data set). A taxpayer with Binance or
Kraken holdings above threshold confiding in this CLI incurs grave
infraction with zero CLI warning. Confirms Eva round-9 finding;
remediation tracked as Path-B refusal stub.

### CRITICAL — Modelo 714 (Patrimonio) entirely absent

`aeat app modelo work create --modelo 714` fails identically. M714 is
the Patrimony autoliquidation under Ley 19/1991, obligatory for
patrimonio neto above €600k in Comunitat Valenciana (autonomic
threshold; €700k–€1M in other CCAAs). A wealthy crypto operator with
combined holdings above the threshold has an autoliquidación
obligation that this CLI cannot assist at all.

### HIGH — Foreign-source distinction and double-taxation credit absent

The €180 DeFi yield on Aave (US-domiciled protocol) is foreign-source
rendimiento del capital mobiliario. Art. 80 LIRPF and OECD convention
require integration with possible deducción por doble imposición
internacional. The CLI does not distinguish Spanish-source from
foreign-source rendimientos in any binding or casilla mapping. No
binding of the type `renta-2024-deduccion-doble-imposicion-
internacional`. The €180 either disappear or pile into 0033 without
source distinction; the foreign tax credit cannot be applied.

### MEDIUM — Casilla 1812 manual auto-propagation gap

Casilla 1811 (ganancia no exenta) computes correctly to €8.500.
Casilla 1812 (ganancia imputable a 2024) is `input_kind = "manual"`:
the operator must duplicate the value. Without explicit `--casilla
"1812=8500"`, aggregates 1813/1814 stay zero and the entire crypto
gain disappears from base imponible del ahorro silently. AEAT form
behavior is that 1812 defaults to 1811 unless multi-year deferral
under Art. 14.2.d LIRPF; either flip 1812 to computed identity, or
surface a verification finding when 1811 > 0 and 1812 = 0.

### MEDIUM — Capital mobiliario does not flow to base del ahorro

Casilla 0033 (rendimientos capital mobiliario, imposición de
capitales) accepts the staking €600 and flows correctly to 0041 (suma
capital mobiliario base del ahorro). However casilla 0460 (base
imponible del ahorro) carries only the €8.500 from ganancias
patrimoniales; the €600 capital mobiliario component does NOT appear
summed. Aggregation channel from 0041 to 0460 inactive or
misconfigured for this revision.

### MEDIUM — NFT classification guidance absent

NFT transmissions tribute as transmisiones de elementos patrimoniales
in the 1804-1814 monedas-virtuales block per AEAT 2024 manual.
The CLI gives zero indication of this classification; an operator
without external guidance could route NFTs into 0386 (otros elementos
patrimoniales) producing a technically incorrect declaration.

### LOW — M720 is bindings container without semantic abstraction

M720 catalog entry exists; work_create succeeds. However the 49 bindings
are all `manual_input` with identifiers like `modelo-720-2013.type_2.
77-101.tipo-de-titularidad-sobre-el-bien-o-derecho` — direct BOE
record-design nomenclature without any semantic abstraction. No
threshold validation (€50.000), no category separation (cuentas /
valores / inmuebles), no asistente. Functional as a binding store;
does not replace the AEAT form workflow.

### LOW — Extemporaneidad warning absent (R9 re-confirm)

Plazo ordinario para Renta 2024 was 30 June 2025. The simulation
date is May 2026. The CLI emits no extemporaneidad advertencia and
applies no recargo automation (Art. 27 LGT) at `work create` or
`calculate` time. Confirmed open.

### POLISH — `work create` requires explicit `--revision` without discovery

Signature requires explicit `--revision 2024` (M100) or
`--revision 2013-y-siguientes` (M720). Without prior exploration of
`aeat app modelo bindings list`, an operator has no way to know
which revision identifier to pass. Surface a `default-latest` flag
or print the available revisions in the error message.

## Recommendations

The most operationally important finding is R7 cluster-T — every
M100 salary filer computes 0% effective on the general base. This
dwarfs the S361 settlement-chain tail in scope: S361 fixes 0587-0670
chain, but if 0532/0533 are zero, the entire calculation is wrong
upstream of S361. Architecture grounding required before any
remediation: confirm the 2024 state-scale `lookup_bracket` formulas
exist and are wired to the 0500 → 0532 path. Compare against the
2023 (`d64dfb7ff`) and 2025 (`6eda54425`) wiring commits.

Path-B refusal-stubs for M721 (already tracked) and M714 (new task)
are cheap defects-of-record that eliminate the silent-misrouting
hazard without requiring AEAT corpus PDFs.

The 1812 auto-propagation gap is a small targeted fix that removes
a real footgun for any crypto declarant.

The foreign-source / double-taxation-credit gap is the largest
authoring task uncovered — requires either a new `source_country`
attribute on rendimientos bindings or a dedicated
`renta-deduccion-doble-imposicion-internacional` construct mapped
to casillas 0588-0594.
