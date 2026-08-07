---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:46348c7601dc714649bbe15ef64ef677a685a4cb7433f37a538a39771c44f172'
step_id: 'S118'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Route the structured e-invoice draft through the deterministic findings before returning it, since the exact-reader path returns early and never reaches the sole caller of the arithmetic closure and regime contradiction checks, so a Facturae CII or UBL invoice whose base plus cuota does not equal its total confirms clean and one printing inversion del sujeto pasivo beside a repercutido cuota does too. The regime legend is already read on that path and nothing consumes it. The inversion is the finding: the most machine-readable documents in the corpus get the least checking, because the path chosen for being exact and model-free is the path where no deterministic check runs. Carries a decision about drafts already confirmed past unrun checks rather than silently changing what a re-read says

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add `_deterministic_findings.py`: one list of every check that needs only the
  draft, holding the arithmetic identities and the regime contradiction.
- Rewire the grounded reading path to call that list instead of naming the two
  checks itself.
- Attach the same list to the structured e-invoice draft before it is returned,
  through a function-local import that breaks the same cycle the grounding
  import on that path already breaks.
- Add a reachability suite that drives the real path over the in-repo corpus
  invoice and edited copies of it.

## Outcome

The exactly-read path is checked. Before this, a structured e-invoice returned
straight from its own reader and reached the findings assembly not at all, so
arithmetic closure, rate consistency, breakdown sums and the regime contradiction
were structurally unreachable for it. An invoice whose base plus cuota did not
equal its printed total confirmed clean, and so did one printing a reverse-charge
mention beside a charged cuota -- with the mention already read into the draft
and nothing consuming it.

The routing comment above that early return states the reason without noticing
the consequence, and it is worth preserving why it was persuasive: a structured
document reaches no model, which makes prompt injection categorically impossible
for it. That is true and it is good design. What does not follow is that it needs
no checking. **Being unable to be lied to is a different property from being
right**, and an exactly-read wrong invoice is still a wrong invoice. Those are
questions about the issuer's document rather than about the reader.

**Why the checks moved behind one shared list rather than a second call site.**
Two call sites naming the checks by hand is the same defect one refactor later:
the next check lands on whichever path its author had in mind, and the other
silently keeps confirming clean. One list means adding a check reaches every
reader by construction. The list now has exactly two consumers, which is the
whole of the reading surface.

**Why anchor verification is deliberately NOT in that list, which is the decision
most at risk of being undone by a later reader.** A reader looking at the shared
list will see the transcription-dependent check missing and no reason for it, and
adding it will look like tidying. It must not be added. Anchor verification exists
to check a claimed printed form against an independently produced transcription --
it answers "did the reader that proposed this value tell the truth about what the
page said". A structured record has no transcription and needs none: its values
come from the document's own machine-readable fields rather than from a reader
that might be wrong about the page. Running that check there would be a check that
cannot discriminate, which is worse than an absent one, because it reports a
verdict its evidence cannot support and makes the list look complete while doing
so.

**The decision on drafts already confirmed past unrun checks: no special
handling, deliberately, and not by omission.** Two reasons. The compatibility
regime is pre-release, so there is no released data and a migration path would be
inventing one, which the standing rule forbids. And more importantly a
confirmation record that "answered" checks which never ran is not evidence those
checks passed. Re-reading such a document now surfaces findings, and a re-confirm
blocks until the operator answers them; that is not a regression but the system
telling the truth about that document for the first time.

The corollary is deliberately not encoded here, because it is a fact about
records already on disk rather than about this module: an existing confirmation
record must not be read as attesting the checks this Step turned on. It attests
what ran when it was minted. That was raised at report time rather than left
implicit, and it now has its own row.

## Verification

The reachability suite, against the staged tree object rather than the working
copy, which held other lanes' work:

    uv run --no-sync python -m pytest src/cadrumo/application/ledger/tests/test_structured_path_findings.py -n0 -p no:cacheprovider -q -m unit
    3 passed in 2.60s

Re-run against the committed tree after a later repair commit landed, extracted
with `git archive`:

    3 passed in 3.34s

The coherent corpus invoice comes back clean; a copy with a broken printed total
surfaces the arithmetic closure finding; a copy declaring a reverse-charge
mention beside the document's real cuota surfaces the regime contradiction. Every
case drives the same function the CLI calls, over bytes written through the real
encrypted-bucket evidence service. No draft is constructed and no producer is
called directly -- either would reproduce exactly the gates that were already
green while this path ran nothing. The corpus tree is never written to; each edit
is a copy in a temporary directory, and each edit asserts its target text was
present so a corpus change fails loudly instead of storing an unedited document.

The coherent case is the positive control and carries a second assertion that the
read genuinely worked, since an empty finding set from a failed read would satisfy
the first assertion while proving nothing. It also demonstrates the newly
reachable arithmetic identities do not false-fire on exactly-read values, which is
the risk of running them over a reader that was previously exempt.

The rewired paths:

    79 passed, 1 failed

The single failure is `test_a_missing_reader_does_not_fall_through_to_the_vision_engine`,
raising a `TypeError` for a missing keyword-only argument on the semantic read
helper. It was reproduced identically on the committed tree WITHOUT this Step's
change, by extracting that tree and running the case alone, so it belongs to the
lane that widened that signature without updating its test.

## Notes

A stale capture was caught one check short of being committed. The change to the
structured reader was built from the committed bytes, and while the rest of the
Step was being written a sweeping commit landed eighty-seven lines of another
lane's work into the same file. The reconstruction was therefore based on a
superseded version, and the staged diff read `27 added / 88 deleted` -- it would
have silently reverted that lane's landed work.

It applied cleanly. Every check except the deletion count said it was fine, which
is the point worth carrying: a patch built from a stale capture applies cleanly,
so success proves nothing about what it applied to, and the deleted side is the
only one that can surprise you. The change was rebuilt from the current committed
bytes with assertions that the other lane's markers survive the transform, and
the re-staged diff read `15 added / 1 deleted`, the single deletion being the
return statement the edit replaces.

Two of this Step's files reached the committed tree through that same sweeping
commit before this lane could stage them. The result was coherent and the tree
was never broken in between: the grounded path used the shared list while the
structured path simply stayed unfixed until this Step's own commit completed it.
