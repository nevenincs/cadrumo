---
tags:
  - '#adr'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:c03a1aa22b6acbd96d7af34e3707d354e93a5a714df0fa4a3e691de22252d354'
related:
  - "[[2026-09-07-tuimodelo-reference]]"
  - "[[2026-08-24-modelo-edit-contract-adr]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
---

# `tuimodelo` adr: `reconciliation and verification surfacing` | (**status:** `proposed`)

## Problem Statement

The campaign brief names four operator verbs, two of which — reconcile and review — have
no reachable surface and no settled meaning. "Reconcile" is ambiguous in the worst
possible way: the backend offers four genuinely distinct comparison mechanisms that differ
in what they compare, what they return, how severe their output is, and whether it is
persisted (`2026-09-07-tuimodelo-reference`). A surface labelled "reconcile" that silently
picks one of them would mislead an operator about what was checked.

Verification has the opposite problem. The mechanism is settled and rich — 30 verify-time
gates plus 9 raising gates, and a registry predicate population divided 103 advisory to 78
blocking — but the built screen shows only severity, kind and casilla, while the
command-line surface shows the message, the legal references and the recovery action
(`2026-09-07-tuimodelo-reference`). The frontend is therefore strictly less informative
than the backend it fronts, on precisely the surface where an operator decides whether a
declaration may be filed.

A decision is needed before the reachability wave wires either surface, because wiring
them as they stand would freeze both defects into the product.

## Considerations

- Four comparison mechanisms exist, at two different levels, and the distinction matters. The
  reconciliation service itself accepts two closed evidence kinds — a justificante and a filed
  declaración — through two entry points, and returns a reconciliation report. Two further
  mechanisms live outside that service and return verification findings rather than a report:
  the divergence check against an authority-pulled filing, and the modelo 303 to modelo 349
  intracommunity check. A surface that presents all four as one verb would be conflating two
  result types as well as four questions (`2026-09-07-tuimodelo-reference`).
- The reconciliation report yields a binary verdict derived purely as match-if-no-diffs,
  with no severity gradation (`2026-09-07-tuimodelo-reference`).
- Reconciliation advisories carry three constructed codes with no severity field, no resolution action,
  and an English prose message rather than a locale key — so they cannot be rendered in a
  localized surface as they stand (`2026-09-07-tuimodelo-reference`).
- Diffs are grounded: a validator refuses a value diff that lacks legal or source
  references, so provenance is available to display
  (`2026-09-07-tuimodelo-reference`).
- The frontend contract for verification severity is an invariant, not a convention:
  blocking findings carry a typed precondition failure with a recovery action, warnings
  carry none (`2026-09-07-tuimodelo-reference`).
- 36 of 38 calculation diagnostic reasons are not persisted onto the revision, so a surface
  that reads a stored revision loses them; they must be captured at calculation time
  (`2026-09-07-tuimodelo-reference`).
- The command-line structured calculate result carries no diagnostics at all, so parity
  with that surface would be a downgrade (`2026-09-07-tuimodelo-reference`).
- Two gates are in-source admissions of non-operation: one advisory cannot fire in
  production, and one reconciliation population declares known false negatives
  (`2026-09-07-tuimodelo-reference`).
- Verification findings already have 37 locale keys and a total mapping from finding kind
  to an operator-action axis (`2026-09-07-tuimodelo-reference`).

## Considered options

**For the reconcile verb:**

1. **One "reconcile" action that picks a mechanism by heuristic.** Rejected: the four
   mechanisms answer different questions, and an inferred choice makes the answer
   unattributable.
2. **Expose all four as separate top-level actions.** Rejected: three of the four are
   distinguished by evidence provenance rather than by operator intent, so it pushes an
   internal taxonomy onto the operator.
3. **One reconcile destination parameterised by evidence source, with the source chosen
   explicitly and named in the result.** Chosen: the operator picks what to compare
   against, which is the real decision, and the result states which comparison ran.

**For the verification surface:**

4. **Wire the existing screen as built.** Rejected: it would ship a surface strictly less
   informative than the command line on a filing-grade decision.
5. **Render the full finding, driven by the severity invariant.** Chosen: blocking findings
   render their recovery action because the invariant guarantees one exists; warnings
   render without, because the invariant guarantees none.

## Constraints

- Reconciliation advisories cannot be localized until they carry locale keys instead of
  authored English prose. This is a backend change and a prerequisite for the surface, not
  a frontend workaround.
- Advisories carry no severity and no resolution action, so the surface cannot rank or
  action them until the backend model gains those fields. It must still declare their
  existence; withholding is disclosed, never silent.
- The host workspace is already decided: an accepted decision places reconciliation under the
  authority-sync workspace, so this record adopts that placement rather than choosing one
  (`2026-09-02-unreachable-capability-tui-navigation-join-adr`).
- Diagnostics are captured into the accepted modelo work review read model rather than a second
  projection authored for this surface
  (`2026-08-10-casilla-schema-read-model-adr`).
- Diagnostics must be captured at calculation time; a design that reads them back off a
  stored revision is unbuildable for 36 of the 38 reasons.
- The two in-source non-operational admissions must be resolved or explicitly labelled;
  neither may be silently rendered as a passing check.
- Depends on the edit contract decision for the session and staleness semantics the verify
  step observes; that record is accepted and stable.
- The retired exit-receipt family must not be reintroduced to gate these surfaces.
- No surface may present a local verification pass as authority acceptance.

## Implementation

Reconciliation is one destination with an explicit evidence selection. The operator chooses
what the declaration is being compared against — a document they hold, a justificante
retrieved from the authority, a filing pulled from the authority, or the cross-modelo
consistency check — and the resulting report names the comparison that ran, so the answer
is never detached from its question. The cross-modelo check is presented alongside the
others rather than hidden, because it answers a question operators actually ask, but it is
labelled as a consistency check rather than as evidence reconciliation.

The report renders the diff set as the primary content, not the binary verdict. Each diff
shows both values, the field it belongs to, its kind, and the grounding that the domain
validator already guarantees is present. The binary verdict is retained as a summary but is
never the only thing shown, because match-if-no-diffs collapses "nothing differs" and
"nothing was comparable" into one word.

Advisories gain a severity and a resolution action in the backend model, and their prose is
replaced by locale keys. Until that lands the surface renders them as explicitly withheld,
stating that advisories exist, how many, and why they are not shown. It does not omit them:
omission would collapse "withheld pending localization" into "none found", which is the exact
substitution the no-silent-under-declaration rule forbids, and doing it in a reconciliation
surface would mean reporting a clean comparison that was not clean.

Verification renders the complete finding: message, severity, kind, casilla, legal
grounding, and — for blocking findings only — the recovery action that the precondition
invariant guarantees. The severity invariant is the rendering rule, so the presence or
absence of a recovery action is derived from the finding's own type rather than from a
frontend conditional. The existing finding-kind to operator-action mapping supplies the
action vocabulary, and the existing locale keys supply the copy.

Diagnostics are captured at calculation time into the accepted work review read model rather than
read back from the revision, because the revision does not carry them. This means the
verify surface and the calculate action are joined: a verification view that was not
produced from a calculation in the same session shows what the revision holds and says so,
rather than implying the diagnostic set is empty.

Gates that cannot fire in production and reconciliation populations with declared false
negatives are labelled as such wherever their result appears. A check that cannot fail must
never render indistinguishably from a check that passed.

## Rationale

The reconcile decision turns on attribution. Three of the four options produce a screen
that says a declaration reconciles; only the chosen one produces a screen that says what it
reconciles *against*. In a filing-grade product that distinction is the whole value of the
verb, and the cost — one explicit selection by the operator — is trivial next to the
alternative of an unattributable verdict.

The verification decision is forced rather than balanced. Wiring the screen as built would
knowingly ship less information than the command line already gives, on the exact surface
where a filing decision is made. The severity invariant makes the richer rendering cheap:
because blocking findings are guaranteed to carry a recovery action and warnings are
guaranteed not to, the surface needs no conditional logic of its own and cannot drift out
of step with the backend's own classification.

Both decisions push work backward into the application layer — locale keys and severity for
advisories, calculation-time diagnostic capture — rather than compensating in the
frontend. That is the campaign's standing direction, and here it is also the only correct
option: a frontend that invented severities or translated its own advisory prose would
become a second authority on how serious a discrepancy is.

## Consequences

The reconcile surface becomes honest about a distinction the backend already makes and the
command line already exposes, at the cost of one more operator choice before the comparison
runs.

Two backend changes become prerequisites rather than improvements: advisory localization and
advisory severity. Both are small and both unblock the surface; neither can be deferred
without shipping untranslated prose or an unrankable list.

Joining diagnostics to calculation time makes the verify surface stateful in a way an
implementer may not expect. A verification view opened against an old revision is
legitimately less informative than one opened after a fresh calculation, and the surface
must say so rather than let the difference read as "no problems found".

Labelling the non-operational gates will make the product look weaker in two places where
it currently looks complete. That is the correct direction: a gate that cannot fire is not
a passing gate, and the campaign inherits the obligation to either fix or retire both.

The four-mechanism reality is now visible to operators. Some will ask why there are four,
which is a documentation cost, but the alternative was answering a question they did not
ask and not telling them which one.
