---
tags:
  - "#adr"
  - "#real-pdf-import"
date: 2026-04-22
related:
  - "[[2026-04-12-modelo-303-390-adr]]"
  - "[[2026-04-12-manual-practico-adr]]"
  - "[[2026-04-17-export-first-adr]]"
---

# ruleset-architecture-adr

## status

Proposed — 2026-04-22. Establishes the canonical architecture for the
`src/aeat/formulas/_rulesets/` subpackage as it scales from the
original Modelo 130/303 pair (2 rulesets) through the EPIC #305 wave 12-45
expansion (18 rulesets across 13 modelos) and beyond (regional
variants, per-year backfills, full-form upgrades).

## context

The formulas ruleset fleet grew from 5 entries (wave 12 baseline:
100.summary, 130×2, 303×2) to 18 entries (wave 45: adds 111×2, 115×2,
123×2, 131×2, 180×2, 200, 202, 390) in one EPIC. Two concrete
architectural questions surfaced:

1. **Registry key shape.** The current `RulesetRegistry` resolves on
   `(modelo, period)` with a uniqueness contract enforced by
   `_spans_overlap`. This breaks the moment a second variant of a
   modelo ships for the same period: a full Modelo 100 ruleset would
   overlap with `modelo_100.summary.2025`; a Canarias Modelo 303
   ruleset would overlap with `modelo_303.2025`.

2. **Percent-rate normalisation.** Some rulesets read the rate from an
   extracted casilla (whole-percent, e.g. `17,00`), others from a
   ParameterTable (fraction, e.g. `Decimal("0.19")`). The engine's
   `PercentFormula` is unconditional `rate * base` — no normalisation.
   Without convention, a misauthored formula yields 100× wrong audits.

Two secondary questions also surfaced during wave 37-45 reviews:

3. Module-level inheritance for year-over-year backfills (the
   `from .modelo_X_2025 import _CASILLAS as ...` pattern used by
   115/180/111/123/131 2024 rulesets).
4. Semantic meaning of an empty `ParameterTable` (Modelo 390 is a
   pure aggregator; some reviewers flagged this as suspicious).

## decision

### 1. Registry key grammar — `(modelo, variant, period)`

Ruleset IDs follow `modelo_{code}[.{variant}].{year}`. The optional
`{variant}` segment disambiguates partial / alternate / regional
encodings of the same modelo+year:

- `modelo_130.2024` — canonical full-year ruleset.
- `modelo_100.summary.2025` — summary-block partial.
- (future) `modelo_100.full.2025` — complete tarifa + deducciones.
- (future) `modelo_303.canarias.2025` — Canarias IGIC variant.

The `RulesetRegistry` key was `(ModeloCode, FiscalPeriod)` with
period-overlap checking. **Wave 47 (post-ADR) extended the key to
`(ModeloCode, variant, FiscalPeriod)`** — the refactor landed
immediately rather than being deferred because the `modelo_100.summary.2025`
ruleset already relies on the variant slot to reserve the default
slot for a future full-form `modelo_100.2025`.

`resolve()` accepts `variant: str = "default"` kwarg. Callers that
don't pass `variant` get the canonical ruleset for that (modelo,
period). Non-overlap checking runs per-(modelo, variant) slot.
Wave 48 audit stream 3 confirmed the variant axis is fully live.

### 2. Percent-rate normalisation — helper, not a flag

`PercentFormula` stays semantically pure: `rate * base`, both operands
already-normalised fractions. The /100 normalisation for
whole-percent casillas lives in the ruleset-authoring helper
`percent_from_whole(rate_ref, base)` which wraps `percent(div_op(rate,
lit("100")), base)` with a consistent `Decimal("0.0001")` quantize.

**Rejected alternative:** a `rate_is_whole_percent: bool` flag on
`PercentFormula`. That flag would push input-format provenance into
the operator node, which should remain dimension-agnostic. Named
helper carries the same meta-information without contaminating the
operator's semantics.

### 3. Year-over-year backfills — module-level inheritance

Pre-2025 rulesets (115/123/131/180 2024, etc.) import the 2025
sibling's `_CASILLAS`, `_FORMULAS`, `_CITATIONS` and only redeclare
`_EFFECTIVE_FROM`, `_EFFECTIVE_TO`, and the `ParameterTable` (which
is the only piece that must be year-tagged). This keeps the Pydantic
models frozen + explicit per-year without introducing mutation
semantics or a merge protocol.

**Rejected alternative:** a ruleset-inheritance graph
(`modelo_130.2024` inherits from `modelo_130.2023`). Would require
override semantics, merge resolution, and re-validation; complexity
outweighs the <5 year-over-year deltas observed per modelo to date.

### 4. Empty ParameterTable — acceptable for pure aggregators AND whole-percent-casilla rulesets

A ruleset with `ParameterTable(entries={})` is valid under two
distinct rationales (wave 48 audit stream 3 clarification):

**Pure aggregators.** Modelo 390 sums pre-computed cuotas; Modelo 123
and Modelo 100 (summary) aggregate per-row counters. No parameter
store is needed because no formula applies a rate. Future contributors
should NOT duplicate 303's `iva.rate_*` table into 390 — 390 reads
pre-rate-applied values from the quarterly 303 filings.

**Whole-percent casilla readers.** Modelos 200 and 202 read the tax
rate from an extracted casilla (whole-percent value like `17,00` or
`25,00`) via the `percent_from_whole` helper. The rate is carried by
the PDF itself, not by a rule-stored parameter, so a ParameterTable
entry would be redundant. This is the canonical pattern for any
modelo whose tipo de gravamen varies per filing (pyme vs micropyme
IS, etc.).

## implications

### Short-term (wave 46+)

- Pre-compile `named_field_patterns` regex in `__init_subclass__` now
  that 5 modelos use the primitive (036/037/232/369/720) — LOW from
  the wave 46 review. Avoids per-`extract()` re-compilation.
- Author wave 47+ rulesets using `percent_from_whole` for any
  whole-percent rate from an extracted casilla; use plain `percent`
  for ParameterTable rates (already a fraction).

### Already implemented (wave 47)

Variant-axis extension — `(ModeloCode, variant, FiscalPeriod)` key.
The below migration was executed in wave 47 (`987422b`); this block
is preserved as the historical record and renamed from
"Milestone-scale (1.0.0+)" per wave 54 M2 audit-closure:

- `variant: str = "default"` on `Ruleset` ✅
- Registry keyed on `(modelo, variant)` ✅
- `_spans_overlap` runs per-variant slot ✅
- `resolve(*, modelo, period, variant="default")` signature ✅
- 17 of 18 rulesets remain `variant="default"`; Modelo 100 summary
  uses `variant="summary"` to reserve the default slot for the
  future full-form ruleset ✅

### Future milestones (1.0.0+)

- First regional / full-form ruleset lands (Canarias IGIC, full
  Modelo 100, Navarra, etc.) — no registry changes needed; the
  variant axis is already live.
- Sub-EPIC #305-Modelo-100-full activates the canonical
  `variant="default"` slot for Modelo 100.

### Non-goals

- Ruleset inheritance / override graph (§3 rejected).
- Flag-based percent normalisation (§2 rejected).
- Cross-modelo parameter sharing (Modelo 390 does NOT read
  303's rate table — §4).

## alternatives considered

- **Collapse the three PDF primitives into a single FieldExtractor
  protocol.** Rejected — each primitive has a distinct output-type
  contract (Decimal vs str) and different warning taxonomies
  (truncation detection only applies to text). Unifying would erase
  static reasoning for zero gain. See wave 46 architectural review.

- **Add `modelo` code variants like `303_CAN` for Canarias.** Rejected
  — leaks geography into `ModeloCode` enum which should stay closed
  on AEAT's form catalogue. The `variant` axis preserves the enum's
  original shape.

## references

- [[2026-04-12-modelo-303-390-adr]] — initial 303/390 ruleset design.
- [[2026-04-12-manual-practico-adr]] — AEAT Manual citation discipline.
- Wave 41 contract-drift audit (vaultspec-code-reviewer) —
  introduced the ruleset-id grammar proposal.
- Wave 46 architectural review (vaultspec-code-reviewer) —
  identified the `variant` axis gap as HIGH risk.
