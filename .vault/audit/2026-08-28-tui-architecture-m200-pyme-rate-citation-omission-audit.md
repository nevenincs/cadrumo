---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:fccfcc30bd18fdae33381c6d97debde559e9c815ffee2240189dacb6aafeb153'
related: []
---

# `tui-architecture` audit: `M200's 2024 pyme rate names its authorities in a comment but not in legal_refs`

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
