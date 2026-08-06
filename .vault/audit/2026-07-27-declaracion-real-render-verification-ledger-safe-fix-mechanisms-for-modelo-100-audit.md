---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:36c1bef7664c5a182dddf4881efb4a903379cff9535fe578c3f5fc375bfe4c31'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - "[[2026-07-26-modelo-100-parser-glyph-merge-adr]]"
---

# `declaracion-real-render-verification` audit: `which mechanism spares the ledger path while fixing Modelo 100`

## Scope

Research for `P04.S23`: is there a mechanism that recovers Modelo 100's real
amounts while leaving the ledger evidence text layer byte-identical.
Evaluates the three candidates the dispatch brief named, against the
current code as it stands. Report-only throughout: no edit to
`_parser.py`, the shared primitive, or any declaración test. Every
empirical claim below was produced by a standalone script calling
`pdfplumber` and the production registry authority directly against
bundled fixtures, never by modifying a committed file. Method is stated
beside every claim; measured versus inferred is stated per conclusion.

## Findings

### declaracion-already-owns-a-second-word-level-extraction-path-entirely-separate-from-the-shared-primitive | critical | this is the finding that reframes all three candidates

Read `_parser.py` directly rather than assuming the shared-primitive framing
of Q1 covers everything declaración reads. It does not. Declaración has TWO
independent extraction axes, not one:

- Text-string extraction (`extract_pages_text`, `extract_pages_text_from_bytes`),
  which the declaración `_parsers/_pdfplumber_backend.py` module gets by calling
  the SHARED `adapters/inbound/pdf/_pdfplumber.py` functions -- the same
  functions the ledger evidence layer (`extract_pages_text_from_bytes`) and the
  borrador adapter (`extract_pages_text_from_path`) also call. This is the axis
  Q1 was scoped against, correctly.
- Word-level extraction (`_extract_pages_words`, `_extract_pages_words_from_bytes`,
  `_parser.py:799` and `:820`), used today only for `bbox_anchored` targets. Both
  functions call `pdfplumber.open(...)` **directly, inside `_parser.py` itself** --
  not through the shared primitive at all. Grepped every production caller of
  the shared module's exported functions and confirmed neither `_extract_pages_words`
  function is one of them, and neither is called from `adapters/inbound/pdf/`,
  the ledger evidence layer, or the borrador adapter.

This means a size-aware change to `_extract_pages_words` -- adding
`extra_attrs=["size"]`, exactly the parameter the ADR own prototype already
used -- touches zero lines the ledger evidence layer or the borrador adapter
executes, not because the change is scoped carefully, but because those
consumers structurally cannot reach this function: it lives in a different
module and neither imports it. This is stronger than "the wrapper is thick
enough to hold new logic" (candidate 1's framing) -- the isolated pathway
already exists and already runs today, just without the size attribute.

### split-at-capture-as-literally-stated-does-not-work-the-merge-is-not-a-clean-concatenation | high | measured character-by-character, not assumed from the ADR wording

Attacked candidate 2's premise directly: "changes no text at all" implies
the trailing-box-number rule operates on the merged STRING already produced
by `extract_text()`, stripping a recognisable trailing substring. Extracted
casilla `0545`'s actual merged text from the bundled real specimen with
`page.extract_text()`: `'1.001.0000,50405'`. The correct amount is
`1.001.000,00` (12 characters) and the box number is `0545` (4 characters);
naive concatenation would give `1.001.000,000545`. The actual merged string
is neither: comparing character-by-character, the digits from the two runs
are interleaved by x-position rather than appended, because the box
number's bounding box (`x0=552.66-566.00`) sits inside the amount's own span
(`x0=513.97-566.51`), not after it.

**A regex or string operation on the merged text cannot recover the correct
amount, because the correct amount is not a substring of the merged text at
any position.** The "last token is the target's own box number, take the
amount before it" rule the ADR own prototype describes only becomes
applicable once the two runs are already correctly separated into distinct
tokens -- which requires size-aware WORD extraction, not smarter string
parsing of the existing merged text. Confirmed this directly: with
`extract_words(extra_attrs=["size"])`, casilla `0545`'s region yields
`'1.001.000,00'` at size 9.0 and `'0545'` at size 6.0 as two clean, separate
words on the correct page.

**Candidate 2, read literally ("leave extraction exactly as it is"), is not
available. What is available is its word-level cousin: give the capture
step access to the same size-tagged word data `bbox_anchored` already
consumes, and apply the trailing-box-number rule there.** That is a real
mechanism, and finding 1 establishes it can be built entirely inside
`_parser.py` -- but it is a genuine new data-flow (`named_label` capture
gaining access to word-level data it does not read today), not merely
smarter parsing of the same text.

### the-word-level-fix-has-its-own-previously-unmeasured-consumer-a-second-set-of-currently-passing-targets | high | narrower risk than ledger, but real, and not yet zero

Adding `extra_attrs=["size"]` to `_extract_pages_words` does not risk the
ledger evidence layer or borrador (finding 1), but it is not free: it is
the SAME word-extraction function the currently-passing real-render gate
already relies on for Modelo 390, 111 and 190's `bbox_anchored` targets, and
this pass measured that the returned word lists genuinely differ with the
attribute added -- both the general page word lists (header and footer text
reorganise on Modelo 390) and, on Modelo 111, the raw order of duplicate
same-text matches.

Narrowed the check to what the gate actually depends on: the specific
`box_number_pattern` matches for every currently-declared `bbox_anchored`
target across these three modelos. Modelo 390's only populated target
(box 49) is unaffected -- identical single hit, same coordinates, both ways.
Modelo 111's 21 `bbox_anchored` targets show hits with identical text and
identical coordinate pairs in both cases; where a target pattern has two
occurrences on the page (columns), the two hits appear in a different
order in the returned list, but the same two coordinate pairs are present
either way. Modelo 190 has no `bbox_anchored` targets, so it is not at risk
on this axis regardless.

**Measured: no target-match content changes on the three currently-gated
modelos, only incidental list-order and header/footer differences outside
what the gate checks.** This is real evidence the risk is narrow, but it is
not the same as re-running the actual committed real-render gate with the
change applied, which this report-only pass cannot do without touching the
other agent's files. That re-run is what should happen before landing,
not skipped on the strength of this narrower probe.

### candidate-1-and-candidate-2-converge-into-one-mechanism-once-finding-1-is-applied | high | the two named candidates are not actually independent options

Read against finding 1, "scope it to the declaración entry point" and
"split at capture" are not two separate mechanisms to choose between --
they are the same mechanism once the word-level pathway is used instead of
the text-string one. The declaración entry point is where the split-at-
capture logic must live, because it needs the size-tagged word data that
pathway already carries and the shared text primitive does not. Evaluating
them as alternatives risks picking one and rediscovering the other is a
precondition for it.

The combined mechanism, stated precisely: add `extra_attrs=["size"]` to
`_extract_pages_words`/`_extract_pages_words_from_bytes` (contained to
`_parser.py`, per finding 1); give `named_label` capture, for
`value_kind = "amount"` targets specifically, access to this same word data
alongside the text it already reads; apply the trailing-box-number rule
(last word on the matched line equals the target's own `form_number`, take
the preceding well-formed amount word) at that point. Text assembly itself
-- what `extract_pages_text` returns -- never changes.

### candidate-3-reconstruct-lines-from-words-is-strictly-dominated-by-the-combined-mechanism | medium | shares the same isolation, costs more, solves nothing extra

Candidate 3 could also be implemented locally in `_parser.py` rather than in
the shared primitive, so it shares finding 1's isolation from the ledger
evidence layer. But it does not need to be: it would mean discarding
pdfplumber's own `extract_text()` line assembly (robust, already correct
for every declaración profile except Modelo 100's merge) and rebuilding line
grouping from size-tagged words by hand, which is exactly the mechanism the
ADR own prototype already tried and which broke the ledger evidence text's
line grouping when applied at the shared-primitive level. Reimplementing it
locally in declaración does not remove that risk, it only relocates where
the risk is re-measured -- and it would need to be re-verified against all
158 `named_label` targets across every declaración profile, not the narrow
21-casilla surface the combined mechanism above touches. There is no
capability the combined mechanism (finding 4) lacks that this candidate
would supply; it is the same isolation with a harder implementation and a
wider blast radius to re-verify. Not recommended.

### the-n-equals-1-ledger-corpus-caveat-is-reaffirmed-not-re-inflated | medium | checked directly rather than repeating the ADR own corrected figure

The ADR already corrected an earlier overstatement (the N26 statements
being counted as real, external evidence when they are this project's own
generated fixtures) and recorded n=1 as the true evidential weight -- the
one genuinely external text-native document is the bundled ZUGFeRD invoice.
Re-checked directly rather than repeating that figure: grepped the ledger
evidence fixture directory sidecars and the N26 generator script itself
(`fixtures/financial/n26/_generate.py`, present alongside the fixtures it
produces) and confirmed the fixtures declare `Producer = reportlab`,
`Creator = aeat fixture generator` as the ADR states. The scanned specimen
has no usable text layer either way. n=1 stands, and this pass did not cite
it as anything larger.

## Recommendations

The capture-time split proves out, with a correction to how it is framed:
say so plainly, but say it as "the word-level version of split-at-capture,
built where declaración already has an isolated word-extraction pathway"
rather than as "leave extraction exactly as it is" -- the literal premise
does not survive contact with the merged text, and the mechanism that does
work needs the word-level data candidate 1 and candidate 2 turn out to
share.

Recommend the combined mechanism from finding 4 as the one to prototype
next: `extra_attrs=["size"]` on `_extract_pages_words`, `named_label`
capture extended to consult it for `value_kind = "amount"` targets, the
trailing-box-number rule applied there. It collapses candidates 1 and 2
into one contained change that structurally cannot touch the ledger
evidence layer or the borrador adapter, per finding 1.

Before landing it, measure two things this report-only pass could not:
re-run the actual committed real-render gate for Modelo 390, 111 and 190
with the size attribute added, rather than trusting this pass's narrower
target-match probe (finding 3); and re-answer Q2 in its now-narrower
word-level form -- does giving `named_label` access to size-tagged word
data change any of the other 158 targets' captured values across the
estate, not only whether the 21 Modelo 100 targets recover correctly.

Do not pursue candidate 3 (finding 5): it shares the same isolation as the
combined mechanism, costs more to implement, and reintroduces a risk the
combined mechanism avoids by not needing to rebuild line assembly at all.

The borrador lead remains exactly where the ADR left it -- undecidable
without a real borrador render, unrelated to which of these three
mechanisms is chosen, since the combined mechanism is entirely local to the
declaración parser and never executes in the borrador adapter's own code
path.
