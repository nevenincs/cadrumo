---
tags:
  - '#reference'
  - '#registry-temporal-coverage'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:287ff8f903af191b1e8cd20443a592be80d890d25015c798395dcae8bf296db5'
related:
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
---

# `registry-temporal-coverage` reference: `authority grade proposal for 77 ungraded-by-default revisions`

A reviewable promotion proposal, not an attestation. It recommends a rung per
revision and states each recommendation as a sentence a reader can disagree
with. No grade is written by this document, and nothing here is an operator
review. A human applies it, or rejects it.

## Summary

Ninety-seven `revision.toml` files received `authority_grade = "filing"` from a
single bulk insertion whose commit subject concerned MCP surfaces. Twenty-five
of those files carried a human-written "Scheduling/applicability-grade" comment
that the inserted line contradicted two lines above it; those twenty-five have
been transcribed down to the grade their own prose declared, which added no
claim. The remaining **77 carry an unauthored claim**: nobody chose `filing` for
them, and no prose in those files declares any grade.

Each of the 77 resolves one of two ways: build the families the rung requires,
or establish what the revision is actually for. This document addresses the
second. It groups the 77 so the decision is a handful of judgements rather than
seventy-seven, and isolates the ones that cannot be settled from the codebase.

**The recommendations are grounded in what each modelo IS** - who files it,
whether it produces a liability the taxpayer pays, whether this application
would ever emit it. They are deliberately NOT derived from which families each
revision currently holds. A grade read off present content agrees with the
content by construction, which would make the validating check inert; the
family counts below are context for the reader, never the basis of the
recommendation.

### What grounds "who files it"

The user profile schema declares both `entity_type` and `legal_entity_form`, so
this application models individuals and legal entities alike. That puts the
retencion families and the Impuesto sobre Sociedades forms in scope, and leaves
out the declarations that only a bank, insurer, fund or pension manager,
platform operator or very large group ever files. That distinction carries most
of the grouping below.

### Rung mechanics worth knowing before reading the tables

`applicability` is reached immediately: the validator returns no failure for a
revision declared at the floor, because the floor makes no coverage claim to
outrun. `filing` requires **every one of the 19 enrolled families** to be
resolved - populated, or declared not applicable with a reason and citations.
There is no partial credit, so the "blocked" column is the distance to `filing`
and has no bearing on the distance to `applicability`, which is always zero.

Consequently, adopting the recommendation for groups 3 and 4 would legitimately
clear **15** of the 77 refusals immediately, because those revisions would stop
claiming a rung they were never meant to reach. Groups 1 and 2 would keep
refusing, correctly, until their families are built - that is the check working
as designed, not a backlog to clear.

## Group 1 - self-assessed liability, filed by this application's taxpayer

**Recommended rung: `filing` (39 revisions).**

*The taxpayer computes an amount and pays it, and producing that return is the
application's core purpose; if this application is for anything, it is for
these.*

Keeping `filing` here is not ratifying the bulk stamp - it is reaching the same
value deliberately. The refusals persist until the families are built, which is
the intended behaviour for a revision meant to reach filing.

| modelo | revision | domain / cadence | calc_class | DR | emits | blocked |
| --- | --- | --- | --- | --- | --- | --- |
| 100 | `2020` | irpf / annual | - | yes | yes | 4 |
| 100 | `2021` | irpf / annual | - | yes | yes | 2 |
| 100 | `2022` | irpf / annual | - | yes | yes | 2 |
| 100 | `2023` | irpf / annual | - | yes | yes | 2 |
| 100 | `2024` | irpf / annual | - | yes | yes | 2 |
| 100 | `2025` | irpf / annual | - | yes | yes | 2 |
| 111 | `2019-y-siguientes` | irpf / profile_based | - | yes | no | 7 |
| 115 | `2019-y-siguientes` | irpf / quarterly | - | yes | no | 7 |
| 123 | `2019-2023` | cross_tax / quarterly | - | yes | no | 10 |
| 123 | `2024-y-siguientes` | cross_tax / quarterly | - | yes | no | 8 |
| 130 | `2019-y-siguientes` | irpf / quarterly | - | yes | no | 5 |
| 131 | `2019-2023` | irpf / quarterly | - | yes | yes | 5 |
| 131 | `2024` | irpf / quarterly | - | yes | yes | 5 |
| 131 | `2025` | irpf / quarterly | - | yes | yes | 4 |
| 131 | `2026` | irpf / quarterly | - | yes | yes | 3 |
| 151 | `2015-y-siguientes` | irpf / annual | - | yes | no | 10 |
| 151 | `2025-y-siguientes` | irpf / annual | - | yes | no | 10 |
| 200 | `2024-y-siguientes` | is / annual | - | yes | no | 4 |
| 202 | `2019-2022` | is / quarterly | - | yes | no | 6 |
| 202 | `2023-2024` | is / quarterly | - | yes | no | 6 |
| 202 | `2025-y-siguientes` | is / quarterly | - | yes | no | 4 |
| 210 | `2025` | irnr / ad_hoc | - | yes | no | 9 |
| 216 | `2024-y-siguientes` | irnr / profile_based | - | yes | no | 12 |
| 303 | `2009-y-siguientes` | iva / quarterly | - | yes | no | 6 |
| 303 | `2023` | iva / quarterly | - | yes | no | 3 |
| 303 | `2024-desde-09-y-3t` | iva / quarterly | - | yes | no | 3 |
| 303 | `2024-hasta-08-y-2t` | iva / quarterly | - | yes | no | 3 |
| 303 | `2025` | iva / quarterly | - | yes | no | 3 |
| 303 | `2026-y-siguientes` | iva / quarterly | - | yes | no | 3 |
| 349 | `2020-y-siguientes` | iva / profile_based | - | yes | yes | 8 |
| 390 | `2022` | iva / annual | - | yes | yes | 4 |
| 390 | `2023` | iva / annual | - | yes | yes | 4 |
| 390 | `2024` | iva / annual | - | yes | yes | 4 |
| 390 | `2025` | iva / annual | - | yes | yes | 4 |
| 714 | `2021` | patrimonio / annual | - | yes | no | 15 |
| 714 | `2022` | patrimonio / annual | - | yes | no | 15 |
| 714 | `2023` | patrimonio / annual | - | yes | no | 15 |
| 714 | `2024` | patrimonio / annual | - | yes | no | 15 |
| 714 | `2025` | patrimonio / annual | - | yes | no | 15 |

Modelo 303 (6) and Modelo 390 (4) sit in a tree owned by the in-flight export
fragment campaign, and Modelo 714 (5) is being populated concurrently. Those 15
rows are recommendations only; do not edit those trees on the strength of this
document.

## Group 2 - informative or summary declaration this application's taxpayer files

**Recommended rung: `filing` (12 revisions).**

*The taxpayer submits this to AEAT and the application should be able to emit
it, but it settles no liability of its own, so its formula family is honestly
inapplicable rather than merely unbuilt.*

This is the shape the coverage decision record explicitly created room for: an
informative modelo carrying export layouts and no formulas reaches `filing`
legitimately, through a reasoned disposition rather than through population. All
eleven modelos whose manifest declares `calculation_class = "informative"`
already carry that formulas disposition, so the precedent is established and
fully worked.

| modelo | revision | domain / cadence | calc_class | DR | emits | blocked |
| --- | --- | --- | --- | --- | --- | --- |
| 145 | `2012-01-31-y-siguientes` | irpf / ad_hoc | informative | yes | yes | 12 |
| 180 | `2019-2022` | irpf / annual | - | yes | yes | 6 |
| 180 | `2023-y-siguientes` | irpf / annual | - | yes | yes | 4 |
| 184 | `2015-y-siguientes` | informative / annual | - | yes | no | 8 |
| 190 | `2024-y-siguientes` | irpf / annual | - | yes | no | 5 |
| 193 | `2024-y-siguientes` | cross_tax / annual | - | yes | no | 5 |
| 232 | `2016-2017` | is / annual | informative | yes | no | 8 |
| 232 | `2018-y-siguientes` | is / annual | informative | yes | no | 7 |
| 296 | `2024-y-siguientes` | irnr / annual | - | yes | no | 12 |
| 347 | `2008-y-siguientes` | informative / annual | informative | yes | no | 7 |
| 720 | `2013-y-siguientes` | informative / annual | informative | yes | yes | 4 |
| 721 | `2023-y-siguientes` | informative / annual | - | no | no | 11 |

## Group 3 - filed only by financial institutions, managers, platforms or very large groups

**Recommended rung: `applicability` (13 revisions).**

*This application's taxpayer never files these in their own name - they are
submitted by banks, insurers, collective-investment and pension managers,
platform operators, or groups above the country-by-country reporting threshold -
so the application needs to know they exist and when they fall due, and would
never emit one.*

These are the clearest demotions in the set. They are worth scheduling knowledge
because they appear in deadline surfaces and cross-references, and worth nothing
above that.

| modelo | revision | domain / cadence | calc_class | DR | emits | blocked |
| --- | --- | --- | --- | --- | --- | --- |
| 117 | `2019-y-siguientes` | cross_tax / quarterly | - | yes | no | 11 |
| 126 | `2019-y-siguientes` | cross_tax / quarterly | - | yes | no | 11 |
| 128 | `2019-y-siguientes` | cross_tax / quarterly | - | yes | no | 11 |
| 182 | `2007-y-siguientes` | informative / annual | - | yes | no | 11 |
| 187 | `2019-y-siguientes` | cross_tax / annual | - | yes | no | 11 |
| 188 | `2019-y-siguientes` | cross_tax / annual | - | yes | no | 11 |
| 189 | `2025` | cross_tax / annual | informative | yes | no | 13 |
| 194 | `2019-y-siguientes` | cross_tax / annual | - | yes | no | 11 |
| 231 | `2021-y-siguientes` | is / annual | informative | no | no | 14 |
| 280 | `2025` | irpf / annual | informative | yes | no | 13 |
| 289 | `2025` | cross_tax / annual | informative | no | no | 13 |
| 345 | `2025` | irpf / annual | informative | yes | no | 13 |
| 379 | `2024-y-siguientes` | iva / quarterly | informative | no | no | 14 |

Modelo 232 was deliberately placed in group 2 rather than here: related-party
operations are declared by ordinary companies well below any large-group
threshold, so it is a declaration this application's taxpayer plausibly files.

## Group 4 - censal and administrative registers

**Recommended rung: `applicability` (2 revisions).**

*These are register maintenance rather than tax returns, and this application
reads Modelo 036 through censo synchronisation rather than producing it, so
there is no filing artefact to emit in either case.*

| modelo | revision | domain / cadence | calc_class | DR | emits | blocked |
| --- | --- | --- | --- | --- | --- | --- |
| 036 | `2025-02-03-y-siguientes` | censo / ad_hoc | - | yes | no | 11 |
| 840 | `2003-y-siguientes` | iae / ad_hoc | informative | yes | no | 11 |

Modelo 840 is the Impuesto sobre Actividades Economicas alta, baja and variacion
communication, administered municipally and one most autonomos are exempt from.
Its sibling Modelo 848 already sits at `applicability` through prose
transcription, which is corroboration rather than proof.

## Group 5 - cannot determine from the codebase

**No recommendation (11 revisions).** These need a product ruling.

| modelo | revision | domain / cadence | calc_class | DR | emits | blocked |
| --- | --- | --- | --- | --- | --- | --- |
| 136 | `2026` | cross_tax / quarterly | filing | no | no | 11 |
| 185 | `2003-2025` | informative / monthly | - | yes | no | 18 |
| 308 | `2009-y-siguientes` | iva / ad_hoc | - | yes | no | 13 |
| 309 | `2004-y-siguientes` | iva / ad_hoc | - | yes | no | 10 |
| 322 | `2008-y-siguientes` | iva / monthly | - | yes | no | 8 |
| 353 | `2008-y-siguientes` | iva / monthly | - | yes | no | 7 |
| 360 | `2010-y-siguientes` | iva / ad_hoc | - | yes | no | 10 |
| 361 | `2010-y-siguientes` | iva / ad_hoc | - | no | no | 14 |
| 369 | `esquema-exterior` | iva / ad_hoc | - | yes | no | 8 |
| 369 | `esquema-importacion` | iva / ad_hoc | - | yes | no | 8 |
| 369 | `esquema-union` | iva / ad_hoc | - | yes | no | 7 |

Three distinct reasons, kept separate because they need different answers:

**Special-regime IVA autoliquidaciones (322, 353).** Genuinely self-assessed
returns, but only for entities inside the grupo de entidades regime. Whether
this application intends to serve that regime is a scope decision, not a fact
about the modelo.

**Non-periodic and refund IVA surfaces (308, 309, 360, 361).** Each is a real
filing an ordinary taxpayer occasionally makes - a recargo de equivalencia
refund request, a non-periodic liquidation, refunds for non-established
taxpayers. Their frequency in the target population is a product judgement.

**Modelo 369 (3 revisions), the One-Stop-Shop schemas.** Mainstream for
cross-border e-commerce and marginal otherwise. The three revisions are variant
schemas of one regime rather than a temporal sequence, so they should be ruled
on together.

**Modelo 136 and Modelo 185 are listed here because I could not identify them
with confidence.** Neither carries explanatory prose in its revision manifest,
Modelo 136 has no bundled record design, and I declined to infer either from its
number. Modelo 185's span was recently split into a predecessor revision after
its governing orden was found to apply only from 2026, so the 2003-2025 row is
new and its 18 blocked families reflect a revision nobody has built out yet.

## What this document does not claim

It does not claim the recommended rungs are correct - only that each is a
statement about the modelo's nature that a reader can check and reject. It does
not assert any revision has been reviewed. It does not touch the 83 revisions
that declare no export layout: that refusal admits no disposition and shrinks
only when a real layout is authored, independently of any grade.

A revision moved to `applicability` becomes structurally barred from filing
snapshots and surfaces as a visible advisory. Nothing in this proposal grants a
capability; groups 3 and 4 strictly reduce reach, and groups 1 and 2 leave reach
unchanged while the refusals stand.
