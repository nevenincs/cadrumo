---
tags:
  - '#adr'
  - '#modelo-100-parser-glyph-merge'
date: '2026-07-26'
modified: '2026-07-27'
related:
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
  - '[[2026-07-26-declaracion-real-render-verification-campaign-close-honesty-review-audit]]'
  - '[[2026-07-27-declaracion-real-render-verification-ledger-safe-fix-mechanisms-for-modelo-100-audit]]'
---

# `modelo-100-parser-glyph-merge` adr: `how to stop the parser fabricating amounts from merged box-number glyphs` | (**status:** `accepted`)

## Problem Statement

Every value the parser extracts from a real Modelo 100 declaration is fabricated,
and the profile reports full coverage while doing it.

AEAT renders the printed box number at 6pt physically overlapping the 9pt amount.
pdfplumber's text extraction merges the two runs by x-position into a single word,
so casilla `0545` — printed `1.001.000,00` with box number `0545` beside it —
extracts as `Decimal('10010000.50405')`. All 21 targets behave this way on all three
bundled real specimens, 63 of 63, and because coverage counts a parsed value rather
than a correct one, the profile scores 21 of 21 against a `min_coverage` of 1 and
passes.

This was invisible for as long as it existed. The generated corpus prints amounts
without overlapping box numbers, so it never reproduced the merge, and the existing
tests were written to assert `isinstance(..., Decimal)` rather than a value — a
weakening that made the defect load-bearing on a green suite. The profile TOML
recorded it as known and accepted.

It cannot be fixed from the registry. A profile can choose a `match_strategy`, and
none of them can express this layout: the box number's bounding box is nested inside
the amount's, so all three `bbox_anchored` offsets fail by measurement. The
contamination happens during word assembly, upstream of anything registry data can
say.

## Considerations

- The defect is confined to Modelo 100 within the declaración estate. A prototype
  size-aware text path was measured across 21 specimens and 18 profiles: only Modelo
  100 changes, every other modelo byte-identical.
- The size discriminator is clean. `extract_words(extra_attrs=["size"])` separates
  the runs exactly — `'1.001.000,00'` at 9.0 and `'0545'` at 6.0 — and the twelve
  nine-point glyphs are contiguous, so the amount is one rendered run and not itself
  a merge.
- Size-aware segmentation **alone makes Modelo 100 worse, not better**. With the
  tokens correctly separated, the line ends on the box number, `named_label` captures
  the last token, and the blank-box guard correctly reports the target missing. The
  profile then extracts nothing and, against a floor of 1, refuses every real render
  — the Modelo 303 pathology inverted.
- A prototype of the second half — if the last token is the target's own printed box
  number and a well-formed amount precedes it, that amount is the value — recovers 19
  of 21 targets across all three specimens with zero fabrications and only the two
  legitimate printed forms. Two stragglers are believed an artefact of the prototype's
  crude regex rather than of the rule.
- The sanitiser that produced these specimens is length-preserving, writing
  `1.000,00` into eight-character fields and `1.001.000,00` into twelve. The sidecar
  manifests declare only the first, so any check grounded on the declared constant is
  checking against an incomplete description of the document.

## Considered options

**(A) Fix it in the registry profile.** Not available. Measured on casilla `0545`:
amount `x0=513.97 x1=566.51 top=144.80 bottom=153.80`, box number `x0=552.66
x1=566.00 top=147.20 bottom=153.20`. `right_of_number` requires `513.97 > 566.00`,
`left_of_number` requires `566.51 < 552.66`, `above_number` requires `153.80 <
147.20`. All three are false. A new anchor mode would be a schema change, which is
this ADR's subject matter anyway.

**(B) Size-aware segmentation only.** Rejected on measurement: it converts silent
fabrication into total refusal for Modelo 100. Refusing is better than fabricating,
but it is not a fix and it would strand the modelo.

**(C) Size-aware segmentation plus a trailing-box-number capture rule.** The
prototyped combination, and the only measured path to correct values. It is what
this record exists to decide, because it is three coupled changes rather than one
fix. **Chosen, in the word-level form recorded as D1** — applied to word extraction
inside the parser rather than to the shared text primitive.

**(E) Split the merged token at capture, changing no extraction at all.** Proposed as
the most attractive candidate and **refuted by measurement**, which is worth recording
because it was the option that would have cost nothing. It assumed the merged text was
the amount followed by the box number, recoverable by a string operation. It is not.
Casilla `0545` extracts as `1.001.0000,50405`, not `1.001.000,000545`: the box
number's bounding box sits *inside* the amount's span, so the digits are interleaved by
x-position and **the correct amount is not a substring of the merged text at any
position**. No capture-time string rule can recover it. The trailing-box-number rule
only becomes applicable once the runs are already separated, which is precisely what
requesting the size attribute does.

**(D) Leave it, with the exclusion pinned.** The current state. Modelo 100 is
excluded from the real-render gate with the exclusion evidenced rather than assumed,
so nothing reports it as verified. Acceptable indefinitely, and the correct default
until (C) is decided — but it leaves a modelo whose every extracted value is wrong.

## Decisions

**D1 — The fix is word-level, lives entirely in the declaración parser, and does not
touch the shared primitive.** Decided 2026-07-27, once a mechanism was found that
answers Q1's narrow reopened form.

The premise that made Q1 look blocking was wrong. Declaración has **two independent
extraction axes**, not one. The shared `adapters/inbound/pdf` primitive backs only the
text-string functions — the ones ledger and borrador call. The word-extraction
functions call pdfplumber **directly inside the parser**, never through the shared
module, and are not in either consumer's import graph. So an isolated pathway already
exists and runs in production today; it simply does not request the size attribute.

The mechanism is therefore: request size on word extraction, have `named_label`
capture consult that word data for amount-kind targets, and apply the
trailing-box-number rule there. Text assembly never changes, so **ledger and borrador
are untouched by construction rather than by measurement** — which is a stronger
guarantee than any before-and-after comparison could give.

This supersedes the framing that Q1 blocked everything. Q2 narrows with it: the
capture change is confined to one strategy's implementation rather than altering what
"the value on this line" means estate-wide. Q3 is unaffected and still governed by D2
of the parent record.

**What is not yet cleared, and must be before this lands.** The same word-extraction
function backs `bbox_anchored`, which carries the currently-passing real-render gate
for Modelos 390, 111 and 190. Adding the size attribute *does* change the returned
word lists there — header and footer text reorganises on 390, duplicate-match ordering
swaps on 111. Narrowed by direct probe: every specific box-number-pattern match on all
three returns identical text and coordinates, with only list order differing where
there were two hits. That is real evidence the risk is narrow and it is **not** the
same as re-running the committed gate, which the probe could not do. Re-running it is
the precondition for landing.

The three coupled decisions, stated so they are not mistaken for one:

**Q1 — May the shared inbound-PDF primitive change its word segmentation?**
**Answered: no, not by the prototyped mechanism.** The fix belongs in
`adapters/inbound/pdf/_pdfplumber.py`, not in the declaración parser. That primitive
has three production consumers: the declaración adapter (measured — only Modelo 100
moves), the borrador adapter (undecidable — its corpus is wholly generated), and the
ledger evidence text layer (measured — a real invoice's line structure changes, and
that path parses invoice amounts by label-anchored regex). See the two step results
below. Q1 is reopened in a narrower form: find a mechanism that leaves the ledger path
byte-identical, or scope the change to the declaración entry point rather than the
shared primitive.

**Q2 — May the `named_label` capture contract change estate-wide?** The trailing-
box-number rule changes what "the value on this line" means for all 158 `named_label`
targets across the estate, not only Modelo 100's 21. That is a semantic change to a
shared contract and needs its own evidence.

**Q3 — What floor may Modelo 100 carry afterwards?** The prototype lands 19 of 21, so
the current floor of 1 would still refuse. Under the governing D2 a floor may not be
set from a single filer's specimens, and all three bundled specimens are one filer.
This may be unanswerable until a second filer's render exists.

## Implementation

Not implemented, and deliberately so. What implementation would require, in order:

1. Measure the borrador adapter's consumers of the shared primitive the way the
   declaración estate was measured — per specimen, before and after, byte-identity as
   the pass condition.
2. Measure the ledger evidence text layer the same way. This one reads taxpayer
   financial documents, so a segmentation change alters what evidence is extracted
   from invoices and receipts.
3. Only then answer Q1. If either consumer changes, the fix needs a different shape
   or a scoped entry point rather than a change to the shared primitive.
4. Answer Q2 on its own evidence, across the 158 `named_label` targets rather than
   Modelo 100's 21.
5. Answer Q3 last, and only if a second filer's render exists; otherwise record the
   floor as an evidence gap under D3 rather than setting one.

Until step 3 is answered, option (D) stands and Modelo 100 remains excluded from the
real-render gate with its exclusion evidenced.

### Step 1 result, measured 2026-07-26: the borrador question is undecidable, and why

Step 1 was run and it does not return an answer. It returns the reason there cannot
be one yet, which is more useful.

Measured across all three bundled borrador Modelo 100 fixtures: mixed font sizes are
present (9.0, 10.0, 11.0), but there are **zero** small-over-large x-range overlaps on
any shared row, and **zero** malformed money-shaped tokens — no instance of the
comma-not-two-digits-from-the-end signature the declaración merge produces.

**That clean negative is worthless as evidence, and must not be read as "the borrador
is clean".** All three fixtures carry `Producer = ReportLab PDF Library`, are one page
and roughly 1.9 KB, and yield 49 words each; the generator that made them,
`_generate.py`, sits in the same directory. They are this project's own output. A
generated fixture cannot exhibit a defect that arises from AEAT's rendering, so the
probe confirms only that our generator does not overlap glyphs — which was never in
question.

**The repository holds no real AEAT borrador render of any modelo.** So Q1's borrador
half is blocked on exactly the evidence gap that governs the rest of this work, and
option (D) stands for that reason rather than for want of effort.

Two further findings fell out, and both are worse than the blocked measurement:

- **The borrador corpus reproduces the structural weakness that hid the original
  defect**, one layer over. It is authored to match the extractor, so a green borrador
  suite measures the generator's conventions rather than AEAT's — the same condition
  that let six unprintable casillas survive in the Modelo 303 profile for months.
- **Borrador fixtures carry no provenance sidecars at all**, and the provenance gate
  scans only `justificantes/`. So they are outside the fixture-provenance discipline
  entirely: nothing declares what they are, and nothing would notice if a real
  specimen were swapped in or a synthetic one swapped out. That is a weaker position
  than the declaración corpus was in even before this campaign started.

### Step 2 result, measured 2026-07-26: the shared-primitive change is NOT safe as prototyped, and Q1 is answered

Unlike the borrador corpus, the ledger evidence corpus contains genuinely external
documents with declared provenance, so this question was answerable. Measured across
all nine PDFs it consumes — four adversarial synthetics, a scanned invoice, a real
ZUGFeRD invoice from `mustangproject`, and three N26 bank statements — comparing
today's `page.extract_text()` against a size-aware variant, page by page:

- **13 pages of N26 bank statements: byte-identical.**
- Adversarial and scanned fixtures: identical or unreadable either way.
- **The one real text-native invoice changed on both of its pages.**

**Correction, 2026-07-27.** An earlier revision of this section called those N26
statements *real* and cited them as the stronger half of the evidence, at 13
pages against the invoice's n=1. They are not real. They are generated by
`fixtures/financial/n26/_generate.py`, and carry `Producer = reportlab`,
`Creator = aeat fixture generator`. Their being unchanged is therefore worth
close to nothing: a fixture this project authored will not exhibit a third
party's rendering quirks, which is the same blindness that makes the borrador
corpus unable to answer its half of Q1.

So the real evidence for Q1 is **n=1** in total, not n=1 plus a reassuring 13.
The conclusion is unaffected — the single genuinely external document changed,
and that is what answers the question — but the confidence it was reported with
was borrowed from fixtures measuring our own generator. The error was made in
the same paragraph that correctly flagged the invoice half as n=1, which is
precisely how this class of mistake survives: a caveat placed on the weak half
lends unearned credibility to the half beside it.

The change is bounded and worth stating precisely, because "changed" alone would
overstate it. Character counts are identical (1203 and 573 unchanged), no numeric
token is lost or gained, and page 2's numeric sequence is identical. What moves is
**line grouping and reading order**: `2 Joghurt Banane 5,5000 50Stk 7% 275,00` becomes
`2` on its own line followed by the rest, and a heading relocates.

**That is enough to answer Q1 as no.** The evidence text feeds
`_evidence_draft.build_invoice_draft`, which parses the supplier tax id, invoice
number, date, taxable base, IVA rate, IVA amount and grand total by **label-anchored
regex over the text** — mechanically the same class as `named_label`, and dependent on
a label staying adjacent to its value. A reordering that separates the two would
silently change a parsed invoice amount. On this specimen the labelled amounts survive;
one specimen is not a licence.

**The constraint is on the mechanism, not the goal.** The probe used
`extract_text(extra_attrs=["size"])`, which splits words on size change and alters line
assembly as a side effect. A narrower implementation — splitting words for capture
while preserving line assembly, or applying size awareness only on the declaración
entry point rather than in the shared primitive — may well leave the ledger path
byte-identical. That is the design question the fix now has to answer, and it is a
better-posed question than the one this record started with.

So: Q1 is answered no for the prototyped mechanism, and reopened as "find a mechanism
that is byte-identical here". Option (D) continues to stand.

One measurement caveat, stated because it bounds the result: the corpus holds exactly
**one** genuinely external text-native document, the ZUGFeRD invoice. The scanned
specimen has no usable text layer, and the adversarial fixtures and the N26 statements
alike are this project's own generated output. The evidence for this conclusion is
therefore n=1 across the whole corpus.

That is a thin basis for a decision, and it is stated rather than dressed up. It is
enough to refuse the prototyped mechanism — one real document changing is sufficient to
show the change is not transparent — but it is not enough to characterise *how often* or
*how badly* real documents would be affected. A second external text-native invoice
would materially improve it.

## Constraints

The governing `declaracion-real-render-verification` decisions bind here. D2 governs
Q3. D3 means Modelo 100 stays a recorded evidence gap until a render verifies it
rather than a fix asserting it.

The two unmeasured consumers are not equivalent in risk. The **ledger evidence text
layer** extracts text from taxpayer financial documents, and a segmentation change
there alters what evidence is read from invoices and receipts. The **borrador**
adapter parses Modelo 100 draft summaries — which raises a question this record
cannot answer and should not assume: if AEAT renders borrador box numbers the same
way it renders declaration ones, the borrador extractor may carry the identical
defect, unnoticed for the same reason. That is a lead, not a finding.

## Rationale

The reason this is not a bug fix is that its second half is a contract change and its
first half is a shared-primitive change, and neither was visible from where the defect
was found. The original grant to change the parser was issued on the belief that word
assembly was at fault; `named_label` reads the text path, so that change would not have
touched Modelo 100 at all. The correction came from tracing the call rather than from
reading the description, which is the only reason the scope is now right.

Option (D) is the honest default precisely because (C) is attractive. A prototype that
recovers 19 of 21 with zero fabrications is convincing, and convincing is what makes it
dangerous to land against two unmeasured subsystems on the strength of a third.

## Consequences

Modelo 100 remains excluded from the real-render gate, with every extracted value on
its real specimens known to be wrong. That is a documented hole, not a silent one, and
it is worse than it sounds only if someone mistakes the exclusion for a pass.

Answering Q1 requires measuring the borrador and ledger-evidence consumers the way the
declaración estate was measured. That measurement is the gating work, not the fix.

If the borrador lead proves out, this stops being a Modelo 100 declaration defect and
becomes a rendering-convention defect affecting every AEAT surface that prints a box
number beside an amount, which would change the shape of the answer. As measured, the
lead can be neither confirmed nor refuted: the borrador corpus is wholly generated, so
it is structurally incapable of exhibiting the defect. The lead stays open rather than
closed, and anyone who later reads the borrador suite as green should read this
paragraph first.

The borrador corpus's own gaps are now the nearer problem: no provenance sidecars, no
gate coverage, and a corpus authored to match its extractor. Those are fixable without
a real render, unlike the question they currently block.

## Codification candidates

None promoted. Project rule codification is retired by operator directive.
