---
tags:
  - '#audit'
  - '#calculation-correctness-campaign'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:c5910e3876b1cbd8312477ce5734b63f9680d141d1168482d5885dcefb736576'
related:
  - "[[2026-08-28-registry-relation-and-export-integrity-formula-member-continuity-across-revisions-audit]]"
---

# `calculation-correctness-campaign` audit: `Registry rounding discipline is coherent; the ratio dividing line is the substance`

## Scope

## Findings

## Recommendations

## Why rounding is a direction question

Rounding a cuota up over-charges and rounding it down under-charges, so every
rounding rule in the registry is a small standing bias unless it is symmetric or
legally mandated. This sweeps all 1457 compiled formulas and asks, of each
combination, which way it fails.

## The full picture

| target `data_type` | rounding | count | verdict |
|---|---|---|---|
| money | `money-2` | 1151 | correct — `ROUND_HALF_UP`, symmetric about zero |
| decimal | `money-2` | 251 | correct, same rule |
| ratio | `money-2` | 24 | correct — every one is percentage-valued, see below |
| ratio | *(none)* | 10 | correct — fraction-valued rates that must not be rounded |
| ratio | `integer-ceiling` | 6 | correct — prorrata, LIVA art. 104.Dos, now gated |
| integer | `integer` | 3 | non-money counts |
| integer / boolean | *(none)* | 6 | non-money |

**Money-typed targets quantised to whole units: zero.** That was the sweep's
sharpest question — a money box rounded with `integer` would silently drop cents
on every filing — and nothing does it.

## The dividing line the registry gets right everywhere

`ratio` covers two different things, and rounding must treat them oppositely.

A **percentage-valued** ratio — M100's tipo medio de gravamen, computed as
`(cuota * 100) / base` — belongs at two decimals, which is how AEAT prints it.
All 24 cent-rounded ratio targets are of this kind; every one of their
expressions scales by a literal 100.

A **fraction-valued** ratio — M303's transitional rate boxes [154]/[166], M210's
resolved tipo de gravamen — must not be rounded at all. Cent-rounding 0,075 would
yield 0,08: a rate of 7,5 % becoming 8 %, half a percentage point of extra tax on
every euro of base it touches. All 10 such formulas correctly declare no
rounding.

The registry makes that distinction correctly in every one of the 34 instances.
It is not stated anywhere as a rule, which is the only reason it is worth writing
down here: a future ratio target that copies the wrong sibling's rounding would be
a quiet rate error, and the two siblings sit in the same table.

## Not gated, and why

The percentage-versus-fraction test used here is a **heuristic** — it looks for a
literal 100 in the expression. A percentage-valued ratio could legitimately be
produced from a parameter already expressed in percent, with no literal 100
anywhere, and would be flagged wrongly. Gating a heuristic manufactures false
positives and trains the next author to widen an allowlist, so this is recorded
rather than enforced.

The one rounding rule that *is* enforced is `integer-ceiling`, gated separately:
it is the only code whose correctness depends on the sign of its operand, and its
precondition is stated as mandatory by the production docstring rather than
inferred.

No production code, registry data or test was changed by this audit.
