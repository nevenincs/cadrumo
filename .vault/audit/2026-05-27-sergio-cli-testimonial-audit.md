---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-eva-cli-testimonial-audit]]"
  - "[[2026-05-27-david-cli-testimonial-audit]]"
  - "[[2026-05-27-khalid-cli-testimonial-audit]]"
  - "[[2026-05-27-lourdes-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-13 Sergio Castro Mendoza SL director corporate filer`

## Scope

Thirteenth testimonial round, Sergio Castro Mendoza — Madrid SL
administrador único + socio único of Castro Consulting SL. Dual-
filer surface: persona física (€72k nómina director + €20k
dividends, retención 35% director + 19% dividends) AND sociedad
limitada (€380k turnover, €95k beneficio antes impuestos, type
reducido 23% Art. 29 LIS, operaciones vinculadas €100k+ threshold).

First exercise of M200 (Impuesto sobre Sociedades), M232
(operaciones vinculadas informativa), M111 (retenciones a trabajo
trimestral), and dividend path through M100 personal — none
previously tested.

## Findings

### CRITICAL — M200 cuota íntegra engine not computed

`aeat app modelo work calculate --modelo 200 --year 2024 --period 0A`
with `00550=95000` (base imponible) yields `DP200014B:00599 = 0.00`.
Even with intermediate casillas forced manually (`00520=23750`,
`DP200014B:00592=23750`, `DP200014B:00601=23750`,
`DP200014B:00603=23750`, `DP200014B:00605=5750`), the final
result casilla stays zero. No `key_figure` for cuota íntegra
(`00562`), cuota ajustada positiva (`00580`), or base imponible
calculada. The entire Modelo 200 liquidation chain is unwired —
the casillas exist (DP200014B qualified namespace) but no formula
graph connects base imponible → tipo → cuota → liquidación.

Affects 100% of Spanish SL declarations. The M200 motor is in
scaffold state only.

### CRITICAL — M100 dividends do not flow to base imponible del ahorro

With `--casilla "0029=20000"` (dividendos íntegros) and
`--casilla "0033=3800"` (retención M123 19% × €20k):
- `0029 = 20000` correctly stored.
- `0040 = 23800`, `0041 = 23800` (subtotals appear).
- `0460 = 0,00` (base imponible del ahorro) — BROKEN.
- `0510 = 0,00` (base liquidable del ahorro).
- Cuota íntegra `0545=11.123,50` + `0546=10.188,67` corresponds
  ONLY to base general; ahorro cuota is zero.

Dividends tribute via base del ahorro per Art. 25 LIRPF with
escala 19%/21%/23%/27%/30%. The €20k completely evade taxation
in this CLI. Parallel to R7 cluster-T but for the ahorro side.
Affects every M100 filer with dividends, intereses, capital
mobiliario.

### CRITICAL — M123 retención does not flow to casilla 0597

Binding `renta-2024-modelo-123-retenciones-periodicas=3800`
declared at calculate time. Casilla `0597` (retenciones e ingresos
a cuenta imputados) returns `0`. The retention is stored but never
reaches the cuota diferencial computation chain. Manual override
to `0596=25200` (director trabajo retención) works arithmetically
in `0610` but only for the trabajo path; capital mobiliario
retentions disappear.

### CRITICAL — M232 related-party rows do not materialise to positional casillas

M232 declares 223 bindings covering up to 5 related-party rows
(página 1 casillas 144-748) and paraísos fiscales (página 2). All
bindings accepted at calculate time without error. Output contains
only 3 casillas: `decl.cnae`, `decl.ejercicio`, `decl.tipo-ejercicio`.
The €72k nómina-director operación vinculada (above €100k threshold
combined with dividends) does NOT appear in any declaración casilla.
Operaciones vinculadas reporting obligation cannot be satisfied with
this motor.

### HIGH — Tipo reducido 23% Art. 29 LIS missing

The 23% reduced rate for small enterprises (INCN < €1M prior year,
Ley 31/2022 Art. 29.1 LIS effective FY2023) has no profile flag, no
binding, and no calculation path. Only `--new-entity-first-two-
profit-periods` flag (15% for new entities, Art. 29.2 LIS) is
modelled. Castro Consulting SL with €380k turnover should tribute
at 23% but the system cannot distinguish.

### HIGH — Reservas Art. 25 LIS + Art. 105 LIS not modelled

Reserva de capitalización (Art. 25 LIS, 10% of incremento de
fondos propios — up to €19k for Castro Consulting SL's
€95k base) and reserva de nivelación pymes (Art. 105 LIS, 10%
deferral) have no binding or casilla input path. Casillas in
range 00545-00549 (capitalización) and 01033-01036 (nivelación)
exist in the registry but stay zero — no inputs accepted.

### HIGH — `irpf-impatriados.toml` corpus-pending review_status collapses modelo list

`Error: irpf-impatriados.toml: invalid legal reference 'ley-35-2006:art-93':
review_status Input should be 'reviewed', input_value='pending_corpus'`
breaks `aeat app modelo list` and `bindings list` once the legal-
entity profile activates. Same family of corpus-state-blocking
bugs as the M721 corpus-pending issue (#173). A reference in
`pending_corpus` review status must not abort production
operations.

### HIGH — M111 does not distinguish director (Art. 101.3) vs empleado (Art. 86 RLIRPF)

Casillas 16-18 of M111 are AEAT-labelled for "rendimientos trabajo
administradores y miembros consejos administración" (fixed 35% per
Art. 101.3 LIRPF, or 19% if INCN < €100k). The CLI accepts any
retention percentage in casilla 18 without verifying it matches the
required statutory rate for the casilla 16-18 type. A user
incorrectly applying the progressive tabla to a director's
retención goes unwarned.

### HIGH — Director retención Art. 101.3 LIRPF missing from M100 path

Sergio's perfil natural_person carries `irpf_income_categories=trabajo`
but no axis captures that he is an administrator. No `--administrator`
flag, no `administrator: bool` profile field, no binding mapping the
35% fixed retention to a M100 verification. An asesor introducing a
15-20% retention for a director receives no alert.

### MEDIUM — Profile SL: bases imponibles negativas pendientes de compensar absent

No flag for negative bases pending compensation from prior exercises
(Art. 25.1 LIS allows BIN compensation up to 70% of base positiva
or €1M). Constitutive M200 data.

### MEDIUM — Text-type casilla rejects decimal without suggesting correct casilla

`--casilla "0001=72000"` rejected (correctly — 0001 is text-type
contribuyente identifier from #174 guard). Diagnostic does NOT
suggest casilla 0003 as the trabajo income target. Operator
without external guidance is stuck.

### MEDIUM — Aportaciones plan de pensiones individual + empleo (Art. 51/52) not modelled

No casilla or binding for €1.500 individual plan (Art. 51 LIRPF)
or €10.000 empleo plan (Art. 52 LIRPF post Ley 12/2022). Up to
€11.500 deduction unavailable; ~€5-6k cuota reduction unavailable
for a high-marginal-rate director.

### MEDIUM — `work create` does not confirm active profile

Created a M232 unit at the wrong bucket (sergio-castro instead of
castro-consulting-sl) because active profile context was not
surfaced at work_create time. No advisory on which profile owns
the new unit.

### MEDIUM — M100 emits no `result_ingresar` / `result_devolver` role

M111 surfaces explicit `result_ingresar` key_figure with role. M100
returns only signed `0610` for the operator to interpret manually.
UX inconsistency.

### LOW — M111 output casillas 16-18 lack semantic labels

Output prints casilla numbers + values but no description of which
casilla is administrador vs empleado vs other.

### LOW — M232 CNAE binding missing from profile

Field always emits 0 unless manually supplied; profile axis exists
(`actividad_principal_cnae`) but not wired.

### LOW — `aeat app overview status --profile` not accepted

Operator must switch active profile context to query each profile's
status. For dual NP+LE operators (every SL administrator), painful.

## Recommendations

The four CRITICAL findings collectively make the CLI unsafe for
SL administradores — the largest small-business filer class in
Spain (over 1M actively-trading SLs):

1. **C2 + C3 (M100 dividend path + M123 retención flow):** highest
   operational priority. Affects EVERY M100 filer with dividend or
   capital mobiliario income. Parallel to R7 cluster-T for the
   ahorro chain.

2. **C1 (M200 cuota engine):** structural — M200 is in scaffold
   state, no liquidation chain. Authoring the full chain (base →
   tipo → cuota → ajustes → liquidación → pagos fraccionados
   deducción → resultado) is HEAVY but unblocks Spanish corporate
   filing.

3. **C4 (M232 row materialisation):** binding-to-positional-casilla
   mapping missing. Specific to operaciones vinculadas surface.

4. **H1 + H2 (tipo reducido 23% + reservas LIS):** depends on C1
   (no point in tipo reducido if cuota chain doesn't compute), but
   the profile axis can be added independently.

5. **H3 (`irpf-impatriados.toml` corpus block):** same family as
   #173 — review_status `pending_corpus` should not abort production
   operations.

6. **H4 + H5 (director Art. 101.3 retención):** profile axis
   `administrator: bool` + verification surface.

Total uncovered Spanish-tax surface from this round is substantial:
M200 entirely scaffold, M232 entirely scaffold (despite 223 bindings
defined), dividend path in M100 broken, director-régimen unmodelled.
