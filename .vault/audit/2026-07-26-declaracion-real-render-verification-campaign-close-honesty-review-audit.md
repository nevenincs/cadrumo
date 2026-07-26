---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - "[[2026-07-25-declaracion-profile-printed-box-scope-adr]]"
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
---

# `declaracion-real-render-verification` audit: `campaign-close honesty review, read as a fresh inheritor`

## Scope

Campaign-close honesty review, read in the posture of a fresh inheritor: I did
not run this campaign, and my job here is to list what is missing, vague, or
assumed-but-unverified, not to defend what is there. Covers the plan, both
ADRs, all four audits under this feature (including the three this same
reviewer authored earlier this session), every exec record, and the commit
history through the moment of writing. Report-only: no production code,
registry data, or test file is modified by this pass. The semantic code index
remained truncated throughout and was not used as evidence.

One honesty note about the reviewer's own position: three of the four prior
audits under this feature, and the correction to a fourth's circular
citations, were authored by this same session. A fresh inheritor would not
extend them automatic trust for that reason, and this review does not either
-- every claim below was re-checked against the current tree, not assumed
correct because an earlier pass by the same hand produced it.

## Findings

### seventeen-inert-blank-box-guards-are-a-known-live-defect-with-no-tracked-follow-up | critical | named precisely in one exec record own Notes section and nowhere else

`P01-S04`'s Notes name the defect exactly: seventeen `named_label` amount
targets across nine other modelos carry the identical hazard the M390 and
M190 fixes closed on their own six casillas -- a blank printed box whose line
ends in its own box number, read by a guard that was comparing against the
wrong field. Ten are fichero-BOE positional-range casillas on Modelos 180 and
193 (three each) and 349 (four); seven are `decl.ejercicio`-shaped identifier
targets. The record states that failing the guard closed on a bare integer
was measured as an alternative and rejected, so the investigation is real,
not a guess.

Re-confirmed still open at the moment of writing: commit `c85bf0fd92`, which
landed after this reviewer's own prior pass, revisited exactly this Notes
section and confirmed the seventeen are still "awaiting the same data" -- the
fix that closed the guard for six casillas has not been extended to the other
seventeen.

There is no Step, no plan row, no GitHub issue, and no Recommendations-section
entry anywhere under this feature naming these seventeen as tracked work. The
only place this defect is recorded is inside one Notes paragraph of a closed
Step's exec record. A fresh inheritor who read the plan and both ADRs and
stopped there would not learn this defect exists at all.

### the-adrs-own-implementation-section-would-mislead-a-reader-who-stopped-there | critical | this is the sharpest claims-versus-evidence gap in the campaign

The governing ADR Implementation section states plainly: "The six casillas
whose printed number is not recorded have `form_number` populated from the
bundled renders." Read on its own, with no cross-reference to any exec
record, this sentence describes the printed-box-number hazard as closed. It
is true as far as it goes -- six casillas across M390 and M190 do have
`form_number` now -- but the ADR names no count of what remains, and D1's own
prose gives no hint that a further seventeen targets across nine other
modelos carry the identical defect, confirmed still open as of finding above.

A reader who trusted the ADR alone would believe the printed-box-number class
of defect is handled. The evidence supports only "handled for six of
twenty-three now-known instances." This is the single largest gap between
what the campaign's headline decision record claims and what its own exec
records establish, and it exists because the ADR was written before the
seventeen were swept into `git log`, and nothing has updated it since.

### s03-has-no-exec-record-and-the-specific-handover-facts-exist-nowhere-in-the-vault-or-git | critical | the one deliberately-open Step has zero persisted handover

`P01.S03` (verify M100 across its five revisions) is the plan own only
unchecked row. No exec record exists for it at all -- not a partial one, not
a placeholder, nothing under this feature's exec directory names `S03`. The
general shape of the M100 defect (word assembly merging a six-point box
number into a nine-point amount, all 21 targets on all three real renders
fabricated, coverage 1.0 against a floor of 1) is recorded in `P01-S05`'s
Notes, because that is where the exclusion decision was made, not because S03
was documented there.

Searched the full vault and git history for the specific handover facts named
in the dispatch brief -- a deltas table, three failing bbox offsets, a
prototype result, a pdfium-canary fact -- and found none of them anywhere.
Neither the phrase "pdfium" combined with "canary", nor any bbox-offset
delta table, nor a prototype result appears in any committed document or
commit message under this feature or in `adapters/inbound/declaracion`.

If this session ends now, a stranger picking up S03 has: the fact that word
assembly is the culprit, the fact that all 21 targets on all three specimens
are affected, and nothing else. The three specific bbox offsets, whatever
was prototyped, and whatever the pdfium-canary fact is are not recoverable
from anything this review could find. That is not a thin handover; it is an
absent one, dressed as "deliberately open" when the more precise description
is "deliberately open with its working state undocumented."

### the-plan-own-step-row-still-states-the-superseded-count | high | the checked-off Step text was never corrected after two rounds of number correction

`P02.S06` through `P02.S09` are all checked `[x]`, and `P02.S09`'s own Step
row text reads "Register route R11 for the 19 specimen-less profiles" --
the count both this reviewer's audit and the team lead have since agreed is
22, corrected twice over (19 to 22, and "eight of nine" to "nine of nine" on
a related count). The exec record for `S09` states 22 correctly. The plan
row a reader encounters first, and the one the checkbox sits beside, still
says 19.

This is a small thing on its own, but it is exactly the shape of drift this
campaign's own discipline exists to catch: a corrected number that reads
right in the newest document and wrong in the oldest one a reader is likely
to open first.

### the-plan-own-narrative-sections-are-empty | medium | no stated completion criteria anywhere in the plan itself

The plan Description, Parallelization, and Verification sections are all
blank -- headers only, no prose beneath any of them. There is no sentence
anywhere in the plan stating what "done" means for this feature, which Steps
could run in parallel, or what verification standard closes it. Everything
this review used to judge completeness came from the ADRs and the exec
records, not from the plan document that is supposed to state it.

### d1-is-code-enforced-d2-and-d3-are-documentary-conventions-only | high | per-decision accounting, as requested

Read each of D1 through D5 against whether a test would fail if it were
violated:

- **D1** (form_number, not number) is enforced in production: the blank-box
  guard reads `form_number` first, proven by direct calls to `_classify_target`
  in the exec records with before/after behaviour shown. Falsifiable and
  falsified-and-restored per the adversarial pass.
- **D2** (a coverage floor is set only from evidence across specimens) is a
  documentary convention. Nothing in the test suite would fail if a future
  edit raised Modelo 111's floor above 1/29 without a second corroborating
  specimen, or lowered a floor on the strength of the synthetic corpus. The
  discipline lives in the ADR prose and in the audits' Recommendations, not
  in a gate.
- **D3** (an untestable profile is an evidence gap, never a pass) is also
  documentary. Nothing would fail if a future document reported one of the
  22 specimen-less profiles as "verified". The register in the static-route
  audit is the only thing holding this line, and it holds it by being read,
  not by being enforced.
- **D4** (selection by `surface`, never `artefact_kind`) is enforced in
  production (`_select_extraction_profile` keys on `surface`), but see the
  next finding: the gate that is supposed to prove this does not exercise
  that function.
- **D5** (registry readiness is necessary but not sufficient; a real render
  is required) is not a claim a test enforces or could enforce -- it is a
  policy statement about what evidence enrolment requires, and its only
  teeth are that no code path currently lets any of the nine unenrolled
  modelos reconcile, which D5 itself did not create.

**Two of five decisions (D2, D3) rest entirely on documents being read, not
on anything failing if they are ignored.**

### the-real-render-gate-reimplements-profile-selection-instead-of-calling-the-production-selector | high | d4 is proven true today but not wired to stay true

`test_real_render_extraction_coverage.py`'s `_declaracion_profile` helper
does not import or call `_select_extraction_profile`, the actual production
selector D4 describes. It hand-copies the same filter
(`surface == "declaracion_pdf" and "declaration_pdf" in
accepted_artefact_kinds`) inline, with a docstring claiming parity
("Select the profile exactly as `_select_extraction_profile` does") rather
than an import proving it.

The two currently agree, checked directly: production `_select_extraction_profile`
(`_parser.py:463`) and the test helper (`test_real_render_extraction_coverage.py:239`)
use byte-identical filter conditions today. But nothing ties them together.
If a future change to the real selector added a new exclusion, or if a new
gate elsewhere in the codebase were authored against `artefact_kind` the way
the original defect was, this test would not notice either regression: it
would keep passing against its own frozen copy of the old logic. This is
exactly the class of gap the dispatch brief asked whether anything prevents
-- and for a *second* gate reaching the same conclusion by hand-copying
rather than importing, the answer is no.

### the-m202-enrolment-question-and-the-dormant-verify-declaracion-are-described-but-not-decided | medium | two items named as open, neither with a tracked next action beyond a sentence

The R8-arbitration audit names both precisely and leaves both open by design,
which is within that audit's report-only grant -- but neither has anything
beyond a Recommendations-section sentence holding it open. The M202
enrolment question ("should the nine not-yet-enrolled modelos be added...")
has no plan Step, no ADR question queued, no issue. The dormant
`application.verification.verify_declaracion` -- a complete, tested,
modelo-agnostic mechanism with zero production callers -- is described as
existing and unreachable, but nothing recommends whether it should be wired
up, left as reference, or removed as dead capacity under the project's own
no-dormant-source-resolvers discipline. A fresh inheritor reading only the
plan would not know either question is open at all.

### the-manifest-fidelity-gap-named-in-the-dispatch-brief-does-not-exist-in-any-document | high | searched exhaustively; this is squarely "something only the coordinator knows"

Grepped every vault document for "manifest fidelity" and "manifest-fidelity"
in any casing and found nothing. Whatever this refers to has never been
written down under this feature. The nearest candidate this review could
construct independently: the M111 sanitiser sidecars declare six amount
replacements for 1T-3T against five covered casillas, and one replacement
for 4T against one covered casilla -- a count that does not map one-to-one,
explained in the adversarial-verification audit as an ordinary PDF-internals
artefact (the same real amount redacted at more than one content-stream
offset) rather than a discrepancy. If that is what "manifest fidelity" names,
it has now been examined and explained. If it names something else, that
content is not recoverable from anything in this vault or git history, and
is lost the moment this session ends unless it is written down explicitly.

### r12-does-not-yet-exist-as-a-named-route-in-any-document-under-this-feature | high | stating what an honest closure would need before render-verifier reports one

Searched every audit and the plan for "R12" under this feature and found
nothing; the route label the dispatch brief uses is chat-only shorthand for
"sweep the other 28 profiles for the same Spanish-only-label-versus-real-
render-language defect M390 had." Naming what its closure would need to be
honest, before that report arrives:

- It must distinguish a *static* claim ("no other profile's label patterns
  look Spanish-only on inspection") from an *evidenced* claim ("verified
  against a real render in a non-Spanish language"), because those are
  different strengths of evidence and M390's own history is the proof: the
  synthetic corpus and the registry text gave no signal that the profile
  could not read an English render, and only reading the real specimen
  found it.
- Of the 29 profiles, 22 have no specimen of any kind (per the static-route
  audit's register), so R12 can be evidenced for at most 7 profiles today;
  for the other 22 it can only be a static claim, and D3 requires that
  distinction be stated per profile, not blurred into one summary line.
- A closure that reports "N profiles checked, none affected" without
  stating which of the N were checked against a real non-Spanish render
  versus checked by reading the registry text would repeat the exact
  pattern that let the M390 defect survive: a corpus authored in Spanish
  cannot itself reveal a Spanish-only pattern is a defect.

### the-number-equals-id-placeholder-is-wider-than-the-exec-record-that-names-it | medium | fifteen casillas, not three, share the shape one record flagged as unexplained

`P01-S01`'s Notes name three Modelo 390 casillas whose `number` field equals
their own casilla id string as "a placeholder sitting in a reviewed field",
recorded and deliberately not fixed. Counted directly against the loaded
revision: fifteen of the twenty casillas in that revision share the exact
same shape, not three. The other twelve are not currently exposed to the
blank-box-guard hazard the exec record was scoped to (most are
`bbox_anchored` profile targets or not targeted at all, so the guard's
`form_number`-first read never reaches them), so the record's specific claim
about guard exposure is not wrong. But the underlying data anomaly the
record calls unexplained is five times larger than the record states, and
nothing suggests anyone has asked why fifteen of twenty casillas in this
revision carry this shape rather than a real record-design number.

### what-a-reader-of-only-the-plan-and-the-adr-would-wrongly-believe | critical | the direct answer to the question the team lead most wanted

Reading only the plan and the governing ADR, without any exec record, a
reader would believe: the printed-box-number hazard is closed (finding
`the-adrs-own-implementation-section-would-mislead-a-reader-who-stopped-there`
above); that 8 of 9 (or 19 of 29, per the plan's own uncorrected Step row)
profiles are specimen-less, when the measured figures are 9 of 9 and 22 of
29; that the campaign's remaining work is only "verify M100" (the one open
Step), when a second, equally real defect (the seventeen inert guards) sits
untracked outside the plan entirely; and that the real-render gate's D4
selection guarantee is durable, when the gate proving it does not import
the function it claims to mirror.

None of these are claims the plan or the ADR states falsely in so many
words -- each is an omission or a stale figure, not an assertion contradicted
by evidence. But the cumulative effect of reading only the top-level
documents is a picture more finished than the exec records, read in full,
support.

## Recommendations

This campaign is not structurally complete, and should not be declared so on
the strength of the plan showing 8 of 9 Steps checked. The honest floor
matches what the dispatch brief itself predicted: a campaign that has
already withdrawn one finding, downgraded a second, corrected a span, fixed
three circular citations and broken HEAD once was unlikely to be spotless in
its bookkeeping, and it is not -- this pass adds two more untracked defects,
one absent handover, one stale plan figure, and two documentary-only
decisions to that ledger.

Create a tracked follow-up for the seventeen inert guards (finding
`seventeen-inert-blank-box-guards-are-a-known-live-defect-with-no-tracked-follow-up`)
before this feature closes. It is a confirmed, live, fabrication-producing
defect across nine modelos, currently held by one Notes paragraph.

Update the ADR Implementation section to name the seventeen outstanding
instances alongside the six fixed ones (finding
`the-adrs-own-implementation-section-would-mislead-a-reader-who-stopped-there`),
so the decision record's own claim matches what the exec records establish.

Write S03's handover into a real exec record, or at minimum a dedicated
Notes-style document, before this session or any inheriting one loses the
deltas table, the three failing bbox offsets, the prototype result, and the
pdfium-canary fact named in the dispatch brief -- none of which this review
could recover from anything committed.

Correct the plan's own `P02.S09` row text from 19 to 22, and fill the plan's
empty Description, Parallelization, and Verification sections, so the
top-level document states its own completion criteria rather than requiring
a reader to reconstruct them from four audits.

Decide, rather than merely describe, the M202 enrolment question and the
disposition of the dormant `verify_declaracion` (finding
`the-m202-enrolment-question-and-the-dormant-verify-declaracion-are-described-but-not-decided`)
-- wire it, document it as intentionally reserved, or remove it, but do not
leave "exists and unreachable" as the final word.

Write down whatever "manifest fidelity" refers to, explicitly, if it is not
the count-mismatch this review reconstructed and examined -- it is currently
recoverable from no source but the coordinator's own memory.

Hold R12's closure to the standard named in finding
`r12-does-not-yet-exist-as-a-named-route-in-any-document-under-this-feature`:
per-profile, and explicit about which of the 22 specimen-less profiles are a
static claim rather than an evidenced one.

Consider importing `_select_extraction_profile` into the real-render gate
test rather than hand-copying its filter (finding
`the-real-render-gate-reimplements-profile-selection-instead-of-calling-the-production-selector`),
so a future regression in either the production selector or a new gate
elsewhere would be caught rather than silently tolerated by two independently
frozen copies.
