---
tags:
  - '#research'
  - '#modelo-multiyear-renta-151-beckham'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-modelo-multiyear-renta-adr]]"
---

# `modelo-multiyear-renta-151-beckham` research: `151 Beckham flat-rate engine and six-year window gate`

This research grounds the calculation engine for Modelo 151 — the
autoliquidación filed by taxpayers under the *régimen especial aplicable a los
trabajadores desplazados a territorio español* (LIRPF Art. 93, the "Ley
Beckham") — and its enrollment into the foundational authorization gate, which
requires a ≥2-renta end-to-end test before the backend is treated as functional.
151 is an engine-build modelo: it has no casillas, formulas, or calculation
registry entries today. Unlike the heavier 714 Patrimonio build, 151 is a
**small single-phase** engine: a flat two-band rate applied to a base, minus
retenciones. The régimen's six-year time limit is modelled as an **eligibility
gate**, not as a compute input. Every claim below was verified against the live
registry, the core profile model, and the in-repo legal corpus.

## Findings

### F1. 151 is an empty scaffold — engine build from zero

`src/aeat/_data/registry/aeat/modelos/151/` contains only empty directory
scaffolding: `revisions/2024-y-siguientes/{application_links,workbook_parity_refs}/`
with no `casillas/`, `formulas/`, `parameters/`, or `bindings/` content, and 151
is absent from the calculation registry. The revision id `2024-y-siguientes`
already exists as the scaffold anchor. The build authors casillas, a bracket
parameter, the cuota formula, and a profile-driven eligibility gate from scratch.

### F2. The legal corpus grounds Art. 93 and the six-year window — but NOT the bands

`src/aeat/_data/registry/aeat/legal/irpf-impatriados.toml` declares
`ley-35-2006:art-93` with a corpus HTML ref. Its notes confirm the régimen lets
the taxpayer "tributar por IRNR durante el período impositivo del desplazamiento
y los cinco siguientes" — i.e. the option year **plus five**, six tax periods
total. It also grounds RIRPF Art. 113-120 (procedure) and Orden EHA/2887/2008
(Modelo 151 approval). What it does **NOT** contain is the flat-band schedule of
Art. 93.2.a — 24% up to €600,000 and 47% on the excess. Those rate figures are
not in the legal TOML notes, and the `ley-35-2006-il.html` corpus file uses
anonymised `il`/`ilos` tokens. **The bands MUST be ingested from BOE
(BOE-A-2006-20764, Art. 93) before any calc formula is authored**, or the build
violates the calculation-grounding and no-tautological-test disciplines (a
hand-typed bracket would be ungrounded).

### F3. The eligibility axis ALREADY exists on the profile — no new field needed

The coordinator scratch proposed a new `beckham_option_year` profile field. That
is unnecessary. `core/profile.py` already carries `irpf_special_regime` (validated
to the `IrpfSpecialRegime` enum) and `irpf_special_regime_start_date` (validated
ISO-8601). The enum `IrpfSpecialRegime` lives in `domain/deadlines/_models.py`
and declares exactly two members, `GENERAL = "general"` and
`IMPATRIADO = "impatriado"`. The `IMPATRIADO` member's docstring states verbatim:
it "files Modelo 151, taxed at the flat IRNR rate. The regime has a six-year
window triggered by the opt-in election date (`special_regime_start_date` on the
profile)." So the gate keys on `irpf_special_regime == IMPATRIADO` for
applicability and derives the option year from `irpf_special_regime_start_date`.
Inventing a parallel `beckham_option_year` would duplicate an existing, validated
axis and fork the régimen-clock source of truth.

### F4. The flat-rate engine has a working structural sibling — Modelo 210

210 IRNR is a flat-rate engine that already shipped (revision `2025`, formulas
`m210-base-imponible` → `m210-tipo-gravamen-2025-resolve` → `m210-cuota-integra`
= `multiply(base, tipo)` → `m210-cuota-diferencial`, with a `bracket`/`keyed
bracket` rate parameter). 151's engine is the same skeleton: resolve a base, look
up the rate, multiply, subtract retenciones. 151 differs in that its rate is a
**numeric two-band schedule** (€0→24%, €600,000→47%) rather than 210's
enum-keyed `tipo_renta` table, so the right primitive is the numeric
`lookup_bracket` operator on a `bracket_table` parameter, not 210's
`keyed_bracket_table`.

### F5. The bracket primitives exist and fit the bands exactly

`FormulaOperator` (in `_schema.py`) includes `lookup_bracket`. The `BracketEntry`
model encodes a half-open interval `[lower_bound, upper_bound]` plus
`fixed_addition` (cuota accumulated up to `lower_bound`) and `marginal_rate`, with
the documented evaluation `cuota = fixed_addition + marginal_rate * (base −
lower_bound)`. The Beckham bands map cleanly:
- row 1: `lower_bound = 0`, `upper_bound = 600000`, `fixed_addition = 0`,
  `marginal_rate = 0.24`;
- row 2: `lower_bound = 600000`, `upper_bound = None` (open top),
  `fixed_addition = 144000` (= 0.24 × 600000), `marginal_rate = 0.47`.
The `fixed_addition` of the top row is derived from the lower band, so the build
must compute it from the grounded figures, not assert it independently. A
`bracket_table` parameter dated `valid_from` for the relevant ejercicio holds the
schedule; the cuota formula calls `lookup_bracket(base, <param>)`.

### F6. The six-year window is a GATE, not a compute input (no-silent-under-declaration)

The régimen applies for the option year and the five following. Past that window
the taxpayer reverts to general IRPF (Modelo 100) and 151 no longer applies. This
is an **eligibility predicate**, not a term in the cuota formula: the rate does
not change across the six years, so the window must not enter `lookup_bracket`.
Per the `no-silent-under-declaration` discipline the correct shape is an
**ADVISORY** finding — `filing_year > option_year + 5` surfaces a non-blocking
WARNING that the régimen window has lapsed (the operator may legitimately be in a
transition or late-filing situation; a human files outside the app), exactly
mirroring the Modelo 200 `implies_nonzero` advisory pattern. It must NOT be a
BLOCKING_RULE that refuses computation, because the foundational gate's
ADVISORY-not-refusal posture (from the deadline-independence ADR) holds: an
engine that exists computes and informs.

### F7. The cross-renta invariant is régime-clock continuity, not value carry

151 has no inter-year value carryforward (no BIN, no compensación). The cross-renta
property that the ≥2-renta enrollment test proves is **régime-clock continuity**:
the régimen persists across consecutive years within the window, anchored to one
fixed option year. The mechanism is a `previous_filing`-style binding with
`filing_year_delta = -1` reading the prior year's option-year context to confirm
the régimen has not lapsed or restarted — the same `filing_year_delta`/regime-clock
hook the Modelo 130 carry uses (M130 `bindings/0001` + `0002` under
`2019-y-siguientes` exercise the prior-period read). The carry here is a
**continuity check**, not a sum: year N and year N+1 both inside
`[option_year, option_year+5]` with the same option year is the invariant.

### F8. Enrollment-test oracle

The 24%/47%/€600k bands, once ingested from BOE, are statute-checkable, so the
cuota is groundable against the Art. 93.2.a figures (not hand-computed from the
formula under test). The ≥2-renta test drives two consecutive ejercicios inside
the window for an `IMPATRIADO` profile with a fixed `irpf_special_regime_start_date`,
asserting: (i) cuota = `lookup_bracket(base)` − retenciones each year against the
grounded bands; (ii) the régime-clock continuity hook confirms both years sit in
the window; (iii) a third scenario at `filing_year = option_year + 6` surfaces the
ADVISORY window-lapsed finding rather than a silent grant. The recorder observes
both in-window years, satisfying the ≥2-distinct-renta-years contract.

### Sequencing implication carried to the ADR

The build has a hard ordering: **corpus population of the Art. 93.2.a bands from
BOE-A-2006-20764 MUST precede calc authoring**. This is the same
corpus-gap-first sequencing the A5 714 build faces (714 needs arts. 30/31/4.Nueve
from BOE). The ADR must state the band ingest as Phase A and the engine as Phase
B so no agent hand-types an ungrounded bracket.
