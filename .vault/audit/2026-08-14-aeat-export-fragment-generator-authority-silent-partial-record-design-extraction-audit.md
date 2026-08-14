---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:d0c6cb8e6483f278812dc2c20b3e7d788e79bd793fd3952508f8bc30e362d61a'
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
partial result. That number is unknown, because the mechanism that would report
it is the one being described.
