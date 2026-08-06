---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:5500345013e1cf5ea5911411a93c4e2548a8e6e21713d90bdde9a9f02d9bec58'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` audit: `what a fresh reader would find missing, vague, or unverified`

Written as if I had just inherited this campaign, at the driving agent's request, because the
governing rule requires the review before completion is declared and bars the driving agent
from being its author.

**Headline: the campaign is not at 50 of 53. The plan says 13 of 27.** Everything below
follows from taking the plan seriously as the durable artefact, which is what the closure rule
makes it.

## F1 — The task list has drifted a long way ahead of the plan

    plan:       13 checked, 14 unchecked
    task list:  50 of 53 reported done

The plan is the artefact `plan-closure-requires-exec-records` governs and the one a later
reader inherits; the task list is session state. A reader of the task list sees a campaign
essentially finished. A reader of the plan sees one about half done. Both are current, and
they disagree by roughly twenty rows.

Some of the gap is legitimate — several task-list entries are follow-ups born today that were
never plan rows. But not all of it is, and the specific divergences below are not bookkeeping.

## F2 — Task #26 is closed and its deliverable does not exist

`P04.S24` asks for a confirmation from the localization cascade owner. Task #26 is marked
completed. Searched at HEAD: no ADR, audit, commit message or code comment records the
owner's verdict, and the only commit naming the confirmation is the exec record stating it is
unevidenced.

**This is the fourth mis-closure of the campaign and the first with no downstream consumer to
catch it.** The other three were found by the agent doing the next piece of work. Nobody is
doing a next piece of work on a confirmation, which is exactly why it survived. A row whose
deliverable is an agreement has no artefact to trip over, so it fails silently by
construction.

Note the shape rather than the instance: **rows that deliver a decision or an agreement are
structurally harder to close honestly than rows that deliver code**, and this campaign has
several of them.

## F3 — "Blocked" is doing work it has not earned on #9

Task #9 is recorded as blocked. It is not blocked; it is unverified.

The single failure that justified holding it —
`test_modelo_project_m130_to_m100_full_year_aggregation` — **now passes**, fixed by #49:

    uv run --no-sync pytest <that test> -m integration -n 0
    1 passed in 36.22s

So nothing is blocking #9. What it needs is a re-run of the entrypoints CLI integration lane
to confirm the whole module set is green, which takes about ten minutes and which nobody has
scheduled. "Blocked" and "needs a ten-minute run nobody has started" are different states, and
only one of them is somebody's turn.

## F4 — `P02.S07` is closeable now and my own refusal is the thing keeping it open

I refused to check this row earlier because the reshape had not landed. It has since landed
(#47), and I verified it: the schema is 15896 against an 18000 budget, definitions 11533
against the ~13300 real allowance. The refusal was correct when made and is now stale.

Recorded against myself because it is the same failure mode this review exists to catch — a
judgement that was right at the time, left standing after its premise changed.

## F5 — #44's number is provisional in a way its subject does not say

Task #44 reads "Dev-tooling lane: 26 down to 6, and the residual is entirely #50". The
measurement was taken against a working tree carrying **157 modified or staged paths**, most
of them peer work.

`P02.S08` exists precisely to demand this measurement at a clean HEAD, and it is unchecked.
So the campaign simultaneously holds an open row saying "this number is contaminated, measure
it clean" and a closed task reporting the number as a lane verdict. The count may well be
right; what is missing is the entitlement to state it without the qualifier.

This is the fifth over-confident declaration the driving agent asked me to assume existed.

## F6 — `P04.S17` is accurate about itself and scopes 15% of its own problem

The row names 204 semantic-dedup exec records that closed Steps with empty Outcome sections.
Measured: exactly 204 in that feature. The row is precisely right.

But the identical defect, measured the same way across the whole exec tree:

    993  2026-06-09-docstring-google-style
    204  2026-06-13-semantic-dedup-epic
     47  2026-05-16-profile-lifecycle-cli
     34  2026-05-28-centralized-output-redaction
     11  2026-05-31-emit-envelope-schema-burndown
          ... 15 features affected, ~1321 records total

**A campaign with 993 instances of the same defect has no row anywhere.** Closing S17 as
written would resolve 204 of roughly 1321 and leave the plan reading as though the problem
were handled.

Excluded deliberately from that count: 1776 further records carry no Outcome section at all,
which is an older template rather than an unfilled one. Counting them would have inflated the
finding by more than the finding.

## F7 — Three plan rows have no task-list representation at all

`P03.S19` (state the filing-period validator's reduced coverage in its own docstring),
`P04.S16` (re-pin the model-facing description digest once description sources settle), and
`P04.S17` appear in the plan and nowhere in the task list.

That is the mechanism behind F1 rather than a separate problem: the task list can report
near-completion precisely because work exists that it does not model. Anyone closing the
campaign from the task list would close it over three unmentioned rows.

## F8 — `#15` and `P01.S05` now disagree about what the question is

The task is marked MOOT because a peer's snapshot pushed the branch. The plan row still asks
whether to push it. Both are true statements about different moments, and the row has not
been reworded, so the plan asks a question reality already answered — the same drift I
corrected on `P02.S07`, in a row nobody has revisited.

## Disposition

None of this says the work is bad. The campaign landed a large amount of verified change and
its records are, on the whole, unusually careful — four self-corrections in one day is a high
rate of catching one's own errors, not a low one.

What it says is that **the campaign is not structurally complete and should not be declared
so**: one closed task has no deliverable, one blocked task is not blocked, one refused row is
now closeable, one reported number is not entitled to its confidence, and three rows are
invisible to the list being used to judge completion.

The rule's own premise is that a driving agent reports complete while a fraction is
structurally incomplete. That premise held here, and the fraction is larger than the task
list suggests — not because anyone overstated deliberately, but because the two records of
the campaign drifted and only one of them is being read.

## F9 - The rest of the blocked set, checked one at a time

The driving agent asked whether "blocked" is honest across #9, #13, #14, #10, #11 and #53.
Answered per row rather than in aggregate, because the aggregate answer hides the one that
differs.

- **#9 - NOT blocked.** Covered in F3. Unverified, not blocked.
- **#13 and #14 - honestly blocked.** Both flip a guard off once the step it guards is seen
  green on a runner, and no runner execution has occurred. The precondition is real, external
  and unmet.
- **#10 - honestly blocked**, on the same runner execution, transitively via #11.
- **#53 - honestly blocked.** A working-tree-only scrub awaiting the same index lock.
- **#11 - NOT blocked. Deferred, and the distinction is load-bearing.** Its precondition was
  an unpushed branch; the branch is now pushed, one commit ahead of origin. Nothing prevents
  dispatching it.

  But dispatching it now would produce a verdict about a tree nobody is working on: 161 files
  are uncommitted, so origin/main is missing essentially all of today. A green result would be
  green about the wrong thing, which is the false-green shape this campaign has spent the day
  removing.

  **So #11 is correctly not-yet-run for a good reason, and "blocked" is the wrong word for
  it.** Blocked says someone else must act. Deferred says we chose, and names the condition.
  Here the condition is "after the tree lands", and stating it that way makes visible that the
  lock is what gates the CI verdict - which "blocked on a runner" conceals.

## F10 - On whether escalating the lock repeatedly has been proportionate

The driving agent asked this about their own conduct, which deserves a direct answer.

**Escalating was right.** Only the operator can safely clear a lock, every destructive route
is categorically barred, and the cost is real and compounding: 161 uncommitted files in a tree
whose standing directive is that uncommitted work is unrecoverable.

**Two qualifications.** A route did exist and was used - the temp-index path landed two
commits successfully. So the honest statement is not "blocked with no alternative" but
"blocked for bulk, with a narrow route available for individual urgent items, used twice and
leaving a staging trap both times". The route is real and it has a known cost; both halves
belong in the escalation.

**And repetition is not escalation.** The same request, to the same recipient, at the same
urgency, after 52 minutes of no movement, is repetition. What changed over that period is the
category: from a delay costing latency, to an accumulation of unrecoverable risk that now also
holds a trap armed against a branch that pushes. That is a different message, and it is worth
sending once in those terms rather than re-sending the first one.

Not a criticism of judgement - the decision to escalate rather than force was correct every
time, and forcing would have been the serious error. It is an observation about form: when the
facts change category, say that the category changed.

## F11 - Correcting F3: my own evidence was a working-tree run reported as a HEAD claim

F3 concluded that #9 is "not blocked, just unverified", on the strength of:

    pytest test_modelo_project_m130_to_m100_full_year_aggregation -m integration -n 0
    1 passed in 36.22s

**That run does not support the claim I hung on it.** It was executed against a working tree
carrying 161 uncommitted files, including production modules under
`application/calculations/` and `domain/calculations/registry/` that the test exercises. So
the pass is a statement about the working tree. It is not evidence about HEAD, and I presented
it as though it were.

The driving agent caught this and the general mechanism is theirs: a local pass can be a
peer's uncommitted fix masking a committed red. They demonstrated the shape deterministically
on a different surface - `test_ledger_validation_paths.py`, which carries 48 uncommitted
insertions against an emitter that matches HEAD, so what the test asserts and what production
emits diverge at HEAD while agreeing locally.

**What survives of F3 and what does not.**

- **Survives:** "blocked" is the wrong word for #9, and the blocked-versus-unverified
  distinction is real and worth keeping.
- **Does not survive:** the specific claim that the blocking failure now passes at HEAD, and
  the estimate that #9 needs only a ten-minute re-run. If the local green rests on
  uncommitted production, #9 needs the COMMIT, not a re-run - a third state neither word
  covers.
- **Undetermined:** whether the test I ran is itself masked. Its own file matches HEAD on both
  the test and its nearest emitter, but uncommitted production exists in the path it
  exercises, and I have not run it against HEAD content. I am recording that as open rather
  than resolving it in my own favour.

**This is the third instance today of the same error in my own work**, and the repetition is
the point rather than the individual mistakes: measuring the working tree and reporting the
result as a property of HEAD. The step-check attribution was this. The `git diff` after my own
mutation was this. This is this. Each time the instrument was correct and the question it
answered was one step off the question asked.

**The generalisable form, since three instances is enough to state it as a rule:** in a
worktree with peer WIP, no local test result is evidence about HEAD unless every file the test
transitively exercises is confirmed clean. That is a much stronger precondition than checking
the test file, and it is usually easier to satisfy by running against a clean checkout than by
enumerating the closure.

## F12 - F11's precondition is currently unsatisfiable, so essentially no local green today is evidence about HEAD

F11 states the rule: a local test result is evidence about HEAD only if every file the test
transitively exercises is confirmed clean. The driving agent measured what that costs in this
tree, and I re-measured it independently:

    dirty PRODUCTION (non-test) modules under src/cadrumo :  38

    domain/calculations/registry  6     entrypoints/cli   2
    application/aggregation       6     domain/iva        2
    application/invoices          3     application/auth  2
    application/calculations      3     entrypoints/mcp   1
    domain/renta                  1     locales           1     ... and core

`core`, `registry`, `aggregation`, `calculations`, `mcp` and `cli` are all dirty
simultaneously. **There is essentially no meaningful test path in this repository that does
not transitively exercise at least one uncommitted production module.** The precondition F11
names is therefore not merely demanding right now - it is unsatisfiable for practically any
test.

**The consequence is wholesale rather than per-row.** Every green reported today from a local
run - mine, the driving agent's, every peer's - is a statement about a working tree that no
commit describes, and none of them is entitled to the word "verified" in the sense the
campaign's gates use it. That is not an accusation of carelessness. Every one of those runs
was executed correctly and reported honestly; the tree moved out from under the meaning of
the result.

**What this does NOT say:** that the greens are wrong. Most are probably right, because most
uncommitted changes are unrelated to most tests. It says they are *unestablished*, which is a
different claim and the only one the evidence supports.

**What follows for the campaign's gates.** Any verification gate in this campaign phrased as
"run X and quote the result" is currently satisfiable without establishing anything - which
includes #57 as I wrote it, and I have said so rather than leaving it collectible. The gates
that survive are the ones that do not depend on execution: string containment between an
assertion and its emitter at HEAD, structural checks on committed content, and diffs against
pinned SHAs. Those remain sound because they read committed bytes rather than running a tree.

**The honest disposition, stated plainly:** the campaign cannot be declared verified until the
tree is committed, and the tree cannot be committed until the lock clears. So the lock is not
merely delaying the campaign's completion - it is the reason the campaign's completeness
cannot currently be assessed at all. That belongs in the operator's picture as a property of
the situation rather than as a caveat on individual rows.

## A note on instrument traps, since a third recurrence is the same shape as F11

Three times in this session I invoked `rg -rn` intending "recursive, line numbers". In ripgrep
`-r` is `--replace`, so the flag cluster silently rewrites every match to the literal `n`. It
produced `_OUTPUT_SCHEMA_BUDGET_CHARS = n` and a source line reading `"taxable_base + iva_amount
+ n the gross to the cent"`, both of which I caught only because the output was absurd.

**Catching a silent-corruption trap by noticing the output looks wrong is not a control**, and
it fails precisely when the corrupted output happens to look plausible. The control is to
avoid short-flag clusters with `rg` entirely and pass `--fixed-strings` and `-n` explicitly.

Recorded here rather than only in a personal note because it is the same lesson the rest of
this audit applies to the campaign: **when the same failure recurs three times, the recurrence
is the finding and the individual instances are not.** The same reasoning that promoted F11
from three working-tree-versus-HEAD mistakes applies to three flag-cluster corruptions, and it
would be inconsistent to draw the rule for the campaign's errors and not for my own tooling.

## F13 - The per-feature table: the scaffold signature is uniform, so filling is unavailable almost everywhere

F6 reported ~1321 empty-Outcome records across 15 features and left open whether they were one
defect or several. Measured per feature, with the signature established on the semantic-dedup
204 - single scaffold date, single creating commit, narrative sections wholly empty:

    feature                                    recs  empty  narr  dates  1 commit   plan
    docstring-google-style                      994    993   993      1      yes  994/994
    semantic-dedup-epic                         239    204   204      1      yes  239/239
    profile-lifecycle-cli                        64     47    47      1      yes    64/64
    centralized-output-redaction                 82     34    34      1      yes    82/82
    declaracion-extraction-architecture         128     15    15      1     no(2) 218/218
    emit-envelope-schema-burndown                24     11    11      1      yes  208/208
    bindings-interface-hardening                 32     10    10      1      yes    33/33
    live-justificante-reconcile                  14      8     8      1      yes    14/14
    codebase-solidification                     418      3     3      2     no(2) 690/690
    auth-cert-recovery-custody                   56      3     3      1      yes    56/56
    ledger-invoice-decomposition                 57      3     3      1      yes    57/59
    user-docs-search-consolidation               33      2     0      1      yes    23/33
    ... 6 further features with 1 each

    TOTAL  1340 empty-Outcome, of which 1338 empty-narrative

**Corrected count.** F6 said ~1321; the exact figure is **1340**, and the earlier number was an
approximation from a coarser grouping. Stated because a later reader comparing the two should
know which is measured.

**The signature is uniform.** Every feature's empty records share a single scaffold date, and
all but three resolve to a single creating commit. This is not fifteen separate lapses; it is
one mechanism recurring - exec records generated in bulk after their Steps were already
checked, so that each checked Step had a file to point at.

**And the decisive column is `narr`: 1338 of 1340 are wholly empty**, carrying no Description,
no Outcome and no Notes. So the question F6 left open resolves against the hopeful answer:
**there is almost no population of ordinary partially-filled records where filling is
genuinely possible.** Reconstruction is unavailable tree-wide for the same reasons established
on the 204 - the date is the scaffold date, the paths are shared, and an empty body carries no
symbol to trace.

**The two exceptions are the only genuinely fillable records in the tree.**
`user-docs-search-consolidation` has 2 empty-Outcome records whose Description and Notes ARE
populated. Those are ordinary unfinished records, their authors are identifiable, and they are
worth filling. Two, out of 1340.

> **CHALLENGED AND UPHELD, 2026-08-06.** The campaign lead ran an independent tree-wide sweep
> that reported **56** fillable records across four features absent from the table above, and
> appended a correction here asserting the finding was inverted. **That challenge was wrong and
> is withdrawn. The figures above stand unchanged.**
>
> The defect was in the challenger's section extractor. It located a section by its `##`
> heading and terminated it at the next match of `^##+\s` — **which also matches `###`.** Any
> `## Outcome` whose content is organised under `###` subheadings was therefore truncated to
> zero characters and scored as empty. Worked example:
> `2026-07-27-conformance-cli-P03-S16.md` carries `## Outcome` at line 33 followed by
> `### Ruling: this CLI may not write operator_reviewed, deliberately` at line 35 — a
> substantial authored outcome, read as absent.
>
> Both predicates run over the same corpus settle it:
>
>     terminator ^##+\s  (matches ###)   ->  1386 empty-Outcome,  56 "fillable"
>     terminator ^##(?!#)\s (same level) ->  1321 empty-Outcome,   2 fillable
>
> The corrected sweep reproduces this table's conclusion independently, and locates both
> fillable records in `user-docs-search-consolidation` exactly as stated. All 56 were false
> positives of the challenger's own making, concentrated — as the artefact predicts — in the
> features whose authors used subheadings.
>
> **Recorded rather than deleted, because the near-miss is the finding.** A correction asserting
> an inverted conclusion was one commit from entering this record, and it would have been more
> damaging than the error it claimed to fix: it would have licensed four campaigns to hunt
> records that do not exist. What stopped it was the author of the challenged table refusing to
> amend on an unreproduced number and asking for a single filename instead — the cheapest
> possible request, and the one that made the predicate difference visible in one step.

**What this table is for.** It is deliberately not a remediation plan. Per-feature counts let
each owning campaign see its own share and decide what that share warrants; a single
tree-wide number invites either a mass rewrite nobody should perform or the shrug that has
kept this invisible. `2026-06-13-semantic-dedup-epic` and `2026-06-09-docstring-google-style`
each carry their own provenance audit; the remainder are now visible here rather than nowhere.

**The exclusion, restated because the natural failure mode is an upward correction.** A further
1776 records carry no `## Outcome` section at all. That is an older template rather than an
unfilled one and is NOT part of this finding. Anyone re-measuring will encounter 1776 + 1340
and must not report ~3100.

**The one structural remedy, noted rather than proposed:** a gate refusing to check a Step
whose exec record has an empty Outcome would have prevented every row in this table. That is
the harness owner's decision.
