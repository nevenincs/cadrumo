---
tags:
  - '#adr'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:9eba1d805535cc0bbcf1f9e342fc32a4b5750f3cab9150271358202445feb29e'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-research]]"
  - "[[2026-07-01-modelo-100-minimo-descendientes-engine-adr]]"
  - "[[2026-08-04-profile-derived-selectors-research]]"
  - '[[2026-08-05-minimo-descendientes-eligibility-diagnostic-message-headroom-census-research]]'
---
# `minimo-descendientes-eligibility` adr: `Complete the Art. 58/61 LIRPF eligibility predicate before the derived-aggregate override closes` | (**status:** `accepted`)

## Problem Statement

The Modelo 100 mínimo por descendientes derivation implements three of the seven
conditions the law states, and the omissions are not symmetric: three of them inflate the
mínimo, which reduces the base and under-declares tax. The largest affects an ordinary
two-parent household filing individually. `2026-08-04-minimo-descendientes-eligibility-research`
records the measurement.

A decision is needed now rather than at leisure because the only channel by which a filer
can currently reach a correct figure — an operator override of the derived aggregate — is
scheduled for removal by `2026-08-04-profile-derived-selectors-adr`. Closing that channel
over an incomplete derivation converts a correctable under-declaration into an
uncorrectable one. This record therefore owns both the correctness fix and the ordering
constraint the sibling campaign must respect.

## Considerations

- Three of the four gaps over-grant the mínimo and under-declare tax; the fourth
  (anualidades) inverts and over-taxes. One predicate feeds all three consuming surfaces,
  so one fix corrects all of them — grounding in the research.
- Two of the missing conditions are observable figures with a legal test (the Art. 58.1
  rentas cap, the Art. 61 norma 2ª own-return exclusion). The third, norma 1ª proration,
  depends on whether another entitled contribuyente also claims — not a fact about the
  descendant.
- The project forbids inline regulatory literals; thresholds belong in registry `money`
  parameters with legal-catalogue entries, per `aeat-schema-central-config` and
  `registry-calculation-legal-grounding`.
- Silently guessing an eligibility answer is barred in the over-granting direction by
  `no-silent-under-declaration`. Guessing in the under-granting direction harms the
  taxpayer instead, so neither default is free and the choice must be made explicitly.
- The engine never files; a human files outside it. An advisory the operator can act on is
  therefore a real control, not a consolation.

## Considered options

**Model the missing conditions as per-descendant facts and compute the predicate from
them.** Keeps the derivation a pure function of source facts. Requires new operator input
for figures the app cannot observe. Chosen.

**Keep the aggregate override as the correction channel.** Zero new modelling. Rejected:
the override suppresses the entire law computation to patch one missing condition, carries
no provenance distinguishing a corrected gap from a typo, and is being retired for exactly
those reasons.

**Add a per-descendant applicability override only (`full | half | none`), deriving
nothing.** Cheapest. Rejected as the sole mechanism: it makes the operator responsible for
applying law the engine is capable of applying, and its safe default is unknowable —
defaulting to `full` preserves today's over-grant silently.

**Defer the whole matter and ship the sibling campaign first.** Rejected: it is precisely
the ordering that converts a correctable defect into a locked-in one.

## Constraints

- Blocking on nothing external. The registry parameter mechanism, the legal catalogue, the
  per-descendant fact axis, and the CLI descendiente flow all exist and are stable.
- The sibling campaign `profile-derived-selectors` must not land its write refusal before
  this record's predicate work is complete. That is a hard ordering constraint in both
  directions and is restated in that record.
- Expected values for any calculation test must come from an external authority per
  `no-tautological-calculation-tests`; the bundled AEAT Renta manual worked examples and
  the consolidated LIRPF text are the available oracles.
- Revisions 2020-2025 share the predicate. Whether each revision's parameter set can carry
  the new thresholds is expected but unverified, and is a first implementation check.

## Implementation

Two per-descendant factual inputs are added to the descendiente axis: the annual rentas
figure excluding exempt income, and whether the descendant files their own return above
the norma 2ª figure. The eligibility predicate consumes both, with the two thresholds
supplied by the caller as registry `money` parameters resolved per filing year — the same
shape the birth-order tranches already use — never as Python literals. Each threshold
gains a legal-catalogue entry whose corpus reference anchors the verbatim clause.

Proration under norma 1ª is generalised from the shared-custody special case to the
entitlement rule the law actually states. The existing shared-custody flag remains one
trigger. Where no explicit per-descendant answer exists, the engine derives whether a
second entitled contribuyente is indicated from profile signals already on record — the
taxpayer's marital status, the presence of a spouse record, and the declaration type — and
applies the prorrata when they indicate one. A derivation used in place of an explicit
answer raises a non-blocking advisory naming the descendant and the inference, so the
operator can confirm or override before filing. An explicit per-descendant value always
wins over the derivation.

The direction of the default is a deliberate choice: where the signals indicate a second
entitled filer, the engine applies the prorrata rather than the full amount. That errs
toward under-claiming, which the advisory surfaces and the operator can correct, rather
than toward the silent over-claim `no-silent-under-declaration` forbids.

The anualidades eligibility flag needs no separate work: it consumes the same predicate
and is corrected by the same change. The Art. 64 base comparison is already enforced in
the registry formula and is untouched.

## Rationale

The knockout criterion is the direction of error. Three of the four gaps under-declare
tax, and the research establishes that the affected household shape is ordinary rather
than exceptional. No option that leaves the predicate incomplete survives that, and the
override channel that currently masks it is both unauditable and about to disappear.

Modelling the conditions as facts rather than as an override wins because it keeps the
derived aggregate a pure function of source facts — the property the sibling campaign
depends on — and because the two threshold conditions are genuinely observable, so asking
the operator for a figure is asking for data, not asking them to apply law. Proration is
the one condition that is not a fact about the descendant, which is why it alone is
derived-with-advisory rather than demanded outright: the profile already carries enough
signal to get the common case right, and the advisory keeps the inference visible instead
of silent.

## Consequences

The mínimo becomes correct for the ordinary two-parent individual-filing household, for
filers whose descendant earns above the Art. 58.1 cap, and for filers whose descendant
files their own return — and the anualidades régimen stops being denied to filers entitled
to it. Calculation output changes for affected profiles, which is the intended correction
and not a regression.

Operators gain three new descendiente questions and may meet a new advisory. That is a real
cost in setup friction, accepted because the alternative is a silently wrong figure on a
filed return.

The sibling campaign is unblocked to close the override channel once this lands, and the
two records must be sequenced rather than merely cross-referenced.

Scope is bounded on the ascendientes side by measurement rather than assumption: the
mínimo por ascendientes is a bare manual input with no derivation, so it carries no
incomplete predicate and is untouched by this record. The grounding records the caveat
that its axis is partially scaffolded in the same shape the descendientes axis was before
its engine landed, so a future ascendientes engine must model eligibility completely at
the outset rather than repeating this sequence.

Three conditions remain unmodelled and are deliberately out of scope: Art. 61 norma 4ª
(mid-year death, a fixed amount rather than a factor), the Art. 58.1 asimilación of
tutela and acogimiento, and the assimilation of dependencia to convivencia. All three
under-grant rather than over-grant, so they harm the taxpayer rather than the revenue and
do not carry the same urgency; each needs its own grounding. A follow-up must be opened
before this campaign closes.

The entry surface for the two new facts is the CLI descendiente flow. The wizard question
for them shares a surface with a standing defect — a declared operator field with no entry
point, whose casilla hard-fails without it — so both belong to one entry-surface follow-up
rather than two.
