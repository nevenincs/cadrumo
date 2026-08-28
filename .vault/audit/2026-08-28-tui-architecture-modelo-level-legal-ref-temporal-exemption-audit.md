---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:3cd0b4d5c494dec34cad3fcab994f79779ef6bb6828d771aed003826a95068fa'
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
