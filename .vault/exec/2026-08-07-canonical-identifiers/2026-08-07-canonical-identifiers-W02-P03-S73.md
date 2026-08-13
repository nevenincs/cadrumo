---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:71d2b3b25faa4174b6269a15c26a2ccd3f44873605d3af56ccc538a7d95b6d1f'
step_id: 'S73'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Consolidate every CSV normalisation onto the one canonical authority, closing the concept-shaped gap S20's two-file row could not reach. S20 unified the verify adapter and the calendar-evidence consumer and closed green, but the concept spans SEVEN further sites re-implementing normalise_aeat_csv inline, found independently by two agents during this Phase. This is the same defect shape W01 had to correct twice (S66, S68), a row-shaped close over a concept-shaped gap. TWO strengths, not one. The wrong-form sites are _cross_period_clean_state.py lines 997 and 1000, which compare with .casefold() -- the exact form core/_aeat_csv.py's own docstring rules out, because casefold produces lowercase which fails AEAT_CSV_PATTERN outright and transliterates, fatal for a value that must round-trip to cotejo byte-for-byte. That docstring already describes those sites in the PAST TENSE as reached-for-and-corrected, and they are still there, so the prose is false where the next reader meets it. The right-form-wrong-home sites are .strip().upper() at _justificante.py lines 577, 718 and 891 and _filed_observation_persistence.py lines 519 and 594, correct today but a second authority that drifts the moment the canonical form changes. Route every site through the canonical function, delete each inline copy, and correct the canonical docstring's past-tense claim in the same commit. Line numbers are as measured at HEAD and MUST be re-verified before editing, since two of these files carry live peer WIP. NOTE that line 1008 of _cross_period_clean_state.py casefolds an expediente_id, a different namespace, so assess it on its own bound and do not sweep it in by proximity

## Scope

- `src/cadrumo/application/calculations/_cross_period_clean_state.py`
- `src/cadrumo/application/live/_justificante.py`
- `src/cadrumo/application/live/_filed_observation_persistence.py`
- `src/cadrumo/core/_aeat_csv.py`

## Description

- Route every production CSV normalisation and CSV comparison through
  `normalise_aeat_csv`, deleting each inline copy rather than leaving one beside
  a new call.
- Correct the canonical docstring's stale claim about the sites it describes.
- Add a behavioural regression at each consolidated consumer plus a singularity
  gate that keeps the docstring's claim true rather than merely written.

## Outcome

The row named seven sites in four files. Re-measured at HEAD before editing, the
concept spanned ten sites in six files, and the two extra families are named
below rather than left for a third correction of the same shape. All four files
the row named were clean of peer changes when the edits landed, so the
apply-cached drive was not needed.

The wrong-form sites, casefold, in `_cross_period_clean_state.py`. Line 997
compared a register metadata CSV against the receipt CSV with `.casefold()` on
both sides; line 1000 built a casefolded set membership test the same way. Both
are gone. The module now normalises once, at the two cleaners, and the
comparisons above them are plain equality: `_clean_metadata_csv` at line 1029 is
new and returns the comparison form or nothing, `_clean_metadata_csvs` at line
1033 normalises each split item, and line 997 holds the single
`receipt_csv = normalise_aeat_csv(justificante.csv)` both checks read. The
generic `_clean_metadata_value` was deliberately NOT changed, because it also
serves the expediente id, which is a different namespace.

The right-form-wrong-home sites, `.strip().upper()`. In `_justificante.py`,
lines 577 and 718 were not merely two copies of the transform, they were the
same ten-line comparison and refusal duplicated byte for byte. Routing each
through the canonical function separately would have left the duplication
standing, so the pair collapsed into `_require_receipt_csv_matches_capture` at
line 551, called from line 600 and line 733. Line 891, the capture-evidence
match, is now line 898 and calls the canonical function on both sides. In
`_filed_observation_persistence.py`, line 519 is now line 518 and line 594 is
now line 592, both on the canonical function.

Two families the row did not name, found by re-measuring rather than by
following the row. First, the writing side: `_filed_observation_persistence.py`
line 717, now line 721, deduplicated the CSV references it persists on a trim
alone, so two spellings of one identifier survived as two entries into the very
metadata the cross-period gate reads back and compares. That is the same
second-key defect as the comparison sites, on the side that creates the value.
Second, the two inbound extractors that MINT the canonical form from a regex
capture: `justificante/_extract.py` line 439 and
`borrador/_extractors/modelo_100_summary_v2025.py` line 105 both applied a bare
`.upper()`. Both now call the canonical function. Neither is proximity sweeping:
both are the AEAT CSV namespace producing the AEAT CSV normal form.

The docstring correction is on `normalise_aeat_csv` itself. Its claim that two
call sites had reached for casefold read as settled history while the sites were
still in the tree, and the count was never right either. The rewritten paragraph
names the surfaces the casefold form actually came from and stops asserting a
tally. A prose claim was what failed here, so the singularity claim is now
enforced by a gate the docstring points at rather than restated in prose.

Every production CSV normalisation now calls the one authority. The measured
production consumer set is `_cross_period_clean_state.py`, `_justificante.py`,
`_filed_observation_persistence.py`, `_calendar_evidence.py`, the verify adapter,
the two inbound extractors, and the `AeatCsv` alias's own `BeforeValidator`. A
sweep for a case transform applied to a CSV-bearing expression outside the
canonical module returns nothing.

## Notes

The expediente id ruling, on its own merits rather than by proximity. Line 1008
compares a register `aeat_expediente_id` against the receipt's
`presentation_id`, and the two are different namespaces by the core aliases' own
account: `AeatExpedienteId` carries a 12-32 bound and a
year-then-alphanumerics grammar, while `AeatPresentationId` carries a bare
64-character ceiling, no pattern, and admits the empty string. The
`AeatPresentationId` docstring states outright that a presentation id and an
expediente id are not derivable from one another, one appearing only on the
receipt and the other only in the register listing. So the casefold there is not
the CSV defect and was left untouched.

It is, separately, worth a successor row, and the evidence is stronger than a
naming argument. A sibling live-path test asserts that a real captured receipt's
presentation id and a real register expediente id DIVERGE, and its docstring
records that comparing those two values was itself a defect that used to drop
Modelo 303 receipts. Meanwhile the register metadata writer persists an
expediente id and a CSV reference together on every filed observation, and the
equality arm of the cross-period check runs whenever both a metadata expediente
id and a receipt presentation id are present, regardless of whether a CSV
reference is also there. The existing coverage only exercises the
expediente-only shape, so the arm that would fire on the both-present shape is
untested. Two surfaces in this tree therefore disagree about whether those two
identifiers are comparable at all. That is a clean-state gate correctness
question, not a normalisation question, and it deserves its own decision.

Verification. The consolidation carries a behavioural regression at each
consumer family and a singularity gate, and the gate found a real hole in its
own first cut: the detector anchored its CSV match to the ends of the whole
receiver expression, so a trailing `.strip()` hid the csv token and
`justificante.csv.strip().upper()` -- one of the exact forms removed here --
scanned clean. The bite proof caught it before the commit, the match moved to
the ends of each identifier inside the receiver, and that specific shape is now
one of the detector's discrimination cases so the hole cannot reopen quietly.

Both bite proofs ran from a throwaway pytest plugin outside the repository, so
no tracked file was edited to produce a red. Neutralising the canonical function
at the three consumer modules reds eight assertions and only the case-variant
ones: the canonical-spelling parametrisations and every discriminating
must-still-refuse assertion stay green, which is what shows the regressions are
measuring normalisation rather than passing by construction. Planting one
in-memory second copy into the gate's production walk reds the scan with the
planted path named.

The case variance those regressions assert on is real rather than hypothetical,
and not uniform, which is worth stating because it decides where a regression
can even be written. `Justificante.csv` and `JustificanteCaptureSnapshot.csv`
both carry the canonical alias and normalise at their model boundary, so they
can never present a variant spelling. The surfaces that can are the ones that
only trim: the external evidence reference, the register metadata string map,
and the CSV recovered from a cotejo URL. Those are the surfaces exercised.
