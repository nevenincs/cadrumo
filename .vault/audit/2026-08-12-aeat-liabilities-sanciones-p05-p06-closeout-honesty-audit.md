---
tags:
  - '#audit'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:e6e9be3b3dbf9f7e0a3cfa986cdae0042c43accdc54b9c9e7586fca415c11fd0'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
  - "[[2026-08-07-aeat-liabilities-sanciones-adr]]"
  - "[[2026-08-07-aeat-liabilities-sanciones-research]]"
---

# `aeat-liabilities-sanciones` audit: closeout honesty review after the live discovery session

## Context

Written as the campaign-close honesty review this project mandates before any
claim of structural completeness, against a session that ran an authenticated
Cl@ve Móvil discovery session, closed P05.S15, and closed all four P06 rows.
The plan stands at 18 of 23 Steps.

The review is deliberately adversarial about its own session's work, because
the standing failure mode here is a closeout that reads as green while the
goal is untouched.

## What the goal asks, and what it still does not have

The standing goal is that an operator can see, inside the application, what
AEAT currently reports as owed.

**An operator still cannot.** There is no `walk_deudas_consulta`, no `pull`
verb, no write-guard enrollment and no harness entry. The three read verbs
shipped in P04 return zero rows and will keep doing so. Everything closed this
session hardened the wall around a read that nothing performs.

That is worth stating flatly because the numbers invite the opposite reading:
78 per cent of Steps closed, every gate green, two phases advanced. None of it
moved the goal. P05.S15 moved the guard from refusing every landing to refusing
every landing except one endpoint no code navigates to. P06 grounded provisions
the register does not yet interpret and may never need if it only ever displays
AEAT's reported figures — which is what the governing ADR says it does.

## FINDING-1: the P05 remainder is blocked on absent DATA, not absent access

**Pathway:** live discovery → `adapters/outbound/aeat/sede/_deudas.py`

The plan said P05 was blocked on an operator-authorised specimen capture. Access
was obtained: the authenticated session reached the consulta, the query was
accepted, and the surface was decomposed. What was NOT obtained is a populated
listing.

**WITHDRAWN, and the withdrawal is the finding.** This section originally
concluded that the taxpayer has no outstanding deudas, and presented that as
established rather than assumed on the strength of a negative control: a
syntactically invalid NIF drew AEAT's retrieval error while the valid query
re-rendered the form byte-identically apart from the clock.

That control does not support the conclusion drawn from it. It proves the form
PROCESSES a submission. It does not distinguish "this taxpayer has no debts"
from "the listing does not render for another reason" — an error path can work
perfectly while the results path is gated. Two hypotheses were consistent with
the evidence and only one was reported.

The missed evidence was on the captured page the whole time. Both the consulta
form and its result carry an AEAT banner reading *"tiene notificaciones
pendientes. Antes de continuar acceda al enlace: Consultar notificaciones
pendientes"* — before continuing, access the link. That is AEAT instructing the
user to clear a gate before proceeding, and it was read as page furniture and
excluded from the analysis.

The operator subsequently stated that there are many late filings and many
messages clearly setting out the debts, penalties and legal recourse. That is
direct evidence against the withdrawn conclusion.

**Current honest position.** At least three readings remain open and the
evidence gathered does not choose between them:

1. The consulta listing is gated behind the pending-notifications banner.
2. The liabilities exist but sit at notification stage — a liquidación or
   sanción served but not yet an enforceable deuda in the recaudación register.
3. The debts are in the register and the query needs something the probe did
   not supply.

**Remediation:** S13, S14, S16, S17 and S18 remain deferred, but the recorded
REASON is corrected from "no debts exist" to "the listing was not reached, and
why is not yet established". The distinction matters: the first reason says the
work is unschedulable, the second says it is unfinished investigation. This is
the second one.

**A hard constraint on the next attempt.** The obvious way to test hypothesis 1
— following AEAT's instruction and accessing the pending notifications — is NOT
available to an agent acting alone. Accessing an electronic notification is an
act with legal effect: it is the moment the notification is deemed served, which
starts the appeal and payment clocks. For a taxpayer with late filings and
pending penalties that is a consequential, irreversible act on the operator's
legal position, and it is categorically outside the read-only posture this
project holds toward AEAT. The notifications LIST surface is different and is
safe — the shipped reader is documented as never telling AEAT a notification was
read — and that is the only side of this that may be exercised without an
explicit operator decision.

### Re-established, this time with a discriminating control

The withdrawal above was right to withdraw. A second authenticated session then
supplied the control the first attempt lacked, and the original conclusion is
re-established on much stronger evidence than it originally had.

**The control.** Within ONE session, two authenticated read surfaces were driven
back to back. AEAT's notifications summary rendered three populated tables. The
deudas consulta, queried immediately afterwards, rendered no table at all and
returned the form byte-for-byte apart from the clock.

That separates the hypotheses the first attempt could not. A session that
renders content elsewhere is authenticated, un-gated and capable of returning
rows, so the empty consulta is not a session artefact, not an authentication
artefact, and not a generic gate. The pending-notifications banner was also
tested directly rather than reasoned about: the notifications summary was
visited — which is what AEAT's "antes de continuar acceda al enlace" asks for —
and the consulta was re-queried afterwards, returning the identical empty form.
So the banner is not gating the listing either.

**Conclusion, now supported.** Hypothesis 2 of the three listed above is the
live one: the operator's liabilities exist at NOTIFICATION stage — liquidaciones,
sanciones, providencias served as messages — and are not present in the
recaudación register the *Consultar deudas* surface reads. Those are different
AEAT registers at different procedural stages, and the operator's statement that
the debts and penalties are "clearly indicated in the messages" is consistent
with exactly that, not in conflict with it.

**What this does NOT license.** It does not license inventing the row DOM. The
register is empty for this taxpayer today, so S13 and S14 still have nothing to
observe, and the deferral stands on evidence rather than on the unsupported
reasoning that was withdrawn.

**Method note worth keeping.** The first pass reached the right answer by the
wrong route and would have been indistinguishable from a wrong answer. What
fixed it was not more care with the same probe but a SECOND surface driven in
the same session as a positive control. When a read returns nothing, prove the
reader can return something before concluding the thing is absent.

## FINDING-2: the specimen established more than S15 consumed, and the surplus is unrecorded in code

**Pathway:** live discovery → nothing

Three observations were made that no shipped code carries, because the code
that would carry them is exactly the blocked work:

- The surface is served as **ISO-8859-15**. Decoding as UTF-8 raises outright;
  decoding as Latin-1 silently mangles the euro sign, which is the column the
  listing exists to report.
- The consulta is **two-step**: the endpoint renders a NIF form and the listing
  exists only behind its submission.
- A retrieval failure surfaces as an error line naming the NIF in the avisos
  region, not as an HTTP status.

The two-step finding did reach code, as the scoped `allowed_read_post_paths`
entry. The charset and the error shape reached only the S15 execution record.

**Remediation:** accepted as recorded-not-implemented, because the consuming
function is blocked. The execution record is the durable home; a future S14
author who does not read it will decode the page wrong. Flagged rather than
fixed, since inventing a walker to hold the charset would be the defect above.

## FINDING-3: S15 did not land as one atomic commit

**Pathway:** shared worktree → git history

One Step is meant to be one commit. S15's five files landed across several
peer commits: a merge was in flight in the shared worktree while the work sat
uncommitted, and the files were swept in — two under a peer message describing
the unnumbered-host fix, three absorbed into the merge commit itself.

Content survived intact and is green at HEAD. Nothing was lost. But the history
does not record this Step as a unit, and a later reader reconstructing why the
allow-list names an endpoint rather than a prefix will not find it in one place.

**Remediation:** not repairable without rewriting shared history, which is
forbidden. Recorded here as the durable account. The operational lesson — check
`.git/MERGE_HEAD` before any commit sequence, because during a merge a bare
commit completes the PEER'S merge commit rather than merely over-staging, and
`git commit -- <pathspec>` is refused outright — is a real gap in the standing
worktree-safety rule, which warns about the index but not about this case.

## FINDING-4: P06 delivered 18 entries where the plan wrote 4, and the rows could not have been met as written

**Pathway:** `registry/aeat/legal/` → `_legal.py` anchor resolution

Rows S20 and S22 each asked for "the legal-catalogue entry" for an article
range. A `corpus_ref` resolves exactly one anchored unit, so a range is not
representable as one entry. S20 became seven entries and S22 eight.

This is a plan-authoring defect rather than a scope increase: the row as
written described an artefact the schema cannot hold. Closing it "as specified"
would have meant one entry silently covering one article while its heading
claimed a range.

**Remediation:** delivered as 18 entries, one per anchor. No follow-up owed.

## FINDING-5: the stamp rests on operator authorisation, and the review has one real limitation

**Pathway:** `registry/aeat/legal/*.toml` → `LegalReference`

The catalogue schema has **no draft state**. `review_status` is a literal
`reviewed` with `reviewed_at` and `reviewed_by` both required, so an unstamped
entry cannot exist in the tree: landing an entry and stamping it are one action.
The plan's "author but do not stamp" instruction was not executable.

The operator ruled explicitly, naming themselves the reviewer and authorising
the cross-check to be carried out by a dispatched review agent. The cross-check
ran — 45 numeric clauses, zero disagreements, every article complete — and its
bundled-side claims were then independently re-verified before stamping,
including the check that the superseded art. 188 reduction figures are absent
from the corpus.

**AMENDED after a second-channel pass.** This finding originally recorded that
only art. 28 had two independent live channels and the other seventeen rested
on one. That is no longer true and the claim has been corrected everywhere it
was shipped.

A second channel was obtained: the ORIGINAL 2003 BOE diario publication plus
the original publications of each modifying norm. Its independence is
demonstrated rather than asserted — the 2003 original lacks the apartados added
to arts. 28 and 170 in 2012, which the consolidated text carries, so it cannot
be the same document re-served. Thirteen of the seventeen articles have never
been amended, so for them the 2003 original IS the current text. 31 figures
checked on the second channel, 31 AGREE, zero disagreements. Every
figure-bearing article among the seventeen falls in the unamended set.

Art. 188's reductions — load-bearing for every sancionador entry, since they
move the nominal band to what is actually paid — gained a second channel too,
against Ley 11/2021's own original publication.

**What two channels did NOT buy, and this is the honest residual.** The channels
agree on what text was ENACTED. They do not independently agree that nothing
later changed it: the claim that the amendment history is exhausted still rests
on the consolidated database's own version list. For the unamended articles the
gap is small — a later amendment would have to be invisible to BOE's own
consolidation — but it is not zero.

An AEAT restatement was sought as a third channel for the sanction bands and
NOT obtained; the published recargos material covers art. 27 only. The reviewer
recorded this as unobtained rather than counting a search-engine paraphrase,
which is the right call.

**Remediation:** the corrected two-channel statement and its residual limitation
now sit in each catalogue file's header, replacing the superseded one, so what
travels with the data is accurate. No further channel work is owed before a
consumer merely CITES these entries.

## FINDING-6: unrelated red gates on the shared tree, triaged to peers

**Pathway:** full-tree gates

A broader run showed failures in the declarations adapter tests, one AEAT
route-literal centralisation gate, and three registry tests around M100
art. 85, record-design completeness and occupancy directions.

Each was triaged rather than assumed. The declarations files were in the peer
merge's own conflict set. None of the route-literal offenders is in a file this
session touched — the two apparent hits in the deudas guard test are docstrings,
which the real gate excludes. The three registry failures were confirmed
pre-existing by holding this session's four new catalogue files aside and
observing identical failures.

**Remediation:** none owed by this campaign. Recorded so a later closeout does
not inherit them as unexplained.

## Verdict

### FINDING-7 (OUT OF SCOPE, needs an owner): the notifications reader silently reports zero against a populated surface

**Pathway:** `adapters/outbound/aeat/sede/_notifications.py` →
`aeat app live notifications pull`

Found while establishing the control for FINDING-1, and reported rather than
absorbed because it belongs to the notifications feature, not this plan.

`aeat app live notifications pull` completed successfully against a live
authenticated session and persisted a snapshot with `row_count 0`. The AEAT
summary surface it reads, fetched directly in the same session, carries THREE
tables each with one populated data row. AEAT's own banner states the taxpayer
has pending notifications.

So the verb reports an empty inbox while the surface behind it is populated. It
does not fail, warn, or refuse — it returns a clean zero.

The likely cause is a stale parse. The module docstring records the summary as
"two tables keyed by número de certificado"; the surface now renders three, and
the header sets differ between them (the first carries `Destinatario` where the
other two carry `Concepto`). A parser keyed to the two-table shape would find
nothing to bind.

**Why this matters beyond a missing feature.** This is the exact shape the
`no-silent-under-declaration` rule exists to prevent, on a surface where the
missing rows are AEAT telling the taxpayer about liabilities and deadlines. An
operator reading `row_count 0` would conclude they have no pending
notifications. For a taxpayer with late filings and served penalties, that
reading is not merely unhelpful, it is dangerous — electronic notifications are
deemed served after ten days whether or not anyone looked.

**Remediation, owed by the notifications feature:** re-capture the summary and
query surfaces, repair the parse against the current three-table layout, and add
a regression that fails when a populated surface yields zero rows. A reader that
cannot distinguish "empty inbox" from "parse found nothing" should refuse rather
than return zero. **Not fixed here:** it is outside this plan's scope, and the
campaign rule against opportunistically editing another campaign's surface
applies.

### FINDING-7, CORRECTED AND FIXED

The finding above blamed the summary parser and a "two tables where AEAT now
renders three" layout drift. **That diagnosis was wrong.** Driving the real
parser against the live summary returns three rows, correctly classified across
all three headings. Nothing is wrong with the summary parse or its table count.

The defect was real but in a different place. `notifications pull` does not read
the summary at all — it reads the QUERY surface through
`fetch_notifications_query`. There, AEAT labels the date columns without the
article: "Fecha emisión" and "Fecha notificación", where the summary says
"Fecha de emisión". The column indexer matched only the "de" spelling.

What made it silent rather than merely lossy: `_row_from_cells` treats an
unresolvable `fecha_emision` as an unclassifiable row and returns `None`. So an
unindexed column did not empty a field, it dropped every row. The verb returned
a clean zero with no error, no warning and no partial row.

The bundled query fixture still carries the "de" spelling and a `Leída` column
the live surface no longer serves. That is why the suite stayed green while
production returned nothing — the fixture had drifted from the sede, and the
tests were measuring the fixture.

**Fixed.** The indexer now keys on the article-free stems so both spellings
resolve; `modo` keeps its column because it is matched ahead of the date branch,
and that ordering is now pinned by a test, since "Modo notificación" shares the
stem the date branch keys on. Verified live: the same account returns 1 row
after the change and returned 0 before it. The regression pins the labels
directly rather than through the drifted fixture, and an anti-tautology case
proves a genuinely unindexable header still drops the row, so the new cases
cannot pass with the indexer removed. Mutation-proved from outside the repo:
narrowing the matcher back reds the regression.

**Still open, and smaller than it looks.** The summary lists three unread items
— one notification pending notificación, one already notificada, one
comunicación — while the query surface's default search returns one. So the
captured snapshot is complete for what the query surface serves but is not the
whole unread inbox. Whether the query default is date-bounded or state-bounded
was not established. That is a coverage question on the notifications feature,
not a silent-zero, and it is left to that feature's owner with this note as the
handoff.

**Method note.** This entry was wrong once before being right. The first
diagnosis was inferred from a table count without ever driving the parser; the
second drove the real parser against both live surfaces and isolated the column.
Inference about why a parser returned nothing is worth very little next to
running it.

### FINDING-7 residual, now closed

The correction above left one item open: the summary listed three unread items
while the query surface's default search returned one, and whether that default
was date-bounded or state-bounded was not established.

It was date-bounded. AEAT's notifications search defaults `fecha desde` to one
month before today, and the reader sent no range — so it was asking "what
arrived this month" and reporting the answer as the register. Reading the form's
own field defaults showed the window directly rather than inferring it.

The reader now states its window: a configured lookback from today, with both
the tipo-consulta and leida filters set to Todos so neither axis narrows the
result. Verified live — `row_count` 1 to 10, and all three unread items the
summary lists are present in the ten, confirmed by counting rows whose `leida`
is not true.

The filters go as GET parameters. The form declares `method="post"`, but the
servlet honours the same fields on a query string, so the reader stays a pure
navigation and needed no read-POST allowance added to its guard policy — a
narrower change than the deudas surface required.

Taken with the column fix, this notifications reader has now failed twice in the
same direction: once returning zero rows and once returning a tenth of them,
both silently, both because the surface answered a question narrower than the
one intended. Neither failure raised anything. A reader over a register whose
contents carry legal deadlines should treat an implausibly small result as
suspect rather than as an answer; that is a design note this feature's owner
should weigh, and it is not addressed here.

## Verdict

P06 is complete: 18 grounded entries across four subjects, every figure
confirmed on two independent channels.

P05 is not. S13, S14, S16, S17 and S18 are **deferred carry-forward**, blocked
because the recaudación register holds no rows for this taxpayer — now
established with a positive control rather than asserted. The liabilities are
real and sit at notification stage; they are simply not in the register this
surface reads.

The plan may be recorded as closed on that basis. It must not be recorded as
having delivered its goal: an operator still cannot see what AEAT reports as
owed, and FINDING-7 means they currently cannot see their pending notifications
either.
