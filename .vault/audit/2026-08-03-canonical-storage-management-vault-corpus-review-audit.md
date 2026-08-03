---
tags:
  - '#audit'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:562e5b0249096e789950e61e6b43ab60b4633ab5b7e17919ed2d57e4d1678d90'
related:
  - '[[2026-08-03-canonical-storage-management-adr]]'
  - '[[2026-08-03-canonical-storage-management-plan]]'
  - '[[2026-08-03-canonical-storage-management-self-duplication-review-audit]]'
  - '[[2026-08-03-canonical-storage-management-honesty-review-audit]]'
  - '[[2026-08-03-canonical-storage-management-dormancy-burndown-audit]]'
  - '[[2026-08-03-canonical-storage-management-semantic-duplication-burndown-reference]]'
  - '[[2026-08-03-canonical-storage-management-closure-criterion-reference]]'
  - '[[2026-08-03-canonical-storage-management-closure-statement-reference]]'
  - '[[2026-08-03-canonical-storage-management-enforcement-gates-reference]]'
---

# `canonical-storage-management` audit: `vault corpus review`

## Scope

The companion audit held the campaign's code to its no-duplication standard.
This one holds its documents to the same three tests: is each fact stated once,
does each fact have a canonical home, and is anything superseded still readable
as current. Ten documents, roughly 4,850 lines, written incrementally by five
agents while execution ran.

**Measurement basis, stated because the last audit got this wrong.** Every claim
about code is pinned to committed `HEAD` `c16bb9a0ae` and was read out of
`git show`, never out of the working tree. Every claim about a document is as of
19:20 on 2026-08-03. Both qualifications are load-bearing: the taxonomy module
was rewritten under this review — 1,292 lines with per-member participation
declarations at the start, 23 KB with three `EXCLUDED` spellings twenty minutes
later — and the ADR was amended forty-nine seconds into it. A corpus audit of a
corpus being written is a snapshot, and is labelled as one.

The prior audit's finding six is retracted on exactly this ground; the retraction
is recorded in place in that document rather than by deletion, and that item is
closed.

## Findings

### burndown-taxonomy-entry-count-is-emphatic-undated-and-wrong | high | A correction that instructs future readers to reject any other number is itself wrong by eighteen entries and fourteen files

The semantic-duplication burndown reference, under the heading "Corrections
found while verifying this inventory", states: "**The taxonomy has 28 entries,
settling a dispute the ledgers left open.** Measured directly against the live
mapping: 28 entries, of which exactly 1 is a file. Any 27 figure is wrong."

Counted at `HEAD` `c16bb9a0ae`, the taxonomy declares **46** entries, of which
**15** are `StorageNodeKind.FILE`. The claim is low by eighteen entries and by
fourteen files.

Three properties make this the corpus's worst instance rather than an ordinary
stale number. It carries **no date and no commit** — every neighbouring statement
in the closure documents dates itself, this one asserts the present tense. It is
**maximally emphatic**: "Measured directly", "Any 27 figure is wrong" is an
instruction to a future reader to reject a divergent count, and the counts a
future reader will measure are now all divergent, so the sentence actively
defends the wrong answer against correction. And it is **filed as a correction** —
a reader's prior is that a line under "Corrections found while verifying" is the
settled one. The "exactly 1 is a file" half is the clearest tell: the campaign
spent the day declaring file leaves, so the figure could only have been true very
early.

The fact has an obvious canonical home and it is not this document.
`len(STORAGE_TAXONOMY)` is the authority; the burndown should cite it and state
the dispute it settled without freezing a cardinality. Verdict `CONVERGE` onto
the code, with the number removed rather than refreshed — refreshing it just
schedules the next drift, which is the same lesson `R16` reached the long way.

### closure-criterion-reports-a-closed-family-as-open | medium | Family 1 is recorded as open with its five secret-store files "still ungoverned"; all five are declared at HEAD and the Step is checked

The closure-criterion reference lists "**Family 1 — fixed file leaves directly
under a declared category** (8 names, 14 sites, `S89`, open)" and states "the
five secret-store files themselves are still ungoverned."

At `HEAD` all five are declared taxonomy members — `SECRETS_MASTER_KEY`,
`SECRETS_MASTER_KDF`, `SECRETS_MASTER_LOCK`, `SECRETS_KEYRING_LOCK`,
`SECRETS_MASTER_RECOVERY_KEY` — landed by the commit whose subject is declaring
the secret store's five file leaves. The plan carries `W02.P06.S89` as checked.
So the document disagrees with both the code and the plan, and it disagrees in
the direction that overstates remaining work on the campaign's most
security-load-bearing filenames.

The same document's burn-down line inherits the error: "Still open: Family 1 (8
names/14 sites, `S89`), Family 2 (7 names/7 sites, `S90`/`S91`), and Family 4 (5
names, `S107`) — 20 names across roughly 26 sites remain, not 23/34." With
Family 1 closed the residual is twelve names across roughly twelve sites.
Families 2 and 4 are correctly open — `AUDIT_LIVE`, the submissions nested
segments and the attachments manifests directory are all absent at `HEAD` and
present only in the working tree, so those rows are accurate and were checked
rather than assumed.

Verdict `CONVERGE`. The canonical home for a Step's open/closed state is the
plan, and a reference restating it should cite the Step rather than duplicate its
status.

### deletion-record-has-no-home-in-the-schema-it-was-filed-under | medium | The dormancy audit's three required sections are all empty and its content sits under headings no validator knows

The dormancy-burndown audit carries empty `## Scope`, `## Findings` and
`## Recommendations`, with every substantive paragraph under `## Context`,
`## Deletion record` and `## The unbuilt status-reader feature`. It is the only
document in this campaign that `vaultspec-core vault check body-sections` flags,
and it fails on all three required sections.

The content itself is among the corpus's best: four deleted members with the two
independent confirmation methods named, the re-trace at `HEAD` before deletion,
why the `status-cache` scaffolding was left standing, and a resumption point
precise enough to rebuild the member if the status-reader is ever built. None of
it is reachable by a reader or a tool navigating the audit shape the other nine
documents use, and a validator that cannot see a deletion record cannot tell it
from an empty scaffold.

Verdict `CONVERGE` on structure only — move the existing prose under the three
required headings; change no wording. The facts are sound and are corroborated
elsewhere: the four-member deletion agrees across this audit, the ADR's `R16`
correction paragraph, and the commit that deleted them, which is the corpus
behaving correctly.

### plan-step-row-still-asks-for-a-withdrawn-scope-axis | low | `S88` reads "Add a RUN_RELATIVE scope axis" and is checked, while the axis was deliberately never built

Plan row `W02.P06.S88` is checked and its action text begins "Add a
`RUN_RELATIVE` scope axis anchored on the runs root". No `RUN_RELATIVE` exists at
`HEAD`; the three run-trace filenames were declared through the grammar mechanism
instead.

**This is a preserved trail, not a stale duplicate, and the distinction is worth
recording since the two look identical.** The withdrawal is documented in three
places and documented well: the exec record for `S88` states the axis "is now
withdrawn", explains that the honesty reviewer's own recommendation was retracted
on finding the grammar mechanism already covered the shape, and — the part that
makes it trustworthy — records that the retraction was verified against landed
code before the Step was marked done rather than either the recommendation or its
retraction being taken on report. The closure-criterion reference records the same
withdrawal, and the honesty audit records both the original proposal and its
retraction with the reasoning that proposing the axis "would have introduced the
precise defect this campaign" exists to remove. Rewriting the Step row would
destroy that arc and is correctly not done, since the row is an
identifier-bearing record of what was asked.

The residual risk is narrow and real: the plan is the widest-read surface and is
the one place carrying no marker, so a reader checking progress sees a completed
Step asserting a member that does not exist. The cheap fix is a short
superseded-by note appended to the row, not a rewrite.

### exec-scaffolder-injects-the-heading-into-its-own-instruction | low | A tool defect duplicates the heading and scope list inside the comment that was meant to explain them; nine records here and other campaigns too

Nine of this campaign's sixty-nine exec records carry a mangled `STEP RECORD`
comment. The template sentence "The `{heading}` and `{scope_block}` placeholders
below are machine-filled ... do not fill them by hand" had its two placeholder
tokens substituted with real content, so the comment now contains a second full
copy of the Step heading and of the scope file list, spliced mid-sentence, with
the instruction it was carrying destroyed. Not one of the nine retains the
literal tokens, so the substitution is unconditional where it fires.

This is not the campaign's authorship — the same artefact appears in unrelated
campaigns' exec records, so the canonical home for the fix is the
`vaultspec-core vault add exec` template, upstream of this vault. Recorded here
because it is duplication in the corpus and because a reader hitting a garbled
comment block has no way to know whether it is a tool defect or a hand-edit.

### r16-both-counts-now-stated-and-verified | none | Closed during this review, and the closing form is better than the finding that prompted it

`R16`'s excluded-set cardinality was the corpus's known repeat offender —
amended from eight to eleven to nine. The prior audit reported it wrong a fourth
time; that report was itself wrong, measured against the working tree, and is
retracted in place in that document.

The ruling now reads correctly and durably: it states that
`FINGERPRINT_EXCLUDED_STORAGE_FIELDS` is keyed by settings field while the
taxonomy is keyed by member, that a file-kind leaf under an excluded directory
category can be an excluded member carrying no field of its own, that the two are
therefore different cardinalities by construction, that both are nine at a named
commit, and that "this agreement is not guaranteed to survive the next
declaration, and a future reader must recompute rather than trust either number
here." Verified: nine excluded members at `HEAD`, matching the nine enumerated,
in order.

That last sentence is the pattern the burndown's 28-entry count and the closure
criterion's Family 1 status both need — state the authority, pin the reading to a
commit, and tell the reader to recompute. The corpus has already produced its own
remedy; two documents have not adopted it.

### what-the-corpus-gets-right | none | Three patterns worth preserving, checked rather than assumed

**The closure-statement skeleton is exemplary and should be the template for this
project's closure documents.** It declares itself a skeleton in its title and
summary, leaves the verdict deliberately open, carries `STATUS: pending` markers
with instructions for replacing them, and — the part such documents almost always
omit — states for every element what would have to be true for the answer to be
"no", with the stated reason that "a skeleton with a shape only for 'yes' will
find one". It cites the companion audit by commit SHA, and flags one
carried-forward claim as needing independent verification before the statement
ships rather than absorbing it.

**The 23/34 census is duplicated across two documents and handled correctly in
both.** The honesty audit states it as a dated finding, which is right for a
rolling log the template forbids rewriting. The closure-criterion reference
qualifies it "at the time the census ran" and then burns it down explicitly. The
mechanism is sound; only the Family 1 row inside that burn-down went stale, which
is a maintenance miss rather than a design fault.

**"Five gates" in the enforcement-gates reference is not stale**, and it is worth
saying so since seven now exist. That document is scoped in its own first sentence
to "the five gates mandated by the campaign's rulings R4, R5, R9, and R16". Those
four rulings do mandate five; the directory-agreement and grammar-vocabulary gates
arose from later findings, not from those rulings. A count bounded by its source
stays true when the world grows, which is the same property the burndown's
unbounded 28 lacks.

**One correction in the burndown was re-verified and still holds.** The "fifth
unpinned `buckets` literal" at `application/_journal_repository.py:196` is present
at `HEAD` exactly as described, and is the same site the directory-agreement gate
exempts by name. Accurate, and still open.

## Recommendations

Delete the 28-entry count from the burndown reference rather than refreshing it,
replacing it with a citation to `STORAGE_TAXONOMY` and a one-line statement of
which dispute it settled. A cardinality restated in prose has no maintainer; that
is what produced both this finding and `R16`'s three amendments.

Correct the closure-criterion reference's Family 1 row to closed, citing `S89`
rather than restating its status, and recompute the residual line that depends on
it. Confirm Families 2 and 4 stay open — they are correct at `HEAD` today, and
will close from the working tree shortly.

Move the dormancy audit's prose under the three required headings without
rewording it. Append a short superseded-by marker to plan row `S88` rather than
rewriting the row. Raise the exec-scaffolder placeholder substitution upstream
against `vaultspec-core`, with one of the nine records as the reproduction.

Adopt `R16`'s closing form as the corpus convention for any count that survives in
prose: name the authority, pin the reading to a commit, and instruct the reader to
recompute. Every count this review found stale lacked all three, and the one that
carries them is the one that stopped drifting.

## Verdict

**The corpus does not meet the standard, but it misses it far more narrowly than
the code did, and it already contains its own cure.**

Two facts have genuinely drifted and both are single-site fixes: an emphatic
undated taxonomy count wrong by eighteen entries, and a closed family reported
open. One document is structurally misfiled. Nothing else is duplicated
carelessly. The larger classes I expected to find — rulings restated in
references, Step text contradicting the ADR, superseded rulings readable as
current — largely are not there. `R23` is explicitly marked retained and
superseded. `R12`'s withdrawal, `R13`'s member-count correction and `R20`'s
resolved blocker are each recorded at their own ruling and named again in the
amendment log, which states outright that its purpose is to record that the
correction discipline was followed repeatedly rather than to hold the corrections
itself — a clean separation of trail from fact.

The failure mode is narrower than "the documents drifted". Every stale fact this
review found is a **count restated in prose with no date, no commit, and no named
authority**, and every count that carries those three is still true. That is a
single mechanical property, not a discipline problem, and the campaign discovered
it itself: `R16` now tells its reader to recompute. Two documents predate that
lesson and have not been brought forward.

The honest asymmetry with the code audit is worth stating plainly. There the
campaign shipped new duplicate authorities while removing old ones, which is a
design failure. Here it restated a handful of numbers and let two go stale, which
is a maintenance failure in a corpus written by five agents across one day —
cheaper to fix, and already fixed once, in the ruling that had drifted most.
