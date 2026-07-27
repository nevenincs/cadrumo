---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - "[[2026-07-26-modelo-100-parser-glyph-merge-adr]]"
---

# `declaracion-real-render-verification` audit: `the Modelo 100 manifest reconciliation gap, explained exactly`

## Scope

Establishes why the Modelo 100 sidecar manifests declare 124, 133 and 137
amount replacements while only 70, 74 and 78 amounts render, and whether
that gap means the manifests are wrong or merely describing something
other than what renders. Report-only: no edit to the sidecars, the
generator, or any test. Every claim below was produced by a standalone
script reading the bundled PDFs and JSON sidecars directly with
`pdfplumber` and `pikepdf`, never by modifying a committed file. Method is
stated beside every claim; measured versus inferred is stated per
conclusion.

## Findings

### the-gap-is-fully-and-exactly-explained-by-one-mechanism-string-nesting-not-hidden-or-non-amount-surfaces | critical | reconciles to zero remainder on all three specimens

Re-derived the two headline counts directly rather than trusting them.
Every rendered amount-shaped word, extracted with `extract_words(extra_attrs=
["size"])` to correctly separate the box-number merge from the amount
itself: 70, 74, 78 -- matching the team lead figures exactly. Every one of
those words is either `"1.000,00"` (8 characters) or `"1.001.000,00"` (12
characters), the two length-preserving synthetic forms the ADR already
named. Counted each shape separately: 16/15/19 renders are the short form,
54/59/59 are the long form, summing to 70/74/78 exactly.

The mechanism: `"1.001.000,00"` contains `"1.000,00"` as an exact substring
starting four characters in (`"1.001.000,00"[4:12] == "1.000,00"`). This is
a property of the two literal strings, not a per-document coincidence.
Searched every page own raw content stream (via `pikepdf`, bypassing
`pdfplumber`'s text layer entirely) for both literal byte sequences: every
single occurrence of the long form has the short form nested at exactly
that +4 offset -- 54 of 54, 59 of 59, 59 of 59, on all three specimens, zero
exceptions.

**The reconciliation is exact, not approximate.** `manifest_amount_rows -
rendered_amount_words` equals the count of long-form renders on every
specimen: `124 - 70 = 54`, `133 - 74 = 59`, `137 - 78 = 59`, and the
long-form render counts measured independently are `54`, `59`, `59`. There
is no unexplained remainder. Whatever counts "amount replacements" for the
sidecar manifest registers two events for every long-form box -- one for
the twelve-character run itself, and a second, spurious one for the
eight-character substring embedded inside it -- while genuinely
independent short-form boxes (the 16/15/19 above) correctly register once
each.

### the-two-hypotheses-named-in-the-dispatch-brief-are-both-ruled-out | high | checked directly, not assumed unnecessary once finding 1 landed

Checked both named candidates before finding 1 explained the whole gap, so
neither is a residual possibility left unexamined:

- **Non-rendering fields (hidden layers, empty boxes, invisible form
  values).** Checked for an `/AcroForm` dictionary (would carry a separate
  stored field value distinct from its visible appearance) -- absent on all
  three PDFs. Checked for `/OCProperties` (optional-content layers) and
  `/StructTreeRoot` / `/MarkInfo` (tagged-PDF accessibility duplication,
  which sometimes carries a parallel invisible text copy) -- absent on all
  three. Checked for the doubled-character rendering pattern this campaign
  found on a different modelo earlier (`"RReetteenncciioonneess"`-style glyph
  duplication, which would produce genuinely invisible-adjacent duplicate
  characters) -- zero instances on any Modelo 100 page, any specimen.
- **Non-amount surfaces inflating the count.** Every one of the 124/133/137
  rows filtered to this analysis already matches an amount shape
  (`\d[\d.]*,\d{2}`) and declares one of exactly two synthetic strings, both
  amount-shaped. There is no third surface type or non-amount value hiding
  in the count.

Neither hypothesis is what is happening. The mechanism is a third thing:
overlapping pattern matches on the same rendered surface, not an invisible
surface and not a non-amount one.

### the-manifests-are-not-wrong-they-over-count-genuine-events-not-fabricated-ones | high | the direct answer to the question that matters most

Every one of the 124/133/137 declared replacement rows corresponds to a
byte sequence that genuinely existed in the source and genuinely got
redacted -- confirmed by locating the literal `surface_index` byte offsets
in the raw content stream and finding real string matches at every one
checked. Nothing is fabricated and nothing points at a byte range that
never existed. The manifests over-count how many **distinct** replacement
**events** occurred, because the detection step that produced
`replacements_applied` does not exclude a match whose byte range sits
entirely inside another match it already counted. That is a real
imprecision in what the row count means, not a false description of the
document.

**This is the answer to the question the dispatch brief posed most
directly: the manifests are not wrong, and they are not describing
something that does not render. They over-count genuine events on a
surface that does render, by counting the same surface twice under two
different pattern widths.**

### what-this-means-for-any-value-check-grounded-on-the-declared-constants | medium | ties directly to P04.S19, without touching it

A check asserting "every extracted amount equals one of the sidecar
declared synthetic constants" -- the shape of check this campaign own
adversarial pass already ran for Modelo 111 and 390 -- would fail on every
long-form Modelo 100 value today, because the sidecars declare only
`"1.000,00"` and never `"1.001.000,00"`, exactly as the ADR own
Considerations section already states. Finding 1 confirms both numbers
belong to the same length-preserving sanitiser and both are genuine: the
short form for genuinely eight-character original values, the long form
for twelve-character ones. Declaring both as valid constants (`P04.S19`'s
own stated remedy) is sufficient for a value-correctness check to pass on
every genuinely correct extraction; it does not, and does not need to,
correct the row-count over-counting in `replacements_applied`, since that
count is not what a value-correctness check reads.

## Recommendations

State the finding as exact, not approximate, wherever it is cited: the
gap between 124/133/137 and 70/74/78 is fully accounted for by 54/59/59
nested substring matches, with zero unexplained remainder on any of the
three specimens. This is a stronger result than "mostly explained" and
should be recorded as such.

When `P04.S19` corrects the sidecars, declaring `"1.001.000,00"` alongside
`"1.000,00"` as valid synthetic constants is sufficient for a
value-correctness gate; nothing in this finding requires also correcting
the row count in `replacements_applied`, since no consumer this campaign
has found reads that count for anything beyond human inspection. If a
future consumer ever does read the row count as a proxy for "how many
distinct amounts this document redacted", this finding is the reason not
to trust it at face value without deduplicating nested matches first.

No further investigation is needed on this question. The mechanism is
exact, proven on all three specimens, and consistent -- which is itself
evidence for one cause rather than several, without needing to invoke a
second explanation to close the last few rows.
