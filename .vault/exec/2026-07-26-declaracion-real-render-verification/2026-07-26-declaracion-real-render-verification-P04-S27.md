---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
step_id: 'S27'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Implement the word-level Modelo 100 fix inside the parser, after re-running the committed real-render gate with the size attribute to clear the bbox word-ordering risk

## Scope

- `src/cadrumo/adapters/inbound/declaracion`

## Description

The precondition was run first and it cleared. Requesting the font size on word
extraction changes the returned word lists, and the same function backs
`bbox_anchored`, which carries the real-render gate for Modelos 390, 111 and 190.
The committed gate passes unchanged with the attribute requested, 45 cases, and
so does the whole declaración suite at 241. A probe had narrowed the risk before
this; running the gate is what settled it.

The fix then has three parts, and the middle one was not anticipated.

Word extraction requests `size`, which is what separates the runs: pdfplumber
will not join words of differing size, so the 9pt amount and the 6pt box number
stop arriving as one token.

`named_label` amount capture reads the line's words rather than its text. The
value is the line's last word, as on the text path; when that word is the
target's own printed box number and a well-formed printed amount precedes it, the
amount is taken instead. When nothing well-formed precedes it the box number is
returned unchanged, so the blank-box guard still sees it and still reports the
target absent.

Word data is now loaded for `named_label` amount targets too, not only for
`bbox_anchored` ones. Without this the new path never runs on Modelo 100, whose
profile declares no bbox targets at all -- the first implementation was measured
as a no-op for exactly that reason. A profile with neither kind of target still
never pays for the pass.

## Outcome

Modelo 100 recovers **21 of 21 targets on all three specimens**, with the only
extracted values being `1000.00` and `1001000.00` -- the two forms the documents
print -- and zero fabrications. It is enrolled in the real-render gate and the
boundary test that pinned its exclusion is deleted, which is what that test's own
failure message instructed.

Every other modelo is unchanged. Measured through `_extract_profile_values` over
every profile with a fixture: 111, 115, 123, 130, 131, 180, 184, 190, 193, 202,
232, 303, 347, 349, 369, 390, 720 and 840 all return exactly what they returned
before, values included.

Falsifiability was proven rather than assumed: removing the size attribute fails
exactly the three Modelo 100 manifest-constant cases and leaves the other 51
green.

Verification: declaración 250 passed; calculations, filing, modelo and ledger
2457 passed; `ruff` and `ty` clean.

The two stragglers from the earlier prototype are resolved, and the coordinator
was right to want them settled rather than assumed. They were never a regex
artefact. `0595` and `0670` matched **twice** and were reported ambiguous,
because Modelo 100 prints a section heading in capitals -- the cuota-resultante
and resultado-declaracion headings -- that a case-insensitive label pattern
matches as readily as the populated row. The text path never saw this: its regex
requires a value token after the label, which a heading does not have. The word
path now requires the same, which is fidelity to the existing contract rather
than a new heuristic, and it is why the result is 21 of 21 rather than the
prototype's 19.

## Notes

The floor is not settled by this and must not be read as settled. Modelo 100
lands at 21 of 21 against its inherited floor of 1, so the profile passes -- but
all three specimens come from one filer and every box on them is populated. They
show what a complete Modelo 100 yields, not what the form yields across filings,
and under D2 a floor may not be set from one filer's specimens. A filer
legitimately leaving one optional box blank would be refused. This is recorded as
an evidence gap in its own Step rather than silently endorsed by a green suite,
and the module docstring says so at the point of enrolment.

One consequence of enrolling Modelo 100 is worth flagging for whoever next reads
the anti-vacuity guard. These are the first bundled specimens that score full
coverage, so the guard now rests entirely on Modelo 390 and Modelo 111 falling
short. That is still true and the guard still passes, but the margin is thinner
than before this Step.

A proposal that would have cost nothing was refuted before implementation and is
recorded so it is not retried: splitting the merged token at capture. Casilla
`0545` extracts as one interleaved token rather than the amount followed by the
box number -- the box number's bounding box sits inside the amount's span, so the
digits interleave by x-position and the correct amount is not a substring at any
position. No string rule recovers it.

The semantic code index was truncated throughout, roughly 1027 chunks against
roughly 4546 files, while reporting itself healthy. No semantic result was relied
on.
