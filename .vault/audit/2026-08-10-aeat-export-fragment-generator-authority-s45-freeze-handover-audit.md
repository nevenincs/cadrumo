---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:953e736229d24433a51b19eaebe0cbe4f61900ad1e52df81bf546881f42574df'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
---

# `aeat-export-fragment-generator-authority` audit: `S45 freeze handover to the executing author`

## Scope

**THIS DOCUMENT HAS BEEN OVERTAKEN. IT WAS WRITTEN AS A HANDOVER ARGUING THAT NOBODY BUT THE
AUTHOR MAY LAND THE CHANGE. THE AUTHOR HAS LANDED IT.** At HEAD `35f2b7d161` the migration is
committed and the freeze is over. What follows is corrected in place rather than rewritten, so a
reader can see which claims were about a transient state.

**Both facts this audit originally led with are FALSE at HEAD, and were verified false
independently rather than accepted.**

- *"Modelo 303 does not load at all"* — **false now.** The whole corpus compiles.
- *"The nine load-refused modelos are exactly the nine withdrawn, in both directions"* — **the
  refusal set is empty.** That coincidence described a tree that has since been repaired.

**The mechanism is the correction worth keeping, not the numbers.** The refusals were **orphans of
a half-landed rename, never a property of the corpus.** The loader refused tokens that an
incomplete migration had stranded; when its owner finished the migration, the refusals went with
it. The set arithmetic was a sound measurement of a transient state, reported across two sessions
as a structural property. **Nobody re-measured it because it was load-bearing — and load-bearing
facts are the ones nobody re-measures.**

Measured at HEAD `35f2b7d161`, each independently:

```
FilingProducerKey commits                    1   (0 for this whole campaign until now)
ExportHeaderKey enum                         gone
header_key tokens in the corpus              gone
Modelo 303 export fragments                  0
export fragments surviving  100:6 131:4 145:1 180:6 349:4 720:1  = 22 of 232
the three export gate modules                deleted at HEAD
support_removal_decisions committed          0
```

**THE WITHDRAWAL SHIPPED WITH ZERO DOCUMENTATION, AND THAT IS A STRONGER FINDING THAN THE ONE THIS
AUDIT WAS WRITTEN TO REPORT.** Nine modelos lost their filing-grade export layouts. **Not one
carries a support-removal record in the committed tree.** The disclosure that seven documented
peers were held up as the standard for is absent from HEAD entirely — the eleven records were
never committed.

**Two findings below are therefore NOT defects at HEAD, and their disposition changes.** The M200
record's truncated grounding and the vault step id embedded in eleven `evidence_note` fields are
defects in **uncommitted files**, not in shipped data — the step id appears nowhere in registry
data at HEAD. They are to be corrected *before* those files are committed, not filed as defects
against the tree. That is a better position than this audit anticipated, and it holds only while
the files remain uncommitted.

**THE ELEVEN RECORDS ARE LIVE, UNCLAIMED, AND OUTSIDE EVERY INVENTORY.** Eleven untracked
`support_removal_decisions` fragments — modelos 111, 115, 123 twice, 130, 200, 202 three times and
232 twice — sit in one working tree. Being untracked they are outside the index, so clearing or
inspecting the index does not reach them and **no index-based inventory will ever show them.** They
remain the only unrecoverable content in the whole change: every other part was a modification or
deletion of a tracked file and is recoverable per-file from git. A backup exists outside the
repository at `C:/Users/<operator>/aeat-freeze-backup/untracked-registry-records`. **Nobody has claimed
them, and now that the landing is done and attention has moved on, they are the item most likely to
be lost.**

**What survives this correction unchanged:** the 210 withdrawn fragments and the 29 deleted test
modules, because the export verification surface is gone and that was never a function of the load
story; both silent fail-open validation holes; and Modelo 303 and 390 still carrying no record —
now alongside the other seven.

## Findings

### naming-regression-the-blind-gate-cannot-see | critical | added post-landing; the surviving gate went structurally blind

Measured at HEAD after the landing, by replicating the surviving gate's own extraction. The
dual-spelling scan now returns **three** distinct tokens across the whole corpus:
`amendment_evidence.is_complementaria`, `filing.result_disposition`, `presenter.tax_id`. The
module's population guard demands more than twenty, so **it fires and the last observer is red** —
correctly, and as this audit predicted.

**But the substantive assertion has gone blind in a way nothing predicted, and it is hiding a real
regression.** The migration re-spelled tokens from underscore-separated names to dotted producer
paths. The gate's offending-stem predicate tests `token.endswith("_" + english)`. `presenter.tax_id`
ends with `.tax_id`, **not** `_tax_id`, so it cannot match — **the predicate no longer describes the
shape of the corpus it reads.** The gate is not merely subject-less; its matching rule was silently
invalidated by a separator change.

**What that conceals:** the corpus previously carried `presenter_nif` — the Spanish stem the
project's naming rule requires, and the exact canonical form this gate's own `STEM_PAIRS` encodes as
correct. At HEAD `presenter_nif` is **gone** and `presenter.tax_id` is what replaced it. The
migration moved an AEAT identity concept **from the canonical Spanish stem to the English one**,
which is precisely the defect this gate exists to refuse — and it cannot see it, because the
rename that introduced the violation also changed the separator its predicate is anchored on.

This is the sharpest instance in this document of a pattern it records elsewhere: **a change that
introduces a violation and disables the detector for it in the same edit.** Neither half was
malicious and neither is visible from the other. Remedy: re-anchor the stem predicate on the
token's final path segment rather than on an underscore boundary, then re-run it against HEAD and
expect it to name `presenter.tax_id`. Until then the gate's silence on stems means nothing.

### deleted-verification-surface | critical | the change deletes the capability and the instrument that would detect the removal being wrong

**This is the finding that governs the handover, which is why it is first.** The change does
not merely remove the gates' subjects. It deletes the gates. Confirmed by working-tree status
rather than by reading the committed files: `test_export_completeness_gate.py` (200 lines),
`test_export_completeness_sets.py` (180) and `test_fichero_boe_completeness_parity.py` (514)
are all deleted, and they are three of **29 deleted test modules under `src/cadrumo/`,
totalling 8,122 lines at HEAD** — including `test_export.py`,
`test_fichero_boe_export_roundtrip.py`, `test_export_xsd_validation_gate.py`,
`test_modelo_303_390.py` and `test_modelo_720_fichero_boe_roundtrip.py`.

Each deletion is internally consistent in isolation: a test whose subject was withdrawn cannot
be kept. **The combination is the finding.** This change withdraws 210 of 232 export fragments
and deletes 8,122 lines of the tests that verify exports, in one uncommitted step, so the two
halves cannot be reviewed against each other once landed. That is not an argument for refusing
the change. It is the argument for why nobody who did not author it may land it.

A correction is owed on the record, because the reassuring version of this was published
first. An earlier reading of this campaign concluded these gates would "fail loudly" on their
anti-vacuity guards, and named five specific assertions. That reading measured every gate at
HEAD through the object store — the correct discipline for committed content — and never ran a
working-tree status on the gate modules themselves. **Guards cannot fire from a file that is
not collected.** There are no reds; there are absences. The mechanism generalises and it is
the dangerous half: `git show HEAD:` gives a pristine view of a file the change under
discussion deletes, so the discipline that protects against reading the dirty tree is blind to
the dirty tree's deletions. When reasoning about what a change does to a gate, run `git status`
on the gate module first — reading the observer at HEAD says nothing about whether the observer
survives.

**What this does not invalidate**, so nobody over-corrects: measurements of these gates taken
at HEAD on a clean checkout are sound and stand, because there the modules exist and genuinely
fail. This finding is about the **post-landing** tree, which no measurement has covered because
no tree holds it. Two claims about two trees — keeping them apart is the same discipline whose
absence produced the error.

### last-observer-standing | critical | one module survives, and quieting it disables the last alarm

`src/cadrumo/domain/calculations/registry/tests/test_export_header_key_naming.py` is the sole
export-verification module the change leaves untouched. It is **the last observer of this
surface**, and it will red.

Its population guard demands more than twenty distinct tokens and will find two: the corpus
falls from 70 to 2 (`complementaria` and `declaration_type`, both Modelo 131's). That red is
correct and is the only remaining signal that the surface was withdrawn at all.

Its substantive assertion, separately, passes **vacuously**. Both `presenter_tax_id` (modelos
115, 123) and `presenter_nif` (111, 130, 200, 202, 232, 303, 390) sit entirely inside the
withdrawal set, so no offender pair can form. The module's own docstring anticipates exactly
this — it warns that a pass without those occurrences being renamed means the scan has gone
blind rather than the corpus clean — and prescribes a remedy, renaming the `presenter_tax_id`
header keys in modelos 115 and 123, which **becomes unperformable because those fragments are
deleted**.

**A lone red gate whose documented remedy can no longer be applied is precisely what gets
"fixed" by deletion.** Anyone tempted to quiet it, lower the threshold, or retire the module is
disabling the last alarm rather than one of four. Either correct that docstring in the same
change, or re-anchor the gate on a concept that survives; do not silence it.

One note for whoever reads the commit that made this gate scan both `header_key` and
`producer_key`: that change cured blindness to a **rename**. The event arriving is a
**withdrawal**. Scanning both field names finds two tokens instead of two. What keeps the loss
visible is the pre-existing population guard, not that fix.

### subject-loss-reaches-beyond-the-export-modules | high | a gate nobody enumerated also loses its subject

The list of gates losing their subjects was assembled from the export-verification modules and
was **incomplete**. At least one gate outside that set is affected:
`TestSubmittedFileContext::test_period_mismatch_raises_parse_error`, which fails with
`modelo 130 revision 2019-y-siguientes has no exports`. It appears in none of the enumerations
this campaign produced, because every one of them started from the modules whose names contain
`export` or `completeness` and that gate's does not.

Treat the enumeration as a **sample with an unmeasured remainder**, not a population. The
defining property is not "the module is named for exports" — it is "the test resolves a
revision that had an export layout". Any module doing that is affected regardless of what it is
called, and only a run over a tree carrying the change can enumerate them.

The attribution deserves recording because it was proved rather than asserted: **the same node
id also fails on a clean clone, for an entirely unrelated cause.** One node id, two trees, two
different reasons. A bare failure count would have shown one number and read as one fact, and
either tree alone would have supported a confident wrong story — the clean clone saying the
change is innocent, the dirty tree saying the change broke it. Neither is true on its own.

### m200-truncated-legal-refs | high | the M200 withdrawal record carries the first 6 of 19 legal_refs

All eleven `support_removal_decisions` records were compared against the layout each one
withdraws, resolving `subject_id` to the layout declaration in the same revision and
comparing `legal_refs` and `source_refs` as exact strings. Ten are byte-identical. One is
not. The record at
`src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/support_removal_decisions/0001-export-layout-support-removal.toml`
carries six entries where the layout in `export/0000-manifest.toml` declares nineteen.

The six are the first six of the nineteen, in source order. **Nobody selecting provisions on
the merits produces a prefix** — that is what makes this mechanical rather than a considered
narrowing. Thirteen provisions are dropped: `ley-27-2014:art-36`, `art-100`, `art-12`,
`art-15`, `art-21`, `art-22`, `art-31`, `art-32`, `art-13`, `art-16`, `art-25`, `art-26`, and
the whole `rd-634-2015:art-3` citation.

It passes registry validation, which is why nothing caught it — see the second validation
hole below. The remedy is one field in one file: replace `legal_refs` with the layout's full
nineteen, copied verbatim and in order.

### silent-layout-withdrawal | high | nothing refuses deleting an export layout no construct cites

The disclosure discipline everyone believed was a rule is an artefact of citation topology.
Each of the seven documented modelos had a construct citing `export_layouts = ["<layout-id>"]`;
deleting a cited layout leaves a dangling construct reference and the registry refuses to
load, so the author was **forced** to substitute a decision record. Modelo 303 across all six
revisions, and Modelo 390, cite no `export_layouts` in any construct. Their layouts were
uncited, so deletion was silent — no dangling reference, no refusal, no prompt.

`src/cadrumo/domain/calculations/registry/_validate_constructs.py` checks only the opposite
direction: a decision whose subject is **still present** fails. Nothing checks a subject that
vanished without a decision. The hole fails open exactly where a layout is unreferenced, and
it would silently withdraw filing-grade capability from any uncited layout in future.

The canonical home already exists and already solves this one scope level down.
`src/cadrumo/domain/calculations/registry/_validate_export_exemption.py` opens by naming the
identical defect for casillas: an exemption expressed by absence, with nothing verifying that
an unaddressed casilla is genuinely unrepresentable rather than merely un-annotated. The
casilla level got a declared reason and a closed vocabulary. The layout level never did. And
that module's own early return — a revision declaring no fixed-width layout is a no-op —
**is** the hole: delete every layout and the validator goes silent by design.

### withdrawal-refs-need-not-cover-subject | medium | validation checks refs resolve, never that they cover

The second hole, and the one that let the M200 defect through. The support-removal validator
requires each cited `legal_refs` entry to resolve in the snapshot catalogue and requires one
accepted source tier. It never requires the record's grounding to **cover** the withdrawn
subject's grounding. A record citing one of nineteen provisions validates exactly as cleanly
as one citing all nineteen.

Both holes are silent, both fail open, and both are under-declaration defects in registry
validation rather than in any modelo's data. They outlive this step entirely.

### s45-token-in-shipped-data | high | eleven wheel-shipped records embed a vault plan-step id

Every one of the eleven `evidence_note` fields opens with the literal string
`S45 withdraws this filing-grade layout atomically because...`. Everything under
`src/cadrumo/_data/` ships inside the wheel. The reference direction is one-way: vault
documents cite code by locator and code never cites the vault. This is a hard blocker on
landing, and it is cheap to fix because none of the eleven is committed.

The corrected sentence keeps the reasoning verbatim and drops the step id:

`This filing-grade fixed-width layout is withdrawn atomically because its official record design contains producer fields that do not yet have canonical typed producer authority; retaining a partial layout would permit silent under-declaration.`

### m131-convergence | high | three gates collapse onto one surviving subject

Measured separately, three independent gates converge on Modelo 131 as their only surviving
subject. The completeness gate loses both its cases, 130 and 390. The parity gate loses six of
its seven parity cases and seven of its eight dormancy modelos. The header-key naming gate
loses 68 of its 70 distinct tokens, and both survivors — `complementaria` and
`declaration_type` — are M131's. Modelos 100, 145, 180, 349 and 720 contribute no header
tokens at all.

Re-anchoring the completeness gate onto M131 is necessary and **does not restore redundancy —
it relocates a single point of failure**. A future edit to M131 would silently move three
gates at once.

On the fixtures the re-anchor needs, the distinction matters: the draft fixture **survives** in
the working tree at `src/cadrumo/application/filing/tests/_export_support.py`, so using it is a
promotion. The headers fixture does **not** survive — it lived only inside the deleted parity
module, so recovering it means reading the deleted file's committed blob. That is a
**reconstruction from a file this change removes, not a promotion of live code**, and it should
be recorded as such in whatever lands it. It is one line, returning a single
`declaration_type` entry.

### records-exist-only-uncommitted | medium | eleven files with no git history

All eleven decision records are untracked. Zero exist in the object store at HEAD. Every other
part of this change is a modification or deletion of a tracked file and is recoverable
per-file from git; these eleven are the only genuinely unrecoverable content in roughly 1,450
files. The honest form of the release condition is therefore not that Modelo 303 and 390 lack
a record while seven peers have one — it is that **no withdrawal in this change is documented
in anything a commit holds, and two are not documented anywhere at all.** Those are different
remediation shapes: nine need committing, two need authoring and committing.

## Recommendations

**Fix the M200 record before landing.** Replace its `legal_refs` with the layout's full
nineteen. One field, one file, and the only known-wrong content in the change.

**Author the seven missing records.** Six for Modelo 303, one per revision, and one for
Modelo 390. The method, which the ten clean peers already follow and which should be stated so
it is not rediscovered: the record inherits the withdrawn layout's own `legal_refs` and
`source_refs` verbatim and in order. No legal reference is authored. This satisfies the
validator by construction, because those refs already resolve in that revision, and every
`aeat-dr-303-*` and `aeat-dr-390-2025` source declares the `layout_authority` evidence tier
the validator demands. Drafted content is available from this campaign's scratchpad and is
built to the correct standard rather than to M200's.

Two cautions for those seven. Modelo 303's layout id is the same string in all six revisions,
unlike every multi-revision peer, so `subject_id` repeats while decision ids should not.
And revision `2009-y-siguientes` cites a 2025 record design; that is pre-existing at HEAD and
should be **carried forward faithfully and flagged separately, never silently corrected inside
a withdrawal record**.

**Do not add construct citations to Modelo 303 or 390.** They never had them, the projection
in `src/cadrumo/domain/calculations/registry/_support_matrix.py` reads the revision directly,
and adding them delivers wider than the defect.

**Correct the eleven evidence notes in the same change that lands them.**

**Re-anchor the completeness gate onto M131 rather than deferring it**, and record in the same
breath that this leaves the surface single-subject. Deferring ships the pre-write thin-draft
refusal unexercised.

**Close both validation holes as their own change, with their own proof obligation.** A gate is
unproven until it bites, and neither belongs inside a landing this large. The layout-absence
gate belongs in the existing exemption validator family, at registry build. Its predicate must
not be inferred from whether a record design exists: measured at HEAD, fifteen revisions cite a
record-design source while declaring no export layout at all — 036, 184, 190, 193, 220, 308,
309, 322, 347, 353, 360, three Modelo 369 schemas, and 840 — and **none is a withdrawal**. A
gate refusing them fires on a legitimate population. The structural reason is that a stateless
validator cannot distinguish "was never built" from "was silently removed"; that bit is
historical and the registry has no history axis. Supplying it by **declaration** rather than by
history is the shape that works: a closed per-revision posture, refusing a withdrawn posture
with no matching decision record, an implemented posture with no layout, and a not-implemented
posture with one. The fifteen then declare their state honestly and the gate refuses nobody.

**Verify that the change loads before landing it.** This is the acceptance test and it is not
answered. Landing may trade thirty orphan-token refusals for fifteen dangling-reference
refusals rather than clearing the load. The loader does discover the
`support_removal_decisions` fragment directory — section fields are derived from the schema by
annotation shape and discovery is a recursive glob, so the directory name is irrelevant — but
that only establishes the records load, not that the tree does. Four unknown extraction-profile
references remain unaccounted for and may be a second unclosed hole.

**The plan row has been corrected.** S45's scope semicolon omitted `src/cadrumo/_data/registry/`
entirely, so every deletion and modification under it fell outside the step performing them.
The path `src/cadrumo/_data/registry/aeat/modelos/` has been appended through the owning plan
verb; fifty-one of fifty-two row texts are byte-identical afterwards and the only other change
is one whitespace normalisation before a wave heading. The narrower alternative — scoping only
the Modelo 303 revisions directory — was rejected because it would have legitimised
thirty-four paths while leaving one hundred and seventy-six equally unscoped, treating the
sample as the population.
