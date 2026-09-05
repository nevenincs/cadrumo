---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-05'
modified: '2026-09-05'
body_schema: 'body-v2'
body_hash: 'sha256:edd2e1eda6ba4f3206044508027c1173f3ee61e58c4ee809c37d63b543a948eb'
step_id: 'S433'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Close the ca and hu label gap behind es for M200/2024, and say what blocks the rest. Three Catalan and one Hungarian label were simply absent for casillas es already carries; two of the Catalan ones are genuine cognates whose Spanish and Catalan forms are the same word, so they take an allowlist justification rather than an invented difference. The remaining 24 Hungarian gaps sit behind an ellipsis-truncated Spanish source and cannot be translated as fragments.

## Scope

- `src/cadrumo/locales/ca/modelo/schema/200.yml`
- `src/cadrumo/locales/hu/modelo/schema/200.yml`
- `src/cadrumo/locales/_intentional_identical.json`

## Changes

Catalan and Hungarian were behind Spanish on casillas Spanish already carried:
ca by 3, hu by 25. That is a translation gap rather than a grounding one, so it
looked like the last unblocked slice. It is mostly not.

24 of the 25 Hungarian gaps have an ELLIPSIS-TRUNCATED Spanish source. Composing
a translation segment-by-segment surfaced it plainly: the segments to author
came out as "Aume...", "D...", "Te...", "To...". There is nothing to translate
there -- the Spanish label is cut mid-word, so any Hungarian written against it
would be a translation of a fragment. Those 24 are blocked behind a defective
source, not behind Hungarian.

The 4 that are clean were written. Two of them then failed the translation
honesty gate, correctly: "Cooperativa protegida" and "Gran empresa" are spelled
the same in Catalan as in Spanish. Forcing a difference would invent terms
Catalan does not use, so they took the sanctioned per-key allowlist
justification instead. That is what the allowlist is for, and each entry says
which word is shared and why.

Catalan now matches Spanish and English at 16 missing. Hungarian is at 40,
lagging by exactly the 24 truncated ones.

## Notes

No new gate this Step, and no teeth claimed. The owning gates are the existing
runtime localization gate, which still fails on the 16 unadjudicated casillas,
and the translation honesty gate, which now passes on everything added here.

The honesty gate's remaining failures are unchanged and not from this work:
ca 16, es 15, hu 9 keys identical to English, all under tui.aeat_sync.* and
tui.home.*, exactly the counts measured before any of this began.

A SYSTEMIC DEFECT IS NOW VISIBLE AND IS NOT FIXED HERE. 381 shipped Spanish
labels in this revision are ellipsis-truncated, cut mid-word by whatever
captured them. They pass their gates today because nothing compares a shipped
label against the record design, and the digest gate only covers pinned
casillas. The page selector validated in the previous Step could repair them --
it reproduces the correct cell for 91.3% of labelled casillas -- but that means
rewriting labels that currently ship and pass, across a filing-bound surface,
which is a decision rather than a cleanup.
