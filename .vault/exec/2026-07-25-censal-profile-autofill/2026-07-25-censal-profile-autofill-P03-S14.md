---
tags:
  - '#exec'
  - '#censal-profile-autofill'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S14'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# Restore aeat config profile censo pull as the live-transport sibling of censo file --file, reading through the censal reader and persisting through apply_cotejo behind the same --apply door, so both transports reconcile identically

## Scope

- `src/cadrumo/entrypoints/cli/_config/_censo_file.py`

## Description

- Add the live censal acquisition to the read-only live facade: gate through the
  shared live-read session boundary, read the consulta with the sede reader, and
  return the parsed result without persisting anything. The taxpayer identifier
  comes off the authenticated session rather than a parameter, because the
  product does not support acting as a representative.
- Register `pull` on the censo command group as the live sibling of `file
  --file`, both defaulting to preview and both committing behind `--apply`.
- Route the commit through the censal read apply authority, which delegates to
  the single cotejo apply path, so one apply event marks the commit and deferred
  axes land in the one divergence namespace both transports share.
- Report all three of the read's outcomes rather than only the two that write:
  adopted rows for paths the profile left blank, unchanged rows for paths already
  carrying exactly what the authority reports, and divergence rows carrying the
  operator's declared value beside AEAT's. The unchanged set is derived from the
  projected paths the reconciliation decided neither way, so the split stays the
  authority's and is not re-decided here. A confirmed field and a field the read
  never covered are different facts, and reporting only writes conflates them.
- Offer no way to aim the read at another taxpayer: the acquisition takes the
  identifier off the authenticated session, and the verb adds neither an option
  nor a positional argument that would reopen that from the outside.
- Report a path the operator deliberately cleared as its own kind of
  disagreement: the divergence row carries a null operator value rather than an
  empty string, because a deletion has no value to show and rendering one as
  blank text would state something different from what happened. A separate
  notice tells the operator the field was not re-added, since someone who
  emptied a field and sees it named again is asking a different question from
  someone whose declared value is contested.
- Announce a disagreement whose values the envelope masks, rather than printing
  two hashes and leaving the operator to work out why they cannot compare them.
  Whether a row is masked is asked of the redaction funnel itself, not answered
  from a list of sensitive paths at this layer, so it cannot drift from what
  redaction actually does.
- Emit every diagnostic on the typed notices channel AND fold each into the text
  output, since the envelope renders notices only in JSON: a warning that AEAT
  disagrees with the operator must not be visible to automation alone. Both
  renderings are built from one notice list so they cannot drift.
- Declare the new command in the operator-surface risk table so the mutating verb
  cannot classify by default.
- Author the four operator-facing strings through the locale CLI in all four
  catalogues, correcting the stale pull help text left by the retired scrape and
  naming what the read actually fills — identity and address — rather than
  censal state at large, since the regime fields have no working read route.

## Outcome

The censo group now offers both transports of the pull-and-file standard, and
they reconcile identically because they share one apply authority. A pull with no
`--apply` writes nothing; a pull with `--apply` adopts only blank fields and
records every disagreement for the operator to adjudicate.

Verified: the acquisition refuses under pytest without the live-test opt-in
(driven to completion, not inspected); the verb surface, its option set and the
preview default read off the real Typer command tree; the no-profile guard is
pinned on WHICH refusal fires, since a bare exit-code check cannot fail there —
the live gate refuses anyway, so removing the guard would leave it green.

The commit call is proven by AST to sit in the apply branch's BODY. An earlier
version walked the whole conditional, which carries its else, and so certified a
door writing on preview and not on apply — the exact inversion of the contract —
as correctly gated. The anti-tautology cases now include that inversion and a
write hidden in a nested function, alongside the ungated, wrongly-gated and
call-free shapes.

The schema-envelope conformance gate, the risk-table parity gate, the locale
suite, the cold-start budget and the layered import contract are green for this
change.

## Notes

The acquisition was first written as a new module under the live package. The
layered import contract refused it: its exception ledger pins each existing
application source module individually and states that a new one must fail
loudly, so extending that ledger would have granted new work the grandfathering
the contract exists to stop expanding. The read was moved into the pinned live
facade beside its sibling reads instead, which costs exactly one deferred-import
site and one ceiling increment — the audit trail that gate asks for.

The reconciliation itself cannot be proven through the CLI offline: the reader
takes an authenticated session and the live-read gate refuses under pytest, so
there is no seam to drive a synthetic read through the door. That behaviour is
proven directly against the application authority in the profile suite; the CLI
layer pins only that this door reaches it rather than re-deciding.

Two gates are red in the shared tree for reasons outside this change and were
attributed rather than absorbed: the lazy-import policy gate is already red at
the committed tree because a landed censal commit carries an undeclared
function-local edge, with three further undeclared edges in peer working-tree
files; and one modelo-390 documented-command sequence fails from a peer's
uncommitted sequence file. Because peers are concurrently adding and removing
deferred-import sites, the exact ceiling value has to be reconciled by whoever
lands last; the increment here is correct relative to the committed baseline.

Two reconciliation defects were fixed at the authority while this door was being
built, and both changed what the door may claim. A previously adopted value went
sticky, so a later change at AEAT reported as a divergence rather than a refresh;
and a path the operator deliberately cleared was re-populated on every read,
because the value projection drops a cleared fact and the path reads downstream
as never set.

The second reached this layer as a false claim rather than a missing feature. The
divergence row rendered the operator's side by way of the value projection, so a
deletion arrived as an empty string — indistinguishable from a field carrying
blank text — and the advisory told them AEAT differed from an answer they had
declared and that their answer stood. It described a declaration they never made.
The row now reads the effective facts, types the operator's side as nullable so a
clear is null rather than empty, renders a marker in text, and raises its own
notice saying the field was not re-added. An earlier draft of this record
predicted the wording would survive the fix untouched; that was wrong, and the
correction is the entry above.

Three surfaces also outlived the refresh branch by still describing adoption as
following blankness — the module docstring, the result schema, and the risk-table
comment. The last was the one that mattered: a risk declaration justified by a
false premise is the wrong kind of green, whatever the flags say. All three now
describe the real rule, which is that the door writes only where the operator has
declared nothing to lose.
