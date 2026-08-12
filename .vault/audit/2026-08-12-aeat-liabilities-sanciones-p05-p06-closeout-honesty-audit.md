---
tags:
  - '#audit'
  - '#aeat-liabilities-sanciones'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:064c5e5e28a128ba158721ec93ff062bc88938781b2667fe93de2d6c958dbf0e'
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

The plan said P05 was blocked on an operator-authorised specimen capture. That
framing is now wrong in both directions and the plan Description has been
corrected.

Access was obtained: the authenticated session reached the consulta, the query
was accepted, and the surface was decomposed. What does not exist is a
populated listing — this taxpayer has no outstanding deudas.

**That was established, not assumed.** A syntactically invalid NIF drew AEAT's
retrieval error while the valid query re-rendered the form byte-identically
apart from the clock. The form therefore processes, and the empty result is
real rather than a silent rejection. Recording the method matters: "the query
returned nothing" and "the query was not processed" are indistinguishable
without the negative control, and only one of them means the taxpayer has no
debts.

**Remediation:** S13, S14, S16, S17 and S18 are deferred carry-forward. They
unblock when a listing with rows can be observed — a deuda arising, or a
representation the operator holds over a taxpayer who has one. Neither is
schedulable by this campaign. **None of them may be satisfied by inventing a
row parser or a situación vocabulary**, which is the pressure a nearly-complete
phase creates.

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

**The limitation, stated rather than buried:** only art. 28 was confirmed
through two independent live channels. The other seventeen articles rest on a
single live channel. The review agent reported this itself rather than being
caught at it.

**Remediation:** recorded in each catalogue file's header, so the limitation
travels with the data instead of living in a vault document. A second live
channel is owed before any consumer COMPUTES a figure from these entries rather
than merely citing them. No consumer exists today, so this is not blocking.

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

P06 is complete. P05 is not, and its remaining five Steps are **deferred
carry-forward** under the campaign-close mandate, blocked on data no schedule
controls.

The plan may be recorded as closed on that basis. It must not be recorded as
having delivered its goal.
