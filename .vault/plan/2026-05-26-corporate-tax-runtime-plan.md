---
# REQUIRED TAGS (minimum 2): one directory tag + one feature tag
# DIRECTORY TAGS: #adr #audit #exec #index #plan #reference #research
# Directory tag (hardcoded - DO NOT CHANGE - based on .vault/plan/ location)
# Feature tag (replace corporate-tax-runtime with your feature name, e.g., #editor-demo)
# Additional tags may be appended below the required pair
tags:
  - '#plan'
  - '#corporate-tax-runtime'
# ISO date format (e.g., 2026-02-06)
date: '2026-05-26'
# Complexity tier (mandatory for new plans).
# Allowed: L1 (Steps only), L2 (Phases above Steps),
# L3 (Waves above Phases above Steps), L4 (Epic above Waves
# above Phases above Steps; PM association required).
# Pre-existing plans without this field default to L2.
tier: L2
# Related documents as quoted wiki-links.
# Carries the AUTHORISING documents (ADR, research, reference,
# prior plan) for every Step in this plan; Steps inherit this
# chain; per-row reference footers do not exist.
related:
  - "[[2026-05-21-corporate-entity-calculation-adr]]"
  - "[[2026-05-21-taxpayer-type-applicability-plan]]"
  - "[[2026-05-21-cli-testimonial-audit]]"
---

# `corporate-tax-runtime` plan: IS micro-empresa bracket dispatch, INCN-gated Modelo 202 modality, new-entity period rate

Binding follow-on plan from the Q1 taxpayer-type-applicability campaign,
authorised by the corporate-entity calculation ADR. The Q1 W03.S13 work
landed the LIS Art. 29 IS rate schedule data and a scalar entity-type rate
dispatch covering the general, cooperative-protected, and non-profit sub-
forms. Two period and INCN dependent IS rate cases remain unrouted: the
micro-empresa bracketed rate (17 / 20 percent for 2025, 19 / 21 percent
for 2026) and the new-entity first-two-profit-periods 15 percent rate.
Closing them requires two new profile facts, a new bracket-dispatch
runtime op, a restructured Modelo 200 cuota-integra formula, and the
INCN-gated Modelo 202 Art. 40.2 / 40.3 modality split.

## Proposed Changes

Two regulated profile facts grounded in LIS and Modelo 202 BOE authority.
The first is the INCN (importe neto de la cifra de negocios) of the prior
12 months, a typed Decimal that gates the Modelo 202 modality split at
the 6.000.000 EUR threshold and contributes to the micro-empresa axis.
The second is a boolean flag for the first two profit-making periods of
a newly-created legal entity, gating the LIS Art. 29 15 percent override.
Both facts are optional; an undeclared value yields the same honest
INCOMPLETE-style fallback the rest of the engine emits, never a guessed
rate.

A new calculation-runtime op `lookup_bracket_by_entity_type` extends the
`lookup_bracket_by_ccaa` precedent already shipped for the IRPF tarifa.
The op resolves a `bracket_table` parameter against the profile's
`legal_entity_form` and period state, returning the applicable tranche
list. The Modelo 200 cuota-integra formula is restructured so a bracketed
parameter (the corrected `tipo-gravamen-pyme`) is applied via the tranche
table rather than the current scalar `casilla x rate` shape. The new-
entity 15 percent override is layered on top of the sub-form dispatch via
the period-state fact, consistent with the corporate-entity ADR
description of the rate as a period-dependent state on the sub-form, not
a sub-form value.

The Modelo 202 modality (Art. 40.2 cuota method vs Art. 40.3 base-
imponible method) becomes a registry-derived gate keyed on the INCN
threshold. Above 6.000.000 EUR the engine selects Art. 40.3 and does not
offer Art. 40.2; below the threshold both modalities are reachable. The
LIS Art. 40.3 article text fixing the 6.000.000 EUR figure is
transcribed against BOE-A-2014-12328 and grounded as a new legal entry
before the applicability condition is encoded.

Real-behaviour tests anchor expected cuota values against AEAT Manual de
Sociedades worked examples, never against numbers re-derived from the
rate the registry declares; structural tests cover dispatch wiring,
validation errors, and graph integrity per `no-tautological-calculation-
tests.md`.

## Steps

### Phase `P01` - profile facts and legal grounding

Land the two regulated profile facts and the BOE-grounded legal entry
they cite, with anti-tautology persistence-boundary roundtrip coverage.

- [ ] `P01.S01` - Transcribe LIS Art. 40.3 against the BOE-A-2014-12328 corpus and register `ley-27-2014:art-40-3` as a resolvable scoped registry legal entry carrying the 6.000.000 EUR threshold text; `src/aeat/_data/registry/aeat/legal/is.toml`.
- [ ] `P01.S02` - Add an `incn_prior_12_months` typed Decimal profile fact, project it onto `TaxpayerProfile`, collect it in the wizard with operator-language prompt, and bind a `--incn-prior-12-months` CLI flag on `config profile create` and `edit`; `src/aeat/domain/deadlines`.
- [ ] `P01.S03` - Add a `new_entity_first_two_profit_periods` typed boolean profile fact, project it onto `TaxpayerProfile`, collect it in the wizard with operator-language prompt, and bind a CLI flag on `config profile create` and `edit`; `src/aeat/domain/deadlines`.
- [ ] `P01.S04` - Roundtrip and anti-tautology tests for both new optional facts through the real encrypted SQL persistence boundary, populating non-default values and asserting strict equality on reload; `src/aeat/application/user_profile`.

### Phase `P02` - runtime, formula, and Modelo 202 modality

Wire the new facts into the calculation runtime so the micro-empresa
bracket, the new-entity 15 percent rate, and the Modelo 202 modality
gate all resolve correctly.

- [ ] `P02.S05` - Introduce a `lookup_bracket_by_entity_type` calculation-runtime op modelled on the `lookup_bracket_by_ccaa` precedent, resolving a `bracket_table` parameter against the profile's `legal_entity_form` and period state and rejecting scalar parameters with a clear validation error; `src/aeat/domain/calculations/registry`.
- [ ] `P02.S06` - Restructure the Modelo 200 cuota-integra formula to apply a tranche table per entity sub-form, routing a micro-empresa profile to `tipo-gravamen-pyme` via the new op and layering the new-entity 15 percent override via the period-state fact; `src/aeat/_data/registry/aeat/modelos/200`.
- [ ] `P02.S07` - Register the Modelo 202 modality gate as a registry-derived applicability condition keyed on the INCN threshold, making Art. 40.3 mandatory above 6.000.000 EUR and keeping Art. 40.2 reachable below, each carrying the new `ley-27-2014:art-40-3` `legal_refs`; `src/aeat/_data/registry/aeat/modelos/202`.
- [ ] `P02.S08` - Real-behaviour tests grounding expected IS cuota against AEAT Manual de Sociedades worked examples for the general, micro-empresa, and new-entity cases, plus structural tests proving the Modelo 202 modality gate; `src/aeat/domain/calculations/registry`.

## Parallelization

`P01` precedes `P02` by a hard ordering: every `P02` Step consumes a
profile fact, a legal entry, or a registry shape that `P01` lands.
Within `P01`, `S02` and `S03` are independent and may run in parallel,
both following `S01`; `S04` is the closing verification and runs last.
Within `P02`, `S05` precedes `S06` and `S07` (both consume the new op);
`S08` is the closing verification, runs last. The Q1 W03 corporate-
calendar foreign-flight work registering Modelo 202 deadline windows is
a soft dependency, not a hard block; `P02.S07` registers the modality
gate independently of the deadline-window data.

## Verification

The plan is complete when every Step is closed and each of the following
verifiable checks holds:

A micro-empresa legal-entity profile (INCN declared below the
6.000.000 EUR threshold) computes its Modelo 200 cuota via the LIS
Art. 29 micro-empresa tranche table, with the 2025 (17 / 20) and 2026
(19 / 21) scales each matching an AEAT Manual de Sociedades worked
example.

A newly-created legal entity declared as in its first two profit-making
periods computes its cuota at 15 percent, with the period-state fact
gating the override against the otherwise-applicable sub-form rate.

A legal entity above the 6.000.000 EUR INCN threshold is offered only
the Modelo 202 Art. 40.3 modality; below the threshold both modalities
are reachable; the gate is a registry-derived applicability condition
citing `ley-27-2014:art-40-3`.

Every new `legal_refs` resolves against the registry legal catalogue;
the `test_seed_legal_refs_resolve_against_the_registry` style guard
extends to the new keys and fails on a fabricated one.

Every formula change is grounded against an external oracle (AEAT
Manual de Sociedades worked example, BOE article text, or registry-
authoritative fixture); no calculation test asserts a number re-derived
from the rate or formula the registry declares.

All tests pass with real behaviour; no mocks, fakes, stubs,
monkeypatches, skips, xfail markers, or tautological assertions.

`vault plan check` parses the document; `vault check all` reports no new
broken links or schema violations attributable to this plan.
