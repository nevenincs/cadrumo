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
---

# `cli-testimonial` audit: `round-12 Lourdes Etxebarria Aguirre pareja de hecho separación custodia compartida`

## Scope

Twelfth testimonial round, Lourdes Etxebarria Aguirre — Bilbao
resident, vasca, recently separated after 5-year pareja de hecho.
Two minor children with custodia compartida 50/50. Income €38k
salary + €4k freelance translation. Exercises three previously-
untested surfaces: **foral régimen** (País Vasco — Hacienda Foral
de Bizkaia, not AEAT), **pareja de hecho unidad familiar** (Art. 82
LIRPF), and **prorrata custodia compartida** (Art. 59 LIRPF). Also
re-tests R7 (cuota tarifa) and R9 (extemporaneidad).

## Findings

### CRITICAL — País Vasco + Navarra absent from CCAA enum; silent Madrid default

`aeat config profile create --tax-residence-ccaa pais_vasco` returns
`'pais_vasco' is not one of 'andalucia', 'aragon', ..., 'murcia'`.
País Vasco and Navarra are both absent from the enum — the two
foral CCAAs representing ~9% of the Spanish population.

When the field is omitted, the profile silently gets
`tax_residence.ccaa = madrid`. A Bilbao resident proceeding without
catching this assigns to Madrid autonomic scale and tariff. The
foundational defect is that the AEAT system itself is the wrong
authority for foral residents — they file with Hacienda Foral de
Bizkaia / Gipuzkoa / Álava under Concierto Económico. The CLI should
either (a) refuse foral CCAAs with a clear redirect message, or (b)
enable a stub explicit-refusal mode for foral declarations.

### CRITICAL — Actividad económica €4k produces base imponible −€4k

`calculate --casilla "0001=38000" --casilla "0006=4000"` yields:
- `0007 = -4000`
- `0432 = -4000` (saldo neto rendimientos)
- `0435 = -3000` (base imponible general)
- `0500 = -3000` (base liquidable general)
- `0545 = 0.00` (cuota íntegra)

Expected: positive base imponible ≈ €42k, cuota ≈ €5-6k progressive
estatal. The motor treats `0006` (actividad económica) input as a
loss not a positive rendimiento neto. Cuota silently zeroes via
negative base. May be a casilla-routing defect distinct from S342
(M130 ledger aggregation). S342 fixed the M130 quarterly flow;
this is the annual M100 actividad económica casilla path.

### CRITICAL — Pareja de hecho unidad familiar (Art. 82 LIRPF) no guidance

No flag, binding, or assistant for the unidad-familiar test:
- Art. 82.1.2º LIRPF requires marriage OR pareja de hecho registrada
  en registro autonómico — a non-registered pareja cannot file
  conjunta.
- Exclusivity rule: in custodia compartida with descendants, only
  one progenitor can integrate hijos in unidad familiar conjunta;
  the other must declare individual.

`--taxation-type 2` (conjunta) is accepted without verifying
marriage/registry status or exclusivity. The CLI cannot quantify
the trade-off conjunta vs individual for Lourdes' situation.

### CRITICAL — Prorrata 50/50 mínimo descendientes (Art. 59 LIRPF) not applied

CLI accepts any value in casillas 0513/0514 (mínimo descendientes)
without verifying or warning about the 50% prorrata rule when
custody is shared. If two progenitores each declare the full
mínimo, AEAT generates a paralela in the cruce de datos. No
`--custodia-compartida` flag, no automatic prorrata, no advisory.

### HIGH — Pensión por alimentos / anualidades por alimentos a hijos missing

No casilla or binding for €300/mo pensión Lourdes pays. The
fiscally-relevant distinction between Art. 64 (pensión
compensatoria al cónyuge) and Art. 65 (anualidades por alimentos a
hijos — separate escala, special tariff) is ignored entirely.
Cuota calculation incorrect for any user with these obligations.

### HIGH — Extemporaneidad warning absent (R9 re-confirmed)

Plazo voluntario M100/2024 closed 30 June 2025. Simulation date
May 2026 (11+ months out). No advertencia of extemporaneidad,
no recargo Art. 27 LGT calculation, no intereses de demora.

### HIGH — `modelo list` and `bindings list` blocked by M721 corpus error

`aeat app modelo list` aborts with M721 source-reference validation
errors (`bytes: Input should be > 0` and `review_status: pending_corpus`).
A non-cripto user cannot list the catalog because of a different
modelo's corpus state. `bindings list` blocked similarly. Tracked
as task #173 territory but elevated by Lourdes — should be its own
HIGH unblock task.

### MEDIUM — Silent Madrid CCAA default when field omitted

If `--tax-residence-ccaa` is omitted entirely, profile silently
assigns `madrid` with no notification. The field should be required,
or the default should be surfaced in the output of `profile create`.

### MEDIUM — Decimal-encoded boolean binding without assistance

`renta-2024-modelo-100-estimacion-directa-es-normal` must be supplied
as `0`/`1` Decimal even though semantically boolean. Error message
when `false` is supplied is technical (`Decimal operands and must be
supplied as Decimal binding values, not through the enum-binding
channel`). Non-technical users cannot decode it.

### MEDIUM — `verify` returns DRAFT_HAS_ERRORS without enumerating errors

`work verify` rejects with `abort_code: DRAFT_HAS_ERRORS` but does
not name which casillas/fields are in error. Dead-end refusal
contract; user has no path forward without external diagnosis.

### LOW — Euskera (eu) absent from output-language enum

Available: `[es|en|ca|hu]`. Hungarian and Catalan are present but
the only co-official lengua of País Vasco is not. Notable absence
for foral-context coverage.

### LOW — `--quiet` not available on `modelo work create`

`profile create` accepts `--quiet`; `modelo work create` does not.
Interface inconsistency.

### POLISH — No introspection of individual casilla description

No CLI verb to display semantic description of a single casilla
before calculation. Operator must read external normativa to know
whether `0006` is "rendimiento neto actividad económica" or
"pérdidas de actividad económica".

## Recommendations

Priority remediation order:

1. **Actividad económica calculation defect** (CRITICAL F4) — investigate
   casilla 0006 routing. May intersect S342 if the casilla-to-binding
   path is shared. New task.

2. **Foral CCAA handling** (CRITICAL F1) — at minimum add `pais_vasco`
   + `navarra` to the enum and refuse with explanatory message
   pointing to Hacienda Foral. Stub pattern matches M721/M714/M151.

3. **Pareja de hecho + custodia + prorrata** (CRITICAL F2+F3) — three
   related schema/binding additions: situación-familiar enum,
   custodia-compartida flag, automatic prorrata. Decompose into a
   dedicated family-régimen wave.

4. **M721 corpus unblock** (HIGH F7) — already in flight as #173,
   elevated priority.

5. **Pensión/anualidades alimentos** (HIGH F5) — Art. 64/65 binding
   pair, separate escala application.

6. **Extemporaneidad** (HIGH F6) — recargo Art. 27 LGT automation +
   advisory at `work create` when current date > plazo voluntario.

The four CRITICAL findings each affect substantial filer populations:
foral residents (~9%), pareja-de-hecho declarants (significant
fraction of working-age cohort post-2015), divorced/separated with
custodia compartida (a growing demographic), and ANY autónomo with
casilla 0006 input (calculation defect blocks correct EDS filings).
