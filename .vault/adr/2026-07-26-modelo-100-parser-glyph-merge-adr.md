---
tags:
  - '#adr'
  - '#modelo-100-parser-glyph-merge'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
  - '[[2026-07-26-declaracion-real-render-verification-campaign-close-honesty-review-audit]]'
---

# `modelo-100-parser-glyph-merge` adr: `how to stop the parser fabricating amounts from merged box-number glyphs` | (**status:** `proposed`)

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
fix.

**(D) Leave it, with the exclusion pinned.** The current state. Modelo 100 is
excluded from the real-render gate with the exclusion evidenced rather than assumed,
so nothing reports it as verified. Acceptable indefinitely, and the correct default
until (C) is decided — but it leaves a modelo whose every extracted value is wrong.

## Decisions

**None. This record scopes the problem and names what must be measured before any
of it can be decided.** It is `proposed` deliberately: two of the three changes reach
subsystems nobody has measured, and deciding them from the declaración evidence alone
would repeat the generalisation this line of work exists to correct.

The three coupled decisions, stated so they are not mistaken for one:

**Q1 — May the shared inbound-PDF primitive change its word segmentation?** The fix
belongs in `adapters/inbound/pdf/_pdfplumber.py`, not in the declaración parser.
Measured, that primitive has **three production consumers**: the declaración adapter,
the borrador adapter, and the ledger evidence text layer. Only the first has been
measured. The other two must be, before this can be answered.

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
number beside an amount, which would change the shape of the answer.

## Codification candidates

None promoted. Project rule codification is retired by operator directive.
