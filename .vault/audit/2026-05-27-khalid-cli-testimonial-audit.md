---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-eva-cli-testimonial-audit]]"
  - "[[2026-05-27-david-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-11 Khalid Mansour Bouazizi barbería estimación objetiva`

## Scope

Eleventh testimonial round, Khalid Mansour Bouazizi — Moroccan-Spanish
autónomo running a barbería in Granada. Régimen tributario:
**estimación objetiva (módulos)** for IRPF (M131 quarterly + M100
annual) and **régimen simplificado** for IVA (M303 quarterly + M390
annual). IAE 972.1 (peluquería de señoras y caballeros). Three
personnel units (2 employees + self), 60m² locale, 5.5 kW power. Now
filing Q2 2024 via this CLI for the first time.

Exercises the EO calculation surface and the régimen simplificado
IVA surface, both of which had not been exercised in prior rounds.

## Findings

### CRITICAL — EO motor produces €0 with módulos informed, silent

With `modulo-1-unidades=3` (personal), `modulo-2-unidades=60` (m²),
`modulo-3-unidades=5.5` (kW) and `actividad-1-porcentaje=20`,
`aeat app modelo work calculate --modelo 131 --year 2024 --period 2T`
returns casillas 01 / 04 / 13 / 15 all `0.00`. Expected for
peluquería IAE 972.1 with 3 personnel units per AEAT 2024 tables:
~€310-650 pago fraccionado after índices correctores. No error, no
warning, no validation that EO cuota cannot be €0 with all módulos
informed.

### CRITICAL — Módulos exposed as unlabeled black boxes

Bindings `modulo-1-unidades` through `modulo-7-unidades` are
generic `decimal` slots with no semantic name. The Orden ministerial
EHA/672/2007 + annual updates assign concrete signos to each módulo
by IAE epígrafe: for 972.1 — personal empleado, superficie del local
(m²), potencia eléctrica (kW). The CLI does not resolve epígrafe IAE
to module names; the user must guess which signo belongs in which
slot. Swapping kW into the superficie slot or vice versa produces
arbitrary cuotas with zero detection.

### CRITICAL — `modulo-N-rendimiento-neto` as manual input not table-driven

In estimación objetiva, rendimiento neto per unit of módulo is
fixed by Hacienda in annual tables (€/unit per actividad). It is
NOT a contribuyente input. The CLI exposes both
`modulo-N-unidades` AND `modulo-N-rendimiento-neto` as manual
inputs — when the user leaves rendimiento-neto at zero (the
default), the cuota silently zeroes regardless of unidades.
Engine should compute `rendimiento = unidades × tarifa_tabla`
using embedded AEAT tables, not request both as inputs.

### CRITICAL — M303 régimen simplificado not implemented

M303 bindings are 6 `ledger_iva_aggregation` entries assuming
régimen general. Régimen simplificado liquidación uses the
forfait de módulos IVA (cuota fija per signo) + IVA repercutido
on non-ordinary operations − IVA soportado. None of the
forfait/módulos-IVA bindings exist. Attempting to supply
`--binding modelo-303-iva-repercutido-general-cuota=1260`
returns `caller binding values cannot override bucket-derived
source bindings` — engine assumes ledger-aggregation always
applies. An autónomo en régimen simplificado cannot file M303
correctly through this CLI.

### CRITICAL — M100 2024 registry integrity errors

`aeat app modelo bindings list --modelo 100 --year 2024 --period 0A`
raises registry validation:

- `renta-2024-total-pagos-a-cuenta` formula: source citation
  `boe-modelo-100-2024-form` missing required text `retenciones,
  ingresos a cuenta y pagos fraccionados`.
- Construct `renta-2024-final-settlement` does not include source
  refs `[lirpf-cuota-chain-authority]` required by application
  link `modelo-100-2024-calculation`.

These block the full bindings list from inspection and may abort
calculation paths. The second item directly intersects S361 work
(in-flight) which authors `renta-2024-final-settlement` — the
construct needs the `lirpf-cuota-chain-authority` source_ref
declared.

### CRITICAL — M100 does not connect M131 quarterly pagos a cuenta

M100 bindings include `renta-2024-modelo-111-retenciones-periodicas`,
`renta-2024-modelo-115-retenciones-periodicas`, `renta-2024-modelo-
123-retenciones-periodicas`, `renta-2024-modelo-193-retenciones-
anuales` — but NO `renta-2024-modelo-131-pagos-fraccionados`. An
autónomo who paid four M131 quarterly amounts during the year has
no automatic deducción in casilla 599 of the annual M100. The
first M100 binding `renta-2024-modelo-100-estimacion-directa-es-normal`
of type `EstimacionDirectaModalidad` further suggests M100 is
modelled for estimación directa only, not EO.

### HIGH — `--revision` accepted without temporal validation

`aeat app modelo work create --modelo 131 --year 2024 --period 2T
--revision 2026` is accepted without warning. The 2026 revision
carries DANA-specific rules that do not apply to 2024 filings. CLI
should refuse or at least warn when `revision_year > filing_year`.

### HIGH — M390 régimen simplificado missing IVA módulos cuota path

The M390 annual summary requires declaración of the cuota devengada
anual del régimen simplificado (casilla 01) — the sum of four
quarterly forfaits. No binding exists for this; only the previous-
filing pointer to M303 trimestral results, which carry net liquidación
not the régimen-simplificado-specific cuota devengada.

### MEDIUM — Revision discovery requires failed attempt

`aeat app modelo work create --help` references `aeat app modelo
describe MODELO` which does NOT exist. The error message on an
incorrect revision lists available revisions, but only after a
failed attempt. Proactive discovery surface needed.

### LOW — Windows PowerShell vs Git Bash env handling

POSIX-style `AEAT_LOCAL_STORAGE_ROOT=... aeat ...` in Git Bash on
Windows produces a Python PermissionError stack trace targeting
`C:\Program Files\Git\mnt`. The error surface is a raw Python
traceback in English rather than a localised "ruta no accesible"
message.

## Recommendations

The EO/régimen-simplificado surface is essentially absent. Five of
the ten findings are CRITICAL — the CLI is unsafe for any autónomo
in módulos régimen. Priority order:

1. **M100 registry integrity errors** (tracked task #167; intersect
   S361 — fix in coordination with the in-flight S361 dispatch).
2. **EO M131 calculation engine** (task #168) — table-driven
   rendimiento neto, semantic módulo labelling per epígrafe IAE,
   cuota-mínima validation. HEAVY scope.
3. **M303 régimen simplificado authoring** (task #169) — separate
   forfait binding set, decoupled from `ledger_iva_aggregation`.
4. **M100 ↔ M131 pagos-fraccionados linkage** (task #170) +
   M100 modalidad recognition for estimación objetiva.
5. **M390 régimen simplificado cuota devengada path** (related to
   #169).
6. **--revision/year validation** (task #171) — small fix.

Quantitatively the EO surface affects every autónomo en módulos —
peluquerías, restaurantes pequeños, taxistas, bares — a large filer
population. The defect-of-record concept (refusal stub with
explanatory message naming the gap) may be appropriate here as a
first-stage remediation, given that proper authoring requires
embedding the AEAT módulos tables for each IAE epígrafe.
