---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-pedro-cli-testimonial-audit]]"
  - "[[2026-05-27-sergio-cli-testimonial-audit]]"
  - "[[2026-05-27-mateo-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-19 Carla Domínguez Verdejo first-year retiree pension plan rescate DT 12ª`

## Scope

Nineteenth testimonial round, Carla Domínguez Verdejo — Sevilla,
65 (turned 65 March 2024). Recently retired banking executive.
Three pagadores 2024: INSS pensión SS €18k + plan de pensiones
rescate en forma de capital €60k (with €9,600 pre-2007
aportaciones) + cuenta de ahorro intereses €1,200. Total €79.2k
across three pagadores. Exercises retiree path: mayores de 65
mínimo incremento (Art. 57 LIRPF), DT 12ª reducción 40% rescate
capital, multiple-pagadores Art. 96.3 obligation, pension
classification as Art. 17.2.a trabajo.

## Findings

### CRITICAL — Mínimo personal mayores de 65 not derived from birth_date

Profile stores `renta_taxpayer.birth_date = 1959-03-15`. The
declaration registry has a bound casilla `DPFNAC_D` marked
required. But `aeat app modelo bindings list --modelo 100 --year
2024 --period 0A` shows ZERO bindings for birth_date — the
profile field does not project to `DPFNAC_D`. Casilla 0511
(mínimo del contribuyente, parte estatal) returns €5,550 (base)
instead of €6,700 (€5,550 base + €1,150 incremento Art. 57.1.b
LIRPF for 65+).

Impact: €1,150 lower base exenta → €230-345 excess cuota per
filer in this bracket. Affects every Spanish retiree filing M100
in their 65+ first year and onwards (~750k retirees yearly +
existing 65+ population). The most elemental retiree deduction
in IRPF is not auto-derived.

### CRITICAL — DT 12ª reducción 40% rescate plan de pensiones capital silent loss

Rescate en forma de capital of plan de pensiones is rendimiento
del trabajo (Art. 17.2.a LIRPF). Aportaciones pre-31-Dec-2006
qualify for 40% reducción (DT 12ª LIRPF) on the proportional
gross. For Carla: `9,600 / 33,000 × 60,000 × 40% = €6,983.64`
reducción.

The CLI offers NO capture surface for the pre-2007 vs total
aportaciones mix. No `--rescate-plan-pensiones-capital` flag.
No auto-calculation. Casilla 0011 (Reducciones rendimientos
trabajo) accepts manual entry but with no guidance — a user
unfamiliar with DT 12ª will not enter anything. Lost reducción
€6,983.64 → lost cuota €2,100-2,790 per Carla-shape filer.

Affects every retiree who rescates en forma de capital with
pre-2007 aportaciones (entire cohort with plans dating back
25+ years — most plan-de-pensiones holders aged 65+).

### TRIPLE-CONFIRMED — Casilla 0041 (capital mobiliario base ahorro) → 0460 NOT propagated

Independently confirms Sergio round-13 C2 (dividends 0029) and
Mateo round-15 (capital mobiliario 0300/0301). Carla case:
intereses cuenta de ahorro €1,200 → 0027 → 0036 → 0038 → 0040
→ 0041 = 1,200.00 (chain works to subtotal). But 0460 (base
imponible ahorro) stays 0.00. Formula declared as `[0424] -
[0436] - ... + [0429]` — does NOT include `[0041]` as summand.

Retención €228 acrediated in 0597 generates a deduction with
NO correlating cuota — fiscally incongruent state. Sergio's
dividends + Mateo's fondo + Carla's intereses all suffer the
same structural defect. **Task #181 elevated to TRIPLE-confirmed
top-priority CRITICAL.** Every M100 filer with any capital
mobiliario income loses the ahorro cuota and the retención
deduction becomes spurious.

### HIGH — Multiple pagadores Art. 96.3 LIRPF obligation undetected

Carla's three pagadores total €79.2k, second + third combined
€61.2k (well above €1,500 threshold). Art. 96.3 LIRPF mandates
filing obligation. The CLI has NO mechanism to derive or warn
about this. No `--multiple-pagadores` axis, no advisory in
`overview status`, no precalificación at `work create`.
Casilla 0824 labelled "Por obligación de presentar la
declaración del IRPF por razón de tener más de un pagador" is
actually a Cantabria autonomic deducción — misleading
nomenclature, not the obligation surface.

A retiree with single state pension €18k below €22k threshold
might assume exemption from filing — incurring infracción.

### HIGH — Pension rescate classification has no guided channel

Pension plan rescate en forma de capital IS rendimiento del
trabajo (Art. 17.2.a LIRPF). The CLI correctly accepts €60k in
casilla 0003 without error, but offers NO guided channel from
"I rescued my pension plan" to "enter in 0003 as trabajo
rendimiento". A user without legal background may classify it
as rendimiento capital mobiliario (base ahorro), triggering
wrong tarifa.

### MEDIUM — €2,000 gastos deducibles Art. 19.2.f + Reducción Art. 20 require manual entry

Both are statutorily granted to every taxpayer with rendimientos
trabajo. Casillas 0019 and 0023 are `manual` — engine does NOT
auto-apply. Many users miss these.

### MEDIUM — `--revision` requirement unhelpful at `work create`

User must discover valid revisions through error message rather
than auto-select latest applicable for `--year`. Family with
R7-error and the revision-temporal-validation fix (#171
shipped at a0d7daa27).

### LOW — `verify` `DRAFT_HAS_ERRORS` opaque

Re-confirms previous rounds (Lourdes F10). Refusal does not
enumerate the failing fields.

### LOW — `birth_date` field stored but unused

Demonstrates "captured but unwired" defect family — same shape
as #162 Beckham start_date (before #191 hardening) and several
other profile fields. Plan-wide audit of "profile fields without
downstream bindings" may surface more.

## Recommendations

Priority order:

1. **TRIPLE-CONFIRMED base imponible ahorro chain (#181, P0)** — Three
   independent personas + three different income types. Author the
   missing formula `0460 = sum of (0041, 0424, etc.)` chain. Most
   operationally critical defect of the campaign — every M100 filer
   with capital mobiliario income misroutes.

2. **Mínimo personal mayores de 65 derivation (CRITICAL)** — wire
   profile `birth_date` to casilla `DPFNAC_D` and the mínimo
   formula. Auto-compute Art. 57.1.b LIRPF +€1,150 increment for
   65+ at year-end. Apply also to 75+ further increment if any.

3. **DT 12ª reducción 40% rescate plan capital (CRITICAL)** — add
   `--rescate-plan-pensiones-capital` axis with `aportaciones_
   pre_2007` and `total_aportaciones` Decimal fields. Auto-compute
   reducción and inject into 0011 with DT 12ª LIRPF legal_ref.
   Verification finding when 0003 contains a large lump sum and
   user has not declared the mix → suggest the axis.

4. **Multiple pagadores Art. 96.3 obligation surface (HIGH)** —
   derive from declared pagadores. Verification finding at
   `work create` and `overview status` when second+ pagadores
   exceed €1,500 → "you are OBLIGED to file M100".

5. **Pension classification guided channel (HIGH)** — add
   `--rescate-plan-pensiones-capital` (canonical) or
   `--prestacion-plan-pensiones-renta` (annuity) flags that
   route to correct casilla family + apply correct treatment.

6. **Auto-apply €2,000 + Reducción Art. 20 (MEDIUM)** — flip
   0019/0023 to `computed` with conditional formula gated on
   trabajo income presence.

7. **`work create` auto-select latest revision** — closes the
   discovery loop (related to #171).

Persona surface coverage this round: retiree + pension rescate
+ multiple-pagadores + DT 12ª. Quantitatively the affected
population spans:
- ~750k new retirees/year (mínimo 65+ + rescate).
- All existing M100 filers with capital mobiliario (#181 triple).
- All multi-pagador filers (~30% of M100 cohort).
