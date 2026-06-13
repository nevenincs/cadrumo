---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-sergio-cli-testimonial-audit]]"
  - "[[2026-05-27-yara-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-15 Mateo Ferrer Sánchez ISD herencia cross-CCAA`

## Scope

Fifteenth testimonial round, Mateo Ferrer Sánchez — Barcelona
resident, 47, autónomo consultant. His mother died Nov 2024 in
Valencia. Three herederos; total caudal ~€653k; Mateo's tercio
~€218k. Bienes: vivienda habitual Valencia + local Castellón +
cuenta corriente + fondo de inversión. Exercises Modelo 650 ISD
+ Modelo 660 informativa caudal + cross-CCAA tariff resolution
(causante Valencia, heredero Cataluña) + autonomic bonificación
99% Valencia Llei 7/2023. Also re-tests M100 capital mobiliario
chain post-defunción.

## Findings

### CRITICAL — M650 (Impuesto sobre Sucesiones) entirely absent

`aeat app modelo list` does not contain M650. `aeat app modelo
work create --modelo 650 --year 2024 --period 0A --revision R1`
returns `Modelo desconocido 650`. No support for:
- Base imponible per heredero (caudal − cargas − deudas − sepelio
  − testamentaría − prorrateo).
- Reducciones Art. 20.2 LISyD (parentesco grupo II €15.956,87 +
  vivienda habitual 95% capped €122.606,47/heredero).
- Escala progresiva estatal 7,65%–34%.
- Coeficiente multiplicador por patrimonio preexistente.
- Bonificaciones autonómicas.

ISD is one of the highest-cuantía tributos for an aging Spanish
demographic (~400k declaraciones M650/year). The defect-of-record
pattern (Path-B refusal stub) applies — same as M721/M714/M151.

### CRITICAL — M660 (informativa caudal relicto) entirely absent

M660 accompanies M650 when sociedades or conjunto declaration
applies. Equally unsupported.

### CRITICAL — Bonificación autonómica ISD not modelled — CCAA-causante determinant

Communitat Valenciana Llei 7/2023 (retroactive 28-may-2023) applies
99% bonificación cuota for Grupo II herederos. This transforms
a ~€20-40k cuota bruta into ~€200-400 effective. Many other CCAAs
(Andalucía, Madrid) apply similar bonificaciones.

The profile schema captures `tax_residence_ccaa` of the DECLARANT
(heredero) — but ISD tariff applicable is by CCAA of the CAUSANTE
(Art. 32 Ley 22/2009). Mateo lives in Cataluña; his mother lived
in Valencia. Valencia normativa applies. No axis captures the
causante's CCAA.

### HIGH — Cross-CCAA tariff resolution structurally missing

The profile assumes one tax-residence CCAA. ISD requires two-CCAA
modelling: declarant + causante. Beyond ISD, the same shape applies
to Impuesto sobre Transmisiones Patrimoniales y Actos Jurídicos
Documentados (ITPyAJD) for inter-vivos transfers where the bien is
in a different CCAA from buyer/seller.

### HIGH — Extemporaneidad Art. 27 LGT undetected

M650 plazo: 6 months from defunción (Art. 67 RISD), prórroga 6
months. Mateo's case: mother Nov 2024, ordinary plazo May 2025;
simulation date May 2026 = 12 months extemporáneo (recargo 15%
+ intereses de demora Art. 26 LGT).

`review queue` returns empty even with overdue borrador units.
`overview status` and `work status` show no plazo warning. Same
gap also reconfirms M100 plazo overdue (R9 cluster Eva/David/Yara).

### HIGH — Reducción vivienda habitual Art. 20.2.c LISyD not implementable

Mother's vivienda habitual: market value €420k → Mateo's tercio
€140k → reducción 95% capped €122.606,47. With mantenimiento 10
years requirement (Art. 20.2.c LISyD). No axis declares which
bien is vivienda habitual; no per-heredero cap arithmetic.

### MEDIUM — Casillas 0300/0301 (capital mobiliario) do NOT propagate to base imponible ahorro

Independently confirms Sergio round-13 C2 (commit `819264e6c`).
Setting `--casilla "0300=25000"` + `--casilla "0301=10000"` leaves
0460 (base imponible del ahorro) and 0510 (base liquidable ahorro)
at 0,00. Capital mobiliario chain to ahorro broken — affects
both dividends (Sergio) AND fund-of-fund yields (Mateo). Task
#181 elevated to extra-critical priority by this re-confirmation.

### MEDIUM — Rendimientos fondo post-defunción guidance missing

Art. 33.3.b LIRPF: adquisición por herencia no genera ganancia
patrimonial for the heredero; but rendimientos generated between
defunción and aceptación accrue to the heredero (renta del trabajo
o capital mobiliario depending on bien type). No CLI context
distinguishes:
- Pre-defunción rendimientos → causante's M100.
- Post-defunción rendimientos → heredero's M100.

### MEDIUM — Binding `enum_typed` with `input_channel=decimal` opaque

`renta-2024-modelo-100-estimacion-directa-es-normal` requires
numeric input but is semantically enum-typed. Same gap surfaced
by Lourdes round-12 F9. Error message describes Decimal vs enum-
binding channel without telling the user the decimal-to-enum
mapping.

### LOW — NIF validation good; NIE coverage unverified

NIF validation correctly rejects wrong control letter with
suggestion. Did not exercise NIE for non-resident heredero
scenarios; coverage unverified.

### POLISH — `modelo list` lacks domain filter

Users searching for "impuesto de sucesiones" without knowing the
code (650) have no discovery path. `--domain isd` filter would
help.

## Recommendations

Priority order:

1. **M650 Path-B refusal stub** (CRITICAL) — same pattern as M721
   (#157), M714 (#159), M151 (#161). Register `"650"` in
   `_STUB_ONLY_MODELOS`, locale message naming Ley 29/1987 ISD +
   plazo Art. 67 RISD + CCAA-causante determinant rule + redirect
   to autonomic Hacienda (or AEAT Sede if estatal régimen).
   Cheap defect-of-record blocking silent misrouting.

2. **M660 Path-B refusal stub** (CRITICAL) — same shape as M650.

3. **Base imponible ahorro chain** (MEDIUM but DOUBLE-CONFIRMED) —
   task #181 elevated. Sergio dividends and Mateo capital mobiliario
   both fail the same way. Fix priority increased.

4. **Cross-CCAA causante axis** (HIGH for ISD, but structurally
   needed for ITPyAJD also) — profile or work-unit context axis
   for CCAA of relevant counterparty (causante for ISD; transmitente
   for ITP).

5. **Extemporaneidad detection** (HIGH) — `review queue` and
   `overview status` should highlight overdue borrador units with
   recargo Art. 27 LGT computation. Family with R9 cluster
   (Eva/David/Yara plazo gaps).

6. **Reducción vivienda habitual + per-heredero caps** (HIGH) —
   depends on M650 authoring. Annotate bienes with
   `es_vivienda_habitual: bool` and compute per-heredero caps.

7. **Enum-decimal binding UX** (MEDIUM) — same family as Lourdes
   F9 + Mateo. Either auto-translate enum-named inputs to decimal,
   or surface the mapping in `bindings list`.

8. **`modelo list` domain filter** (POLISH).

The two most-operationally-critical net-new findings: M650 absence
(structural defect for ~400k filers/year) and base-ahorro double-
confirm (raises #181 to operational-critical from Sergio's
single-persona discovery).
