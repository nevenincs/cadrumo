---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-marcos-cli-testimonial-audit]]"
  - "[[2026-05-27-pedro-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-22 Diego Garrido sports professional M130 acumulación`

## Scope

Twenty-second testimonial round, Diego Garrido Vázquez — Valencia,
29, tennis coach + ACB referee. EDS régimen + retención fija 15%
(Art. 101.6 LIRPF deportivo/artístico). 2024: €40k sport income +
€4.5k artistic + €12k online coaching = ~€56.5k bruto. Retención
M111 €6,675 + Patreon non-retained. Exercises M130 quarterly +
M100 annual interaction, Art. 110.3.b RIRPF exemption rule, EDS
gastos difícil justificación.

## Findings

### CRITICAL — M130 casilla 15 (pagos fraccionados anteriores) silently ignored

Across 1T/2T/3T/4T, `--casilla "15=<importe>"` was silently zeroed.
3T case: pasé `--casilla "15=2694"`, motor returned `casilla 15 = 0`,
`casilla 16 = 5006` (correct), `casilla 17 = 2594` instead of −100.
Diego pays €2,594 per quarter that should be 0. Annual overpayment
~€8,288.

Casilla 15 likely configured as `computed` with `previous_filing`
source but the engine silently rejects `--casilla` overrides for
computed casillas without warning. Asymmetric: casilla 16 (also
`previous_filing` conceptually) accepts overrides.

Affects every autónomo en EDS / EO filing quarterly M130 — every
quarter after 1T, the cumulative deduction breaks.

### CRITICAL — M130 → M100 binding (casilla 0604) entirely absent

`bindings list --modelo 100` shows M111/M115/M123/M193 retención
bindings but NO `renta-2024-modelo-130-pagos-fraccionados`.
Casilla 0604 (pagos fraccionados M130 reflected in M100) stays 0
in calculate output regardless. Diego with €8,288 M130 paid →
M100 ignores it → cuota diferencial overcharged €8,288.

Affects EVERY autónomo en EDS / EO filing M100 annual — universal
double-payment hazard. Confirms Khalid round-11 finding (#170) but
extends scope: not just EO modules; EDS also affected.

When trying to override manually: `--casilla "0604=8288"` triggers
CLI total crash (separate finding H7 below).

### CRITICAL — `aeat app modelo project` non-functional

`aeat app modelo project` to project M100 from M130 quarterlies
fails:
`Invalid value: M100 projection calculation failed: computed
registry casillas cannot be supplied as inputs: ['0505']`

The project verb internally injects computed casilla 0505 (base
liquidable general sometida a gravamen, post-S353 computed) as an
input. Self-conflict with the data-type guard. Blocks projection
entirely.

### HIGH — Art. 110.3.b RIRPF 70%-retenciones exemption rule not implemented

When retenciones acumuladas ≥ 70% of rendimientos netos, the
contribuyente is EXEMPT from M130 filing (Art. 110.3.b RIRPF).
Motor produces negative `casilla 17` saldo (e.g., −7,900) instead
of 0 + exemption notice. Diego with 100%-retained referee income
needs this exemption — gets a fake negative balance instead.

### HIGH — Art. 101.6 LIRPF (deportivo/artístico) not distinguished from Art. 101.5

Profile has `--professional-income-withholding-ge-70pct` (M130
exemption-threshold flag) but no axis for Art. 101.6 sport/art
retención specifically. Art. 101.5 (general profesional 15%) and
Art. 101.6 (sport/art 15%) have different interactions with
irregular-income reglas. The fixed-15% retención does not capture
the article distinction. Add `--irpf-activity-article` axis.

### MEDIUM — Casilla 0114 nomenclature confusion

Diego expected casilla 0114 ("retenciones e ingresos a cuenta sobre
rendimientos actividades económicas" per M111 cross-reference) but
M100's actual casilla is 0599. Casilla 0114 in M100 is unrelated.
Cross-modelo nomenclature confusion. CLI should accept the
"expected" casilla numbers from BOE M111 → autoroute to M100
casilla.

### MEDIUM — `aeat app modelo project` lacks `--output-language`

Per Lourdes F12 / Marcos pattern — flag inconsistency.

### CLI-LEVEL — `UnmatchedPlaceholderError` import-order race (separate task)

After multiple `--casilla` injection attempts on computed casillas,
CLI module imports started failing:
```
ValueError: AeatError subclass aeat.core.i18n._render.UnmatchedPlaceholderError
is missing a declared ErrorCode registry entry
```

Class IS registered in `src/aeat/core/errors/registry/_core.py:117`.
The race appears to be a class-init ordering issue: `_render.py`'s
class-definition assertion fires BEFORE the registry list is loaded
in some import paths. Concurrent agent activity may interleave with
the CLI's own initialization.

NOT a regression from a recent commit (last touch to `_render.py`
is b17876feb, weeks old). Stale `__pycache__` is a plausible trigger.

Filed as separate task #217.

### POSITIVE — Several elements work correctly

- Casilla 16 (retenciones acumuladas) DOES accept overrides.
- Casilla 0599 (M100 actividades retenciones) DOES accept manual.
- Gastos difícil justificación 5% Art. 30.2.4ª LIRPF cap at €2k
  works correctly via casilla 1579 + 0222.
- `--professional-income-withholding-ge-70pct` flag exists and
  persists.

## Recommendations

Priority order:

1. **M130 casilla 15 (#218) CRITICAL** — fix the silent override
   rejection. Either accept `--casilla` overrides for `computed`
   casillas when no `previous_filing` source is available, OR
   surface a clear error explaining the override is not accepted
   and pointing to the binding pathway.

2. **M130 → M100 binding (#170 elevated)** — same task as Khalid
   #170, now confirmed by Diego. ESCALATE PRIORITY. Every autónomo
   with quarterly M130 affected.

3. **70% exemption rule Art. 110.3.b (#219)** — verification finding
   when retenciones ≥ 70% × rendimientos → casilla 17 = 0 +
   `M130_EXEMPT_HIGH_RETENTION_RATIO` finding.

4. **`modelo project` 0505 crash (#220)** — strip computed casillas
   from input list before projection.

5. **Art. 101.6 axis** — profile field for sport/art activities.

6. **UnmatchedPlaceholderError race (#217)** — investigate
   import-order timing; may require lazy registration or assert-
   on-access pattern.
