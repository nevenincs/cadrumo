---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
  - "[[2026-07-26-modelo-100-parser-glyph-merge-adr]]"
---

# declaracion-real-render-verification audit: corpus consistency sweep

## Scope

A cross-document consistency sweep of the whole feature corpus: both ADRs
(declaracion-real-render-verification-adr, modelo-100-parser-glyph-merge-adr),
all audits under the feature tag, every exec record under the feature exec
directory, and the plan. Checked for four things named by the dispatch: stale
counts, contradictions between records, claims contradicted by current HEAD,
and withdrawn or corrected claims still standing uncorrected elsewhere.
Report-only: no registry data, production code, test file, or existing vault
document is modified by this pass. Every claim below states measured against
inferred and names the method. The semantic code index was not consulted;
every figure comes from direct file reads, tomllib loads, or git log / git show.

## Findings

### negative-result-audit-is-refuted-by-the-very-next-commit-in-the-same-campaign | critical | measured, a 28-minute gap between the claim and its refutation

The form-number-sourcing-negative-result-audit (committed 718a6284d7,
2026-07-26 22:57:36) states as its headline finding "there is no printed box
number to source for any of the seventeen targets" and recommends closing the
step on the grounds that it is "unsatisfiable under its own constraint." Its
own method section searched only the diseno-de-registro corpus tree
(the fixed-width fichero-BOE positional-range files) and did not check the
separate bundled AEAT-instructions corpus tree.

Twenty-eight minutes later, commit 1a7c2ef704 (23:25:28, "record the
inert-guard disposition and split the class") armed seven of those same
seventeen targets by reading exactly the instructions tree the negative
result never checked: instr_mod_349.txt names Casilla 01 through 04 directly,
and modelo-180-ayuda-resumen-datos.html names Casilla01 through 03. The
registry today carries form_number on all seven. This session independently
re-derived all seven values against the instructions text in an earlier task
(form-number-grounding-and-two-decisions-audit, commit eea5250898) and
confirmed them correct.

Nothing marks the negative-result audit as superseded, retracted, or
partially wrong. It carries no cross-reference to P04-S15 exec record (the
document that refutes it), and no later document references it by name at
all -- it is an orphaned dead end that a reader encountering it today, with
no timestamps compared, would read as the current, settled answer to whether
these seventeen targets can be sourced. Measured: the commit timestamps, the
corpus-tree distinction, and the registry state at HEAD. Inferred: whether
the author of the negative result genuinely never checked the instructions
tree, versus checked it and missed the box-number prose -- the document own
method section supports the former but does not state it explicitly.

### an-audit-authored-nine-minutes-earlier-is-now-stale-in-exactly-the-way-this-sweep-is-looking-for | high | self-reported: an earlier audit in this campaign is superseded by the next commit

The form-number-grounding-and-two-decisions-audit (committed eea5250898,
08:18:49) found that _DECLARATION_CASILLA_RECONCILE_MODELOS docstring,
already corrected once for a false Modelo 202 exclusion reason, now stated a
second wrong reason ("casilla-id alignment has not yet been confirmed," when
it is confirmed complete), and recommended correcting it a second time.

Commit 3f3e154f32 landed nine minutes later (08:28:10, "stop the enrolled-set
docstring restating why each modelo is out") and rewrote the docstring to
stop stating a per-modelo reason at all -- it now states the two real gates
generically and explicitly documents its own two-time drift in its own prose
("it first claimed Modelo 202 had no declaracion_pdf surface... the
correction then claimed its casilla-id alignment was unconfirmed"). Read at
HEAD (application/modelo/_reconcile.py, lines 114-121), the docstring is now
correct and self-aware; the grounding audit own Recommendations-section text
("Correct the docstring Modelo 202 exclusion reason a second time... to no
real or facsimile specimen exists") is now stale -- the fix that landed took
a different, arguably better shape (removing the per-modelo enumeration
entirely rather than replacing one wrong sentence with a right one), and
that document does not say so. Measured directly: both commit timestamps and
the current docstring text.

### the-campaign-close-honesty-review-is-almost-entirely-superseded-and-carries-no-annotation-saying-so | high | a fifteen-hour-old audit read at face value describes a state that no longer exists in at least six places

The campaign-close-honesty-review-audit (committed 31fe66a484, 2026-07-26
12:35:51) is the earliest full-corpus review and every subsequent document in
the campaign has, individually, addressed one of its findings -- but nothing
links them back to it, and the document itself carries no "superseded" or
"resolved" marker anywhere, unlike the ADR and several exec records which add
explicit "Updated 2026-07-27" or "CORRECTED 2026-07-27" passages inline. A
reader opening this document today, without comparing commit dates across
six other documents, would believe all of the following, none of which is
true at HEAD:

- "Handled for six of twenty-three now-known instances" -- the ADR own
  2026-07-27 update states thirteen of twenty-three, and the arithmetic is
  visible in the ADR itself (six original plus the seven armed later).
- "Seventeen inert guards... with no tracked follow-up" -- now split and
  tracked as P04.S15 through P04.S24: seven armed, three genuinely blocked
  (Modelo 193), seven reclassified as a value_kind schema defect and fixed
  (see finding below).
- "P02.S09 own Step row text reads... 19" -- re-read at HEAD, the plan row
  states 22. Already corrected; this finding is fully resolved.
- "P01.S03... No exec record exists for it at all" -- an exec record now
  exists (P01-S03, committed 429efb0988, 2026-07-26 18:06:08, roughly five
  and a half hours after this review), and it is a substantial one.
- "The M202 enrolment question... has no plan Step" -- now P04.S17, closed
  with a recorded D5 decision (blocked on specimen, not registry gap).
- "R12 does not yet exist as a named route in any document" -- R12 was later
  defined precisely (124 immune targets, 102 bbox_anchored plus 22
  numeric_casilla; 154 exposed, all named_label) and a later audit this
  session attacked it directly, finding the partition holds.

One item this review raised is only partially resolved: see the next finding
on P04.S18. Measured: commit timestamps for every cross-reference above, and
direct comparison of the review own finding text against the current plan,
ADR, and exec-record content.

### p04-s18-is-checked-complete-but-its-own-exec-record-says-the-decision-was-not-made | medium | ambiguous whether classification satisfies a step titled decide

The plan marks P04.S18 ("Decide the disposition of verify_declaracion") [x]
complete, and an exec record exists for it (P04-S18, 2026-07-27). Read
literally, the exec record own Outcome and Notes sections state the opposite
of what the Step title asks: "The disposition deliberately stops short of a
recommendation to delete or to wire... the choice depends on whether the
fresh-compute capability is wanted, which is not this campaign own question."
An earlier audit this session reached the same place independently and
phrased its recommendation as "Decide P04.S18 between enrol and delete... if
the product intent... is still live, that is real work worth scoping as its
own Step; if it is not, deletion is cleaner" -- a recommendation to decide,
not a decision.

The honesty review own original complaint on this exact point ("nothing
recommends whether it should be wired up, left as reference, or removed") is
therefore still literally true at HEAD, even though the Step reads as closed
and the campaign own bookkeeping treats the question as settled. This is
stated as ambiguous rather than a forced verdict: it is defensible that
"decide" was satisfied by "characterize precisely and explicitly defer the
wire-versus-delete choice to whoever owns the CLI surface," since that is
itself a decision (not to decide autonomously here). It is equally defensible
that the Step should have stayed open, or been retitled, since its own exec
record plainest sentence is that the disposition was not decided.

### p04-s24-is-checked-complete-with-no-exec-record-anywhere-in-the-tree | medium | the underlying fix did land; only its execution record is missing

The plan marks P04.S24 ("Correct the seven decl.ejercicio targets declared
value_kind amount on what is a tax year") [x] complete. No P04-S24 exec
record exists under the feature exec directory, nor under any other name
found by a direct directory listing. This is not a stale-count finding: the
substance was independently verified by loading the seven affected
extraction profiles directly (tomllib, not the vault) and confirming all
seven now declare value_kind = "text" matching their casilla data_type of
year -- the fix is real and landed in commit 251c06166e, 2026-07-27 09:19:26,
"declare the ejercicio targets as text, since a tax year is not an amount."
So the work is done; only the exec record documenting it is absent, which is
a direct gap against this project own plan-closure-requires-exec-records
discipline (a checked Step needs a matching exec record or an explicit
deferred-carry-forward note in a close audit; neither exists here).

### manifest-fidelity-has-two-different-referents-in-this-corpus-and-neither-document-says-so | medium | genuinely ambiguous, not a contradiction -- flagged as such rather than resolved

The campaign-close honesty review could not find the phrase "manifest
fidelity" anywhere (it searched case-insensitively and reported zero hits,
correctly -- at the time it was written, 12:35:51, the phrase did not yet
exist in the vault; P01-S03, the document that introduces it verbatim
("Manifest fidelity is a corpus defect in its own right"), was committed
five and a half hours later at 18:06:08). Not knowing this, the review
constructed its own candidate referent: the Modelo 111 sidecars declaring
six amount replacements for 1T-3T against five covered casillas, "explained
in the adversarial-verification audit as an ordinary PDF-internals
artefact."

P01-S03 own later use of the identical phrase names a different thing
entirely: the Modelo 100 sidecars declaring one replacement constant
(1.000,00) while the length-preserving sanitiser actually wrote two
(1.000,00 and 1.001.000,00) -- the exact gap fully quantified in the
manifest-reconciliation-gap audit this session (124/133/137 declared versus
70/74/78 rendered, explained without remainder by the
1.001.000,00[4:12] == 1.000,00 nesting). That reconciliation audit does not
mention Modelo 111 or use the phrase "manifest fidelity" at all -- it was
scoped to the specific M100 count the coordinator asked about directly, not
to resolving which prior reference the phrase was meant to name.

So the corpus now contains two independently-reasoned, independently-correct
answers to "what does manifest fidelity mean," attached to two different
modelos, and nothing anywhere states that they are two different things
rather than one restated twice. This is named as ambiguous: it cannot be
established from the vault alone which of the two the coordinator meant when
the phrase was first used verbally, and both candidate explanations are now
fully worked out and correct on their own terms.

### the-6-of-23-to-13-of-23-and-ledger-n1-corrections-checked-clean | low | a negative result, reported as one

Specifically checking the two numeric corrections the dispatch named by
number: the printed-box-hazard instance count is consistent everywhere
found. The ADR states "That closes six of twenty-three known instances" in
its original Implementation prose and immediately follows it with an inline
"Updated 2026-07-27: thirteen of the twenty-three are now armed," so both
the six and the thirteen are present in the same document, dated and
reconciled against each other (six original plus seven armed equals
thirteen, and the arithmetic is stated). No other document found states a
bare "six of twenty-three" as a current, undated claim.

The ledger-evidence correction (thirteen pages of N26 statements reframed
from "real" to the project own fixtures, n=1 across the whole corpus) is
consistent everywhere it appears: the modelo-100-parser-glyph-merge ADR
states the corrected n=1 conclusion four times in its own text with the
correction reasoning inline, and P04-S22 exec record carries the identical
correction verbatim with its own "CORRECTED 2026-07-27" marker and the same
Producer/Creator evidence independently re-confirmed in an earlier task this
session. No document anywhere in the corpus was found still asserting the
pre-correction "thirteen pages of real bank statements" as a current,
uncorrected claim.

R8 severity language (asserted, provisional, confirmed) is likewise
consistent: the ADR "Resolved, and it is not a live defect" passage
explicitly narrates its own asserted-to-provisional-to-confirmed history
inline, dated, and the R8-arbitration audit own findings (committed
05eaa01b29, 2026-07-26 11:57:25, before the ADR confirmation passage) read
as an earlier, consistent stage of the same progression rather than as a
contradiction of it.

### a-withdrawal-landed-during-this-sweep-and-has-not-yet-propagated-to-the-exec-record-it-corrects | critical | caught live: this is the exact failure mode the dispatch named, observed in real time rather than reconstructed after the fact

While this sweep was in progress, commit d05f8f100c (2026-07-27 09:45:48,
"withdraw exactly seven and the last incoherence") landed on top of the ADR,
correcting two overstatements in the decl.ejercicio coherence measurement:
the "281 targets, exactly seven disagree, the other 274 are coherent"
figure silently baked in an unstated year-versus-integer discrimination, and
the naive rule (value_kind against data_type, nothing else) actually
surfaces four different rows (decl.event-kind, decl.tipo-ejercicio twice,
decl.tipo-declaracion, all enum over text or integer), tracked fresh as
P04.S28. The commit also withdraws the stronger claim that the ejercicio
fix closed "the last incoherence in the estate," naming that as a
completeness claim the count did not support.

The ADR itself carries this correction inline, dated, in the established
pattern this campaign uses elsewhere. But P04-S15 own exec record, the
document that originated the "exactly seven... the other 274 are coherent"
language verbatim, was not touched by this commit and still states it
as flat, undated fact with no correction. This is confirmed by direct
re-read at the moment of writing: the exec record own text is unchanged
since 2026-07-26. So the corpus right now, at HEAD, contains the withdrawn
figure in the exec record and the corrected figure in the ADR, disagreeing
with each other on the same measurement, and nothing points a reader from
one to the other.

## Recommendations

Add a one-line "superseded" note to the negative-result audit
(form-number-sourcing-negative-result-audit) pointing at P04-S15 exec
record, since it is the one document in this sweep whose headline claim is
flatly false at HEAD and which nothing else references or corrects.

Update the form-number-grounding-and-two-decisions-audit Recommendations-
section sentence about the docstring, or add a brief note, since the fix
that landed nine minutes later took a different shape (remove the
per-modelo enumeration) than the one recommended (state a third, corrected
reason).

Add a short "resolved" cross-reference from the campaign-close honesty
review to the documents that closed each of its findings (P04.S15 through
P04.S18, the corrected P02.S09 row, P01-S03, the R12 partition audit), or
mark the review itself as historical, so a future reader does not need to
compare six commit timestamps by hand to learn which of its findings are
still open. Only the P04.S18 item (see finding above) is arguably still
open in substance.

Decide, rather than leave implicit in a checked checkbox, whether P04.S18
classify-and-defer outcome satisfies the Step as written or whether the
wire-versus-delete question should be reopened as its own Step -- this is
named as the one place in the sweep where ambiguous is the honest answer
rather than stale.

Write the missing P04-S24 exec record; the underlying fix is real and
verified independently against the registry, so this is a pure paperwork
gap rather than a substantive one.

State explicitly, in whichever document is authoritative, whether "manifest
fidelity" names the Modelo 111 six-vs-five gap the honesty review
reconstructed, the Modelo 100 124-vs-70 gap P01-S03 and the later
manifest-reconciliation-gap audit both name with the identical phrase, or
both under one umbrella term -- the corpus currently answers the question
twice, correctly, and differently.

Sweep P04-S15 own exec record for the withdrawn "exactly seven / 274 coherent" figure and update it to match the ADR own 2026-07-27 correction, or add a pointer to it -- this is the one instance in the sweep where a withdrawal landed and its origin document had not yet been touched.
