---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-carla-cli-testimonial-audit]]"
  - "[[2026-05-27-sergio-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-20 Aitor Etxegarai SAL socio-trabajador Gipuzkoa foral`

## Scope

Twentieth testimonial round, Aitor Etxegarai Zabala — Donostia
(Gipuzkoa, foral CCAA), 38, socio-trabajador and administrador of
Forjas Etxegarai SAL (Sociedad Anónima Laboral, 7 worker-owners + 2
non-worker shareholders). 2024 income: nómina €38k + bonus €12k +
cuota cargo administrador €6.5k + dividendos SAL €6k + plan de
empleo aportación €4.2k. Exercises SAL régimen (Ley 44/2015), foral
refusal validation (Lourdes F1 follow-up), administrator retención
Art. 101.3 LIRPF (Sergio H4/H5), euskera locale (Lourdes F11),
plan de empleo Art. 52 LIRPF reducción.

## Findings

### CRITICAL — SAL legal entity form entirely absent from enum

`--legal-entity-form sal` rejected: `'sal' is not one of 'sl', 'sa',
'cooperativa', 'sociedad_civil_mercantil', 'sin_fines_lucrativos',
'other'`. No `sal` (Sociedad Anónima Laboral) or `sll` (Sociedad
Limitada Laboral) options. SALs are first-class legal forms under
Ley 44/2015 with distinct fiscal régimen: tipo reducido IS, reserva
especial Art. 14, FOGASA/desempleo peculiarities, plan-de-empleo
limits.

Fallback to `sa` works mechanically but loses entire SAL régimen.
~3,700 active SALs in Spain affected, concentrated in País Vasco
and Catalunya.

### CRITICAL — SAL régimen unmodeled (Ley 44/2015 Art. 14)

Reserva especial Ley 44/2015 Art. 14 obligates SALs to dotar 10% of
beneficio neto annually until reserva = 50% capital social. This
dotación reduces IS base imponible. M200 has 3,227 casillas but
NONE relate to the reserva especial. For Forjas Etxegarai's
hypothetical €120k beneficio, €12k dotación → €3k tax savings
(at 25%) silently unavailable.

### POSITIVE — Foral refusal (Lourdes F1) works correctly

`--tax-residence-ccaa pais_vasco` and `navarra` both refuse with
clear message naming Ley 12/2002 Concierto Económico + foral
redirect URLs (gipuzkoa.eus/ogasuna, etc.). #175 fix validated
in a corporate-context round (no regression from natural-person
Lourdes context). Aitor cannot create a personal profile for
Gipuzkoa — had to use Madrid as proxy, which is the architecturally
correct behavior (CLI is AEAT-scope only).

### QUADRUPLE-CONFIRMED — M100 base imponible ahorro #181

Casilla 0029 = 6000 (dividendos SAL). 0040/0041 populate. 0460
(base imponible ahorro) and 0510 (base liquidable ahorro) BOTH
remain 0.00. Retención M123 €1,140 also doesn't reach 0597.

Fourth independent persona to surface this exact defect:
- Sergio round-13 (dividends).
- Mateo round-15 (fondo intereses).
- Carla round-19 (cuenta intereses).
- Aitor round-20 (SAL dividends).

#181 PRIORITY ELEVATED further — affects every M100 filer with
ahorro income. Quadruple confirmation across four different
income sources means the underlying defect is in the 0460 formula
itself (does not include 0041 as summand), not income-type-specific.

### HIGH — Plan de empleo Art. 52 LIRPF reducción not applied

Casilla 0430 = 4200 accepted as input. Base liquidable general
(0500) shows €56,500 — UNCHANGED. Should be `0500 = 0435 − 0430 =
52,300`. Art. 52 LIRPF allows up to €10k reducción for plan-de-
empleo aportaciones (separate from individual plan cap €1.5k).

Affects every salaried worker with plan-de-empleo aportación
(majority of large Spanish employers offer this). The casilla
exists, accepts input, but no formula consumes it into the base
liquidable computation.

### HIGH — Tipo IS ERD 23% not applied (re-confirms Sergio H1)

INCN €850,000 declared via `--binding modelo-200-2024-profile-incn-
prior-12-months=850000`. M200 returns `DP200014:00558 = 25` (tipo
25%). Should be 23% per Ley 27/2014 Art. 29.1 for ERD (cifra
negocios < €1M). The 15% new-entity flag exists but no ERD path.

### HIGH — Reserva especial Ley 44/2015 Art. 14 missing in M200

Already covered by SAL régimen finding above; specific casilla
hooks for the dotación obligation need authoring.

### HIGH — Administrator retención Art. 101.3 LIRPF labels missing (re-confirms Sergio H4/H5)

M111 mechanically supports casillas 07-09 (administradores) distinct
from 01-03 (empleados ordinarios). CLI accepts both. But:
- No CLI label says "Art. 101.3 LIRPF" or "35% fixed".
- No CLI verification that retention % in casilla 09 matches Art. 101.3.
- M190 accepts `clave B` string without validation of implied 35% rate.
- M100 receptor has no specific binding for cargo-administrador
  retención.

### MEDIUM — Euskera (eu) locale absent (re-confirms Lourdes F11)

`--output-language eu` rejected; options are `[es, en, ca, hu]`.
Catalan and Hungarian present, Basque absent. SALs concentrate in
the País Vasco — substantial Basque-speaker filer cohort
disadvantaged.

### MEDIUM — M123 casilla 06 arithmetic bug

When using bindings `modelo-123-nperceptores=7` and `modelo-123-
base=42000`, casilla 06 returns `42007` instead of `42000`. Casilla
06 should be only base (single field), not `nperceptores + base`.
Wrong formula or wrong binding wiring.

### MEDIUM — M190 no clave breakdown in output

M190 output shows 3 aggregate key_figures only (total perceptions,
total amount, total retentions). No per-clave (A/B/G/etc.) breakdown.
Difficult to verify against M111 quarterly sums.

### LOW — Out-of-scope SS régimen guidance absent

Worker-owner administrators in SAL are asimilados al RGSS but with
peculiarities (no FOGASA, no desempleo if administrator). Not AEAT
competence, but a CLI billing itself as "complete tax guidance"
would benefit from a pointer to TGSS for this corner.

## Recommendations

Priority order:

1. **#181 base ahorro chain (P0 ELEVATED, QUADRUPLE-CONFIRMED)** —
   already-tracked. Now affects every M100 filer with any capital
   mobiliario income; four-persona confirmation removes any doubt
   the defect is universal.

2. **SAL legal_entity_form + reserva especial (CRITICAL)** — add
   `sal` and `sll` to `--legal-entity-form` enum. Add bindings for
   reserva especial dotación in M200. Add tipo-reducido ERD path
   (separate task — Sergio H1 also).

3. **Plan de empleo Art. 52 LIRPF reducción (HIGH)** — wire casilla
   0430 → reducción on base liquidable general computation. Cap at
   €10k or 30% of trabajo rendimientos, whichever lesser.

4. **Tipo IS ERD 23% (HIGH)** — derive from `incn_prior_12_months`
   binding (already present in profile schema). If < €1M, tipo =
   23%; if new entity active, tipo = 15%; else default 25%. M200
   tipo computation must consult this.

5. **Administrator retención labels (HIGH)** — add tooltips /
   labels to M111 casillas 07-09 naming Art. 101.3 LIRPF + 35%
   tipo. Add validation that casilla 09 / 08 ratio approximates 35%
   per Art. 101.3 (or 19% for INCN < €100k entity).

6. **Euskera locale (MEDIUM)** — add `eu` to `--output-language`
   enum. Scaffold + audit cycle for translations of new wizard
   prompts. Existing keys passthrough es initially with translation
   roadmap.

7. **M123 casilla 06 arithmetic bug (MEDIUM)** — fix the formula
   summing nperceptores into base.

8. **M190 per-clave output (MEDIUM)** — extend output with key_
   figure per clave.

The triple-confirmation of #181 elevated to quadruple-confirmation
this round. The campaign has now demonstrated that base imponible
ahorro chain is THE most operationally critical open defect.
