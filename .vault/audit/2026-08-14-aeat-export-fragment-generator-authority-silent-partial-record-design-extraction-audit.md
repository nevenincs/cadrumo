---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:f8c2f2e37bf49859bd836d3d55457645b9cb935ef239ebb4ecd629d53ecd3908'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `silent partial record design extraction`

## Scope

One finding in the official record-design extractor: a worksheet that fails
header detection is dropped and the caller receives a partial result reported as
a complete one. Raised while diagnosing why Modelo 115 produced no record sheets
from a healthy binary; the header defect that exposed it is fixed separately and
is not this finding.

## Findings

### silent-partial-extraction | high | A skipped worksheet leaves no trace, so a partial design reads as a whole one

Both workbook extractors iterate the sheets of an official design, call the
per-sheet extractor, and catch the "has no record-design header" refusal. The
sheet is appended to a local skip list and iteration continues. That list is
used for ONE purpose: composing the message when EVERY sheet fails. When even a
single sheet parses, the skipped ones are discarded and the caller is handed the
survivors with no indication that anything was lost.

Nothing downstream can detect it. The return type is a plain tuple of sheets and
carries no notion of completeness, so a consumer cannot distinguish a design
whose every sheet parsed from one where half were dropped. The intermediate
projection, the semantic map, the census and the anchor count are all computed
over the survivors and agree with each other perfectly.

The observed instance: Modelo 115's design carries two sheets, one of 31 rows
and one of 1422. The larger sheet -- the entire record body -- was skipped, the
smaller was returned, and its 13 fields were then correctly classified as an
auxiliary envelope and moved out of the record set. The design therefore
presented as carrying NO record sheets at all, from a file that is present,
hash-pinned, byte-identical to its declared size, and complete. The reported
error named the wrong thing: it said the intermediate had zero sheets, when the
truth was that one sheet could not be read and the other was not a body sheet.

Severity rests on the failure being INVISIBLE rather than on the one modelo.
An extractor that silently returns a subset means every count derived from it --
anchors, records, coverage, worklist size -- is an upper bound on what was read
rather than a measure of what the design contains, and no gate downstream can
tell the difference. This is the same shape as the other defects this campaign
has found: absence expressed as silence, indistinguishable from correctness.

## Recommendations

Make partiality unrepresentable or explicit. Either the extractor refuses when
any sheet of a design fails header detection, or its result carries the skipped
sheets so a caller can decide. A log line is not sufficient: the consumers here
are gates, and a gate cannot read a log.

Fixing this is deliberately NOT bundled with the header-spelling fix that
exposed it. Widening an accepted-spelling set is provably additive across the
whole corpus; changing how extraction reports failure is a behaviour change for
every consumer, and refusing designs that partially parse today would alter what
the tree can read. The two carry different risk and want separate evidence.

Worth measuring before choosing: how many bundled designs currently return a
partial result. That measurement has since been taken and is recorded below.

## Measured extent

Taken across the whole bundled corpus without changing extraction: the "present"
side is the container's own sheet listing, the "returned" side is production
extraction unmodified.

The corpus holds 212 official designs; 175 are read, 37 refuse loudly. Of the 94
readable workbooks, seven drop at least one sheet and five of those drops are
record-body-shaped. Of the 81 readable PDFs, none shows evidence of a dropped
record -- a PDF has no container sheet listing, so the signal there is the
document's own announced record headings against the returned sheets, and every
apparent gap resolved by hand to a name-normalisation artefact rather than a
loss.

Modelo 115 was the visible case, not the only one. Modelo 714 carries the exact
same shape -- one workbook spelling its length column `Lon` on eleven body
sheets and `Long.` on the twelfth -- across four bundled editions. Modelo 151 is
a larger shape: nine of its twelve sheets title the description column `Datos
Adicionales de la Declaración` and insert a `Com.` column, so the required
description header is absent entirely rather than merely abbreviated. Modelo 151
therefore reads 108 anchors from a design carrying roughly 727. Four Modelo 100
editions fail every sheet and so refuse loudly, which is the same defect with
the silent path closed only by the accident of nothing surviving.

Two consequences for the campaign's numbers. First, no design declared by a
worklist revision and present on disk loses a sheet, so the worklist size
distribution derived from read anchor counts is unaffected and needs no
restatement. Second, the affected designs sit in the not-yet-enrolled tranche --
the twenty-nine whose design binary is bundled but never declared as a registry
source, as distinct from the seventeen genuinely awaiting acquisition. A read
count taken at face value the first time one of those is enrolled would be
wrong, and Modelo 151's would be wrong by a factor of seven: it reads 108
anchors from a design carrying roughly 727. Anyone sizing that tranche from
these counts should read this paragraph first.

That distribution of shapes is itself the argument against the incremental fix.
Recognising `Long.` alongside `Lon` is one more enrolment; `Datos Adicionales de
la Declaración` is reachable by no spelling normalisation at all. Only making
partiality explicit in the result covers the spelling nobody has seen yet.

## The vocabulary behind the skips, and why the two fixes are ordered

A follow-up pass reproduced the header probe against every sheet of every
workbook design, mirroring the real search rather than stopping at the first
candidate row. Of 2803 sheets, 2458 find a header and 345 do not, and the
failures are far less varied than the two observed instances suggest: 330 of the
345 are one spelling, a length column titled `Long.` where the probe accepts only
`Lon`. Four sheets carry no length column at all, which no token rule reaches.
Nine are Modelo 151's differently-titled description column. Two are a Modelo 232
lookup tab that is correctly skipped.

Only fifteen of those 345 are silent drops today. The other 330 sit inside
Modelo 100 designs for ejercicios 2015 through 2019 that already refuse for
independent reasons, so their sheets are lost loudly rather than quietly.

## Correction: the predicted Modelo 100 hazard does not occur

This section argued that widening the length-column spelling first would take
those Modelo 100 designs from refusing outright to returning a partial result
with no signal, trading a loud failure for a silent one. **Measured, it does
not.** The prediction was stated before it was run and the run contradicts it.

Patched from outside the repository across every bundled workbook design: eight
Modelo 100 files (ejercicios 2015 to 2018, in both container formats) move from
one hard refusal to a DIFFERENT hard refusal -- their newly readable sheets fail
the variable-envelope geometry check rather than returning quietly. Two more
(ejercicio 2019) go from refusing outright to reading 41 sheets complete. None
of them becomes a silent partial in either order.

The ordering conclusion survives, on the other case rather than that one. Modelo
714's four editions were a genuine silent partial before the spelling widened --
eleven sheets returned, a twelfth dropped, and no way for a caller to know. Under
the old return type that recovery would have been invisible in both directions:
nobody could have shown the sheet had been missing, nor that widening the rule
recovered it. Partiality-first is what makes the spelling fix PROVABLE, which is
a weaker claim than the one made above and the one the evidence supports.

The general point stands unchanged and is the durable half: a spelling nobody
has seen yet is silent under any enrolment, and only a result that reports its
own completeness makes the next one loud.
