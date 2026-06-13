---
tags:
  - '#audit'
  - '#cli-testimonial'
date: '2026-05-27'
modified: '2026-05-27'
related:
  - "[[2026-05-27-eva-cli-testimonial-audit]]"
---

# `cli-testimonial` audit: `round-10 David O'Connor Beckham impatriado`

## Scope

Tenth testimonial round, David O'Connor — Irish national tech
executive, Beckham régimen opt-in effective January 2024 under
Art. 93 LIRPF. Salary €280k as Spanish empleado, US stock-options
vesting + US bank savings (foreign-source), Spanish freelance income
€8k. CCAA Madrid, preferred output language English. Exercises the
impatriado declaración path (M151 expected), the foreign-asset
exemption (Art. 93.5 LIRPF override of M720), and the flat-tarifa
chain (24% on first €600k, 47% above).

## Findings

### CRITICAL — Beckham régimen entirely unmodelled

The user_profile schema has no axis for Art. 93 LIRPF opt-in. No
`irpf_special_regime`, no `impatriados`, no `beckham`, no `art_93`
field anywhere. The profile wizard never asks whether the taxpayer
has opted into the special régimen for posted workers. This is the
single most consequential classification decision for an impatriado —
it determines which form (M151 not M100), which tarifa (flat 24%/47%
not progressive), and which source scope (Spanish-only not worldwide).
The system is structurally blind to this axis.

### CRITICAL — Modelo 151 entirely absent

`aeat app modelo work create --modelo 151` fails with `Unknown
modelo 151`. M151 is the statutory filing form for impatriados —
not a variant of M100 but a separate declaración with its own
casilla structure, flat-tarifa boxes, and different reduction rules.
Without M151 there is no correct filing path for an Art. 93 opt-in
taxpayer in this application.

### CRITICAL — M100 tarifa chain zeroes out at €280k (DOUBLE-CONFIRMS R7 cluster-T)

Created an M100/2024 work-unit with €280k trabajo income (casilla
0003). Engine correctly computes base imponible general = €280k,
base liquidable general = €280k, mínimo personal = €5.550. Then
the cuota chain breaks: 0527, 0528, 0529, 0532, 0533, 0545, 0546
all output 0.00 despite €280k base liquidable. No error, no warning.
Cuota diferencial = 0 on €280k salary. Independently confirms the
Eva round-10 €52k finding — R7 cluster-T is structural, not edge-
case. Expected output for resident progressive: ~€107k (estatal +
Madrid autonómica). Expected output for Beckham flat: €67.200 (24%
flat). Engine produces neither.

### HIGH — M720 exemption for impatriados not modelled

Art. 93.5 LIRPF exempts impatriados from M720 even with foreign
assets above €50k. Setting `--bienes-extranjero-above-threshold` on
the profile yields no NOT_APPLICABLE verdict for M720; the work-unit
is created without protest. `overview status` provides no obligations
assessment — only in-progress counts. There is no surface saying
"M720 does not apply because you are impatriado." Silent wrong
obligation; régimen sancionador exposure.

### HIGH — Source-scope axis missing (Spanish vs worldwide income)

US stock-options vesting (€120k) and US Bank of America interest are
NOT taxable in Spain under Beckham — only Spanish-source rendimientos
fall in scope. The CLI has no `source_jurisdiction` or
`spanish_source_only` flag in bindings, ledger classification, or
casilla wiring. If foreign-source income is fed into any casilla,
the engine taxes it without warning. Ledger import + classification
workflow is unsafe for impatriados in current state.

### MEDIUM — 6-year Beckham window expiry untracked

Profile schema has no `irpf_special_regime_start_date`. Beckham
runs year-of-displacement plus 5 subsequent years. For a 2024 opt-in,
year 7 (2030) is when progressive régimen returns on worldwide income.
No field to record opt-in date, no derived expiry year, no
advisory surface for approaching year 6. User must track externally.

### MEDIUM — Output-language flag coverage gaps

`--output-language en` correctly persists to `preferences.output_language`
and is honoured by `overview status`, `modelo work calculate`,
`modelo work verify`. NOT accepted by `modelo work create`,
`modelo work status`, `modelo work list`, `review queue`. Flag
contract inconsistent across subcommands.

### MEDIUM — Profile wizard hardcoded Spanish

`config profile create --help` text, option descriptions, and
section headers remain entirely in Spanish regardless of any
language flag. A first-time English-speaking impatriado cannot
understand the onboarding surface.

### POLISH — Modelo list and bindings list table headers untranslated

`modelo list` and `bindings list` tabular outputs always render
English column labels (correct convention) — flagged as polish to
confirm intentional. Tabular labels should NOT be localised; only
prose surfaces should.

## Recommendations

The critical finding from this round is the DOUBLE-CONFIRMATION of
R7 cluster-T from Eva round-10. Two independent personas at vastly
different income levels (€52k salary and €280k salary) both produce
0.00 cuota tarifa on the general base. This is not edge-case; it is
the M100 tarifa wiring for 2024 entirely unwired or misrouted.
Architecture grounding dispatched as task #158.

Priority remediation order for Beckham-régimen coverage:

1. **Task #158** — R7 cluster-T grounding + fix (precedes everything;
   without this, no M100 result is trustworthy for any persona).
2. **Task #162** — Profile schema axis `irpf_special_regime` +
   `irpf_special_regime_start_date` (foundation for #161, #163, source-
   scope, lifecycle).
3. **Task #161** — M151 Path-B refusal stub (cheap defect-of-record
   blocking silent misrouting into M100).
4. **Task #163** — M720 NOT_APPLICABLE wiring (depends on #162).
5. Source-scope axis (separate task to be filed).
6. Beckham 6-year window advisory.
7. Output-language flag coverage + profile-wizard localisation.

The application is not safe for Art. 93 filers in its current state —
a Beckham taxpayer who confides their declaración to this CLI will
get a zeroed cuota and silent worldwide-income scope, both of which
are material compliance failures.
