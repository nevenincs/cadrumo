---
tags:
  - '#audit'
  - '#registry-legal-grounding-windows'
date: '2026-08-28'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:203c12757ff6bce5a67f2a670f9973bc2679fce971ffecff90ffa0903943b940'
related: []
---

# `registry-legal-grounding-windows` audit: `M200's 2024 pyme rate names its authorities in a comment but not in legal_refs`

## Finding

`is.modelo-200.tipo-gravamen-pyme` in the Modelo 200 **2024** revision declares:

```toml
legal_refs = ["ley-27-2014:art-29"]
required_text = ["tipo de gravamen"]
```

and encodes three date-windowed rate regimes: **23 %** for periods initiated in
2024, **21 % / 22 %** for 2025, and **19 % / 21 %** for 2026.

LIS art. 29 states none of those figures. Its bundled excerpt gives the current
steady state — 25 % general, micro-empresa 17 % to 50.000 then 20 %, art. 101
entities 20 %, new entities 15 %, cooperatives general minus three points,
non-profit 10 %, credit and hydrocarbons 30 %.

**The values are correct and the file knows why.** Its own comments name the
establishing provisions:

> Periods initiated in 2024: 23 % flat rate (LIS Art. 29 pre-2025 pyme regime;
> **Ley 31/2022 Art. 39** reduced rate for INCN < 1M, in force for ejercicios
> iniciados en 2024). The two-tranche micro-empresa scale was introduced for
> periods initiated in 2025 by Ley 7/2024 (LIS art. 29.1) with the transitional
> schedule of **LIS DT 44ª** (21 %/22 % in 2025, 19 %/21 % in 2026).

Neither `ley-31-2022:art-39` nor `ley-27-2014:dt-44` appears in `legal_refs`. Both
exist in the catalogue as excerpt-tier entries — `ley-31-2022-art-39.html` and
`ley-27-2014-dt-44.html` — so the citation could be made today with no new corpus
work.

The grounding rule requires the `legal_refs` to declare the provision that
*establishes* the value. Here the knowledge is present, correct and written down —
in prose, where no gate reads it.

## The sibling revision is better, and the same modelo shows both failure modes

The `2025-y-siguientes` revision of the same parameter cites
`["ley-27-2014:art-29", "ley-27-2014:dt-44"]`, and `-pyme-display` adds
`ley-31-2022:art-39`. So the correct citations exist in the tree, on the adjacent
revision.

That makes Modelo 200's parameter file a compact illustration of both citation
failure modes at once:

- **Omission** — this row, three regimes grounded on one article that states none
  of them.
- **Dilution** — `is.modelo-200.tipo-gravamen-general`, eighteen `legal_refs` of
  which one establishes the rate, recorded separately.

Both were reached by an author who understood the law; neither is a
misunderstanding. What they share is that nothing checks the relationship between
a citation and the value it grounds.

## Direction

No computation error. The 2024 rate is 23 %, which is right, and the phased
brackets match DT 44ª. This is a grounding defect, and the exposure is the one
this campaign has recorded repeatedly: a reviewer checking the cited article
against the encoded value finds a mismatch, and the correct resolution — add the
missing citations — is less obvious than the wrong one, which is to change the
value to something art. 29 does state.

Note the 2025 and 2026 brackets carried by a **2024** revision are inert: period
resolution sends 2025 and 2026 filings to their own revisions. They are
documentation of the schedule rather than live values, which is harmless, but it
means the missing DT 44ª citation is not load-bearing for any filing this revision
serves. The missing `ley-31-2022:art-39` is.

## Remediation — owner's decision, not taken here

Add `ley-31-2022:art-39` to the 2024 row's `legal_refs`, matching what the sibling
`-pyme-display` row already does, and `ley-27-2014:dt-44` if the inert forward
brackets are to be kept. Both targets are excerpt-tier, so the resulting citation
would be tightly checkable — unlike the whole-law citations recorded elsewhere.

This is a citation change on a rate, so it is a tax review rather than a text edit,
and the value must not move: 23 % is correct for periods initiated in 2024.

## How it was found

`tmp/tight_match.py`, restricted to rows every one of whose citations resolves to
a provision excerpt — the only tier where "the cited source does not state this
value" carries information. 181 rows qualify; 169 have every encoded value stated;
12 do not, and this is one of them.

The restriction is what made it visible. The same parameter is invisible to a
sweep over all citations, because most of the population cites whole consolidated
laws where every numeral occurs somewhere.

No production code, registry data or test was changed by this audit.

## Second instance, different modelo: M303's transitional rates lost their RD-ley

The same omission appears on Modelo 303, and there it is unambiguous because an
adjacent revision does it correctly.

`m303-dr303-154-transitional-rate-percent` and its `-166` sibling carry the
RD-ley 4/2024 foodstuffs steps — 5,00 → **7,50** and 0,00 → **2,00**, verified
correct against the law and against the companion `iva/recargo-rates.toml`.

| revision | `legal_refs` |
|---|---|
| `2023` | LIVA 88, LIVA 91, RD 1624/1992 art. 71, Orden EHA/3786/2008 art. 1, **`real-decreto-ley-20-2022:art-72`** |
| `2024-hasta-08-y-2t` | the four framework refs only |
| `2024-desde-09-y-3t` | the four framework refs only |

The 2023 revision cites the RD-ley that opened its 5 % window. Both 2024
revisions dropped the RD-ley entirely — and they are the revisions carrying the
7,50 and 2,00 values that **RD-ley 4/2024** established. Their four remaining refs
are the IVA framework (repercusión, tipos, reglamento, the form's Orden); none
states a transitional rate.

The citation is available today: `real-decreto-ley-4-2024:art-1` is in the
catalogue, and its corpus states **"7,5 por ciento"** and **"2 por ciento"**
verbatim. `real-decreto-ley-20-2022:art-72` is an excerpt-tier entry, which is why
the 2023 row passes the tight sweep while the 2024 rows do not.

### What the pair of instances shows

Both are omissions of the *establishing* provision while the *framework* refs are
kept, and in both the correct citation exists in the tree:

- M200 2024 pyme — the establishing provisions are named in a code comment.
- M303 2024 transitional — the establishing provision is cited by the **previous
  revision** of the same parameter.

So neither is a gap in knowledge or in the corpus. The recurring shape is that
citations are **carried forward across revisions and then edited**, and the
provision that makes a value true is the one most easily lost, because it is the
one that changes when the value changes. The framework refs survive precisely
because they are stable and generic — and they are the ones that state nothing.

Direction is unchanged: values correct, grounding weaker than the record implies.
Remediation for both is additive — restore the establishing citation, change no
value.

## The sweep is fully triaged: two actionable items out of 181 rows

`tight_match` judged 181 parameter rows — every one of whose citations resolves to
a provision excerpt — and 169 had every encoded value stated in the cited text.
All twelve misses have now been read by hand and resolve to five causes:

| rows | parameter | verdict |
|---|---|---|
| 2 | `renta-2024/2025-imputacion-inmobiliaria-year-days`, 365 absent | **sound** — a day-count convention; LIRPF art. 85 states no denominator. Already checked and sound; do not "fix" |
| 4 | `is.modelo-200.tipo-gravamen-pyme` and siblings | **actionable** — citation omission, this audit |
| 2 | `m303-dr303-154/-166`, 7,50 absent | **actionable** — citation omission, this audit |
| 2 | `m210-pension-tarifa-2025`, 0,08 absent | **sound** — see below |
| 2 | `modelo-360-*-refund-threshold-eur`, 400 and 50 absent | **already recorded** — the probe independently rediscovered the M360 finding established by hand |

### The M210 pension tranche is a derived rate, correctly

TRLIRNR art. 25.1.b states the pension scale as cuotas, not as a first-tranche
percentage:

> Importe anual pensión hasta 12.000 euros, **cuota 960 euros**, resto pensión
> hasta 6.700 euros, tipo aplicable 30 por ciento; importe anual pensión hasta
> 18.700 euros, cuota 2.970 euros, resto pensión en adelante, tipo aplicable 40
> por ciento.

The registry's `0.08` is 960 ÷ 12.000. The law never writes "8 por ciento", so the
absence is real and correct, and the row's `required_text` — which pins 12.000, 30
and 40 — pins everything the text actually states. This is the "value may be
derived" case the probe's own docstring anticipates.

### What the triage is worth

Two actionable items from 181 rows, both additive citation repairs, and no wrong
value anywhere in the excerpt-tier population. That is a useful negative: the
grounding weakness this campaign has documented is concentrated in *what the
record says about a value*, not in the values themselves.

It also bounds the exercise. The same sweep cannot be run over the whole-law-cited
population at all, so this result covers 181 of roughly 458 parameters; the rest
remain uncheckable until either their citations move to excerpts or an anchored
reader exists.

## Correction to the remediation: the windows constrain which citation is addable

Both remediations above said "add the establishing citation" as though the choice
were free. The catalogue windows constrain it, and checking them changes the
advice.

| provision | window |
|---|---|
| `ley-31-2022:art-39` | 2023-01-01 → open |
| `ley-27-2014:dt-44` | **2025-01-01** → open |
| `real-decreto-ley-20-2022:art-72` | 2023-01-01 → **2024-06-30** |
| `real-decreto-ley-4-2024:art-1` | **2024-07-01** → 2024-12-31 |

### M200 — half the advice was wrong

Adding `ley-31-2022:art-39` to the 2024 row is sound; its window covers the 2024
devengo. Adding `ley-27-2014:dt-44` is **not**: DT 44ª enters force on 2025-01-01,
so the revision-scoped window check would refuse it for a 2024 revision.

That is not a defect in the window rule — it is the rule working. It does mean the
2024 revision's forward brackets for 2025 and 2026 are **ungroundable within that
revision**, which strengthens the earlier observation that they are inert
documentation. The honest remediation is to add art. 39 and leave the forward
brackets uncited, or to remove them as documentation the revision cannot support.

### M303 — each 2024 revision has a different citable RD-ley

The two 2024 revisions serve different quarters, and the RD-leyes tile the year at
30 June:

| revision | periods, devengo | citable RD-ley |
|---|---|---|
| `2024-hasta-08-y-2t` | 1T (31 Mar), 2T (30 Jun) | **RD-ley 20/2022 art. 72** |
| `2024-desde-09-y-3t` | 3T (30 Sep), 4T (31 Dec) | **RD-ley 4/2024 art. 1** |

So the earlier statement that "the citation is available today:
`real-decreto-ley-4-2024:art-1`" is right for the `desde-09` revision and wrong
for `hasta-08`, whose periods close before RD-ley 4/2024 takes effect and whose
correct citation is the RD-ley 20/2022 article the 2023 revision already carries.

This sharpens the finding rather than weakening it: **each 2024 revision dropped
precisely the RD-ley its own periods make citable**, and a different one in each
case. Neither is a copy-forward of the other's mistake.

### The general point

Before recommending a citation repair, check the target provision's window against
the revision's devengo. A citation that cannot be added is not a remediation, and
proposing one would send an implementer into a build failure with no explanation.
The window rule is doing useful work here, and in the Modelo 100 savings-scale case
recorded separately it is the same rule that leaves no satisfiable citation at all
— worth holding both facts about it at once.

## The gap is three rows, not one

This audit originally named `is.modelo-200.tipo-gravamen-pyme`. An independent
sweep — every `unit = "percent"` parameter whose citations all resolve to
provision excerpts, checked for whether the cited text states the encoded value —
found the same omission on two further rows of the same revision.

Modelo 200, revision **2024**:

| row | `legal_refs` | encoded values | `dt-44` |
|---|---|---|---|
| `tipo-gravamen-pyme` | `art-29` | (windowed) | **missing** |
| `tipo-gravamen-pyme-display` | `art-29`, `ley-31-2022:art-39` | 23 / 21 / 19 | **missing** |
| `tipo-gravamen-erd-art101` | `art-29`, `art-101` | 25 / 24 / 23 / 22 / 21 / 20 | **missing** |

Revision **2025-y-siguientes** carries `ley-27-2014:dt-44` on **all three**.

So this is not three independent oversights. The citation set was corrected once,
on the later revision, and never backported to 2024. That is a tighter and more
actionable statement than the original single-row finding, and it means a fix
should sweep the revision rather than the row.

## The values remain correct

The sweep's complaint is that 19, 21, 22 and 24 do not appear in the cited
articles, which is true: LIS art. 29 states the steady state and art. 101 defines
the ERD scope, while the phased schedule those numbers come from is DT 44ª. The
encoded ramps match that disposición — 23/21/19 for the pyme display and the
25-to-20 ERD descent — so once again the number is right and the citation is
incomplete.

`is.modelo-200.tipo-gravamen-erd-art101` is worth calling out separately: its six
dated windows run to 2029, so it is the longest forward schedule in the registry
resting on a provision it does not cite.

## Cross-check with the M303 finding

The same sweep independently re-derived the recorded M303 transitional-rate
omission — `m303-dr303-154-transitional-rate-percent`, with 7,50 absent from its
four cited articles. That finding was reached originally by reading the file's
comment; reaching it again from a numeric corpus comparison, by a different route,
raises confidence that both are real rather than probe artefacts.

Of 58 percent parameters judged against excerpt-tier citations, 54 state every
encoded value. The four that do not are these three M200 rows and the M303 pair.

## A fourth row, and two of the flagged values were never real

Re-running the excerpt-tier sweep with bracket values included (`marginal_rate`
and `fixed_addition`, not only scalar `value`) completes the picture.

**A fourth row carries the same gap.** `is.modelo-200.cuota-integra-bracket-erd-art101`
is a bracket table whose every row has `fixed_addition = 0`, so its flagged
0,21 / 0,22 / 0,24 are pure marginal rates. It encodes the same 2024→2029 descent
as `tipo-gravamen-erd-art101` — 25, 24, 23, 22, 21, 20 percent — and cites
`art-29`, `art-30`, `art-101` with no `dt-44`. So the 2024 revision omits the
disposición on **four** rows, not three.

**Two of the values flagged on `tipo-gravamen-pyme` are derived, not cited.** Its
9.500 and 10.500 are `fixed_addition` entries:

- 50.000 × 0,21 = **10.500** (2025)
- 50.000 × 0,19 = **9.500** (2026)

They are the accumulated cuota at the 50.000 tranche boundary, which LIS states
nowhere because it states rates and thresholds, not the accumulated column. Their
absence from art. 29 is arithmetic, not an omission.

The finding is unaffected: the rates 0,19 / 0,21 / 0,22 remain genuinely absent
from the cited articles, and `dt-44` remains the provision that establishes them.

## Correction: the dt-44 remediation this audit proposed would be refused by a gate

Everything above about "add `ley-27-2014:dt-44` to the 2024 rows" is **wrong**,
and the registry is right.

`ley-27-2014:dt-44` declares `effective_from = 2025-01-01`.
`_check_revision_scoped_legal_windows` tests a revision-scoped legal ref against
the revision's **devengo**, and `_legal_window_covers_devengo` states the rule
explicitly:

> A substantive-law reference (a rate scale, a deduction limit, a threshold) must
> be in force AT THE REVISION'S OWN DEVENGO DATE … A redaction that only starts
> partway through the following calendar year, while the return is still being
> filed, did NOT govern the tax period and must not ground it.

DT 44ª is a rate schedule — substantive law — and the modelo 200 **2024**
revision's devengo is 31 December 2024. Adding the citation would be **refused**.
The 2024 revision does not omit dt-44 by oversight; it is structurally forbidden
from citing it.

That also explains the asymmetry cleanly. `2025-y-siguientes` carries dt-44 on
three rows because its devengo is 2025 or later, where the disposición is in
force. The two revisions are each correct for their own period, and what looked
like "a correction never backported" is two revisions obeying the same rule.

## What actually survives

Two things, and both are narrower than what this audit previously claimed.

**1. A real, validator-compatible gap on one row.** `is.modelo-200.tipo-gravamen-pyme`
encodes 0,23 for the 2024 window and cites only `ley-27-2014:art-29`, which states
the 25 % general rate and not 23 %. Its siblings `-pyme-display` and `-erd` both
cite `ley-31-2022:art-39` for that same 23 %, and art. 39 declares
`effective_from = 2023-01-01`, so it **is** in force at a 2024 devengo and can be
cited. That is the fix: one row, one citation, no value moves.

**2. Structurally ungroundable inert data.** The 2024 revision carries forward
windows for 2025, 2026 and beyond whose establishing provision cannot be cited in
that revision by construction. Period resolution never reaches them — 2025 filings
resolve to their own revision — so they are documentation, not live values. They
sit in a state no citation can legitimise. Whether to delete them or accept them
as annotation is an owner's call; what cannot happen is grounding them where they
are.

## What this says about the method

Three ticks grew this finding from one row to four on the strength of a numeric
corpus comparison, and the fourth-row extension was correct as an observation and
wrong as a defect. The presence check sees that a cited article does not state a
value; it cannot see that the provision which does state it was not yet law when
the period closed.

The campaign's own rule covers this and I did not apply it early enough: when two
gates or two rules conflict, report, do not pick. The grounding rule says cite the
provision that establishes the value; the window rule says never cite a provision
that did not govern the period. For an inert forward-dated value those cannot both
be satisfied, and that tension is the finding — not a missing citation.
