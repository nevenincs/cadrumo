---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:45536531bec3764772234d2d1a2d72e544f7a163416f5f7370fdfa177b57f800'
related:
  - "[[2026-08-28-tui-architecture-m390-recargo-total-fourth-tier-audit]]"
---

# `tui-architecture` audit: `M303 transitional-rate grounding is asserted in prose and absent from legal_refs`

## Scope

## Findings

## Recommendations

## Finding

The two RD-ley 4/2024 transitional rungs of Modelo 303's régimen general
devengado block — boxes **[154]** (reducido transitorio) and **[166]**
(super-reducido transitorio) — encode the correct rates, and their grounding is
argued at length in prose. Neither instrument that *establishes* those rates
appears in the machine-readable `legal_refs`.

All four rows across the two 2024-covering revisions declare:

```toml
legal_refs = ["ley-37-1992:art-88", "ley-37-1992:art-91",
              "rd-1624-1992:art-71", "orden-eha-3786-2008:art-1"]
```

LIVA arts. 88 and 91 state the *ordinary* rates. None of the four states 7,5 %
or 2 %.

## The values are correct — a citation defect, not a computation defect

Verified against the bundled corpus directly, not from the file's own comment.
`boe-a-2024-12944-rdl-4-2024-iva-alimentos.html` reads verbatim:

> se mantiene la rebaja del IVA de estos alimentos en los tipos del 5 por ciento
> (pastas alimenticias y aceites de semilla) y del 0 por ciento … hasta el 30 de
> septiembre de 2024. A partir de dicha fecha … se incrementarán los tipos
> impositivos al **7,5 y 2 por ciento**, respectivamente, hasta el 31 de diciembre

The encoded windows match exactly: [154] 5,00 to 7,50 and [166] 0,00 to 2,00,
both flipping at 2024-10-01 and closing 2024-12-31. **No rate should move.**

## Three surfaces disagree, and one is provably false

| surface | says | true? |
|---|---|---|
| the test module docstring | the instrument opening the 5 % window "is **not yet bundled**" | **false** |
| the registry TOML comment | grounding "fully closed with two already-bundled citations … no residual gap" | true in substance |
| `legal_refs` — the only field a gate reads | neither instrument present | — |

Both instruments are catalogued in `registry/aeat/legal/iva.toml` and bundled:
`real-decreto-ley-20-2022-art-72.html` and
`boe-a-2024-12944-rdl-4-2024-iva-alimentos.html`. The excerpt confirms the
comment's window claim verbatim — "Con efectos desde el 1 de enero de 2023 y
vigencia hasta el 30 de junio de 2024".

So the corpus work was done and the comment updated, the test docstring was left
asserting a gap that had already been closed, and the closure was never expressed
where anything can read it. The stale docstring is the actively harmful part: it
directs a reader to bundle a document that is already on disk.

**The 2023 sibling proves the convention.** That revision's row does carry
`real-decreto-ley-20-2022:art-72` in `legal_refs`. This is an omission, not a
design choice.

## Direction

No liability error today. The exposure is the M200-pyme pattern already recorded
in this campaign: a reviewer checking cited article against encoded value finds a
mismatch, and the wrong resolution — move 7,5 % to a rate art. 91 does state — is
more obvious than the right one, which is to add the missing citations. These are
devengado rungs, so such an alignment would move a taxpayer's output VAT.

## Remediation is per-revision — do not apply it uniformly

`real-decreto-ley-20-2022:art-72` carries "vigencia hasta el 30 de junio de 2024",
so it is in force for `2024-hasta-08-y-2t` (Q1/Q2) and out of force for
`2024-desde-09-y-3t` (Q3/Q4). An applicability-window mechanism already excludes
out-of-window entries from snapshots — `test_source_applicability_window.py:163`
asserts exactly that shape for a sibling article — so adding the 20/2022 citation
to the late-2024 revision would be wrong on the law and may be refused.

`real-decreto-ley-4-2024:art-1` is in window for the 10/4T 2024 period and is the
instrument establishing 7,5 % and 2 %.

Owner's decision, not taken here: add `real-decreto-ley-4-2024:art-1` to all four
rows, add `real-decreto-ley-20-2022:art-72` only to the early-2024 revision, and
correct the stale test docstring. This is a citation change on rate rows, so it is
a tax review, and no value may move.

No production code, registry data or test was changed by this audit.
