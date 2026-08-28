---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:42e7e7d1c1ce51a039a98a837e853936d54beee299d3416809a93f93b24be705'
related:
  - "[[2026-08-28-tui-architecture-orden-kind-temporal-carveout-population-audit]]"
---

# `tui-architecture` audit: `The modelo-level legal-ref exemption lets a 2024 redaction ground 2020 parameters`

## Scope

## Findings

## Recommendations

## A finer question than the gate asks

`_check_revision_scoped_legal_windows` validates a **revision's** devengo. But
parameter *values* carry their own dated windows, and a multi-year parameter can
hold a value whose window sits outside the window of the provision grounding it.
Nothing tests that.

Checking every dated value against its citations' `effective_from` /
`effective_to`: of **316** dated values, **39** have no cited provision covering
their own window — 36 in modelo 100, 2 in 360, 1 in 136.

## What the M100 rows are

All 36 cite `ley-35-2006:art-23`, whose catalogue entry declares
`effective_from = 2024-01-01`. That is the Ley 12/2023 redaction. Among them are
the rental reduction tiers:

| parameter | value |
|---|---|
| `renta-<year>-rental-reduccion-rate-tier-50` | 0,50 |
| `…-tier-60` | 0,60 |
| `…-tier-70` | 0,70 |
| `…-tier-90` | 0,90 |

Every revision from **2020 to 2025** carries all four, each citing only
`ley-35-2006:art-23`. So the 2020, 2021, 2022 and 2023 revisions hold the
2024-onward tier structure, windowed to their own year, grounded on a redaction
that did not exist then. The pre-2024 reduction was a flat 60 %.

The catalogue is not the problem: it already models the article's redactions over
time and carries `ley-35-2006:art-23-2021` for 2021-07-11 to 2023-12-31. No
parameter uses it, and no entry covers 2020 at all.

## Why no gate refuses it

`ley-35-2006:art-23` is one of modelo 100's **23 modelo-level `legal_refs`**, and
the devengo check exempts those by design — the docstring is explicit that
modelo-level refs "describe the modelo's cross-year authority corpus and remain
exempt", which is right for a corpus declaration.

The consequence is that a modelo-level citation grounds a *parameter value* with
no temporal test at all. That is a second carve-out beside the `orden`-kind one
recorded in the companion audit: between them, the two cover every case where
temporal grounding is asserted rather than checked.

## Direction — latent, and currently inert

**Verified: nothing consumes these values outside 2024.** Only the 2024 revision
reaches them, through a dispatch table mapping `tier-50/60/70/90` to the
`renta-2024-…` parameters. In 2020, 2021, 2022 and 2023 they are consumed by no
formula leaf, no dispatch table, and no production Python (the ids appear in no
non-test source). So there is **no liability error today**.

The exposure is what a future consumer would do. A pre-2024 revision that acquired
a rental-reduction formula would apply a 90 % reduction where its year's law
allows 60 % — a large over-relief, and therefore an **under-declaration**, on a
value no temporal gate would question.

## One thing I did not resolve

The **2025** revision also carries the four tiers and shows no consumer, while the
tier regime does apply from 2024 onward. Either 2025 models the reduction another
way or this is a genuine gap. I did not establish which, and it should not be read
as a finding until someone does.

## Not gated

Testing a parameter value's window against a modelo-level citation would require
deciding what a corpus-level declaration is supposed to assert temporally, which
is a design question the exemption deliberately leaves open. Recording the
population is the deliverable; narrowing the exemption is an owner's ruling.

No production code, registry data or test was changed by this audit.

## Resolved: the 2025 question is the declared 0150 deferral, not a gap

The open question above — why the 2025 revision carries the four rental tiers with
no consumer — is answered, and the answer is that the state is deliberate and
guarded.

| revision | casilla 0150 | producer |
|---|---|---|
| 2024 | `computed` | `renta-2024-capital-inmobiliario-reduccion-arrendamiento-vivienda-art-23-2` |
| 2025 | `manual` | none |

Casilla 0150 is *reducción por arrendamiento de vivienda*, and its 2024 producer
is the only formula in either revision that consumes a `rental-*` parameter. In
2025 the casilla is operator-input and the producer is absent.

That absence is declared. `test_modelo_100_2025_semantic_boundaries.py` names
`("0150", "formula")` among its focus rows and states the rule in its own
docstring:

> The 2025 declarations for casillas 0150, 0613, and 1481 are measured
> cross-revision divergences. They must not acquire a prior-year producer until
> their row-specific legal, input-contract, and independent-value evidence has
> been accepted. These tests exercise the loaded registry graph so an accidental
> formula, profile binding, or Modelo 131 relation cannot be added silently.

The 2024 formula is exactly the prior-year producer that guard forbids inheriting.

So the four unconsumed 2025 tier parameters are not orphaned data: they are the
**data half of a producer being deliberately withheld** pending evidence. The
registry holds the coefficients ready and refuses to wire them until the row's
legal and value evidence is accepted.

**This is not a new finding.** It resolves into the already-open M100 2025 relief
deferral evidence bar. A 2025 filer receives no automatically computed rental
reduction and must supply casilla 0150 as manual input — which is the over-payment
direction, and is precisely the cost the deferral consciously accepts until the
evidence bar is met.

Worth recording for its own sake: this is the second time an investigation has
arrived at M100/2025 casilla 0150 looking like a missing relief. The first time it
was characterised as a regression and wired to compute, breaking 39 registry tests.
This time the guard was read before anything was concluded. The rule that prevents
the repeat — grep the tests for the casilla id before calling a registry state a
defect — did its job on a row reached from an entirely different direction, which
is the strongest evidence available that it is worth keeping.
