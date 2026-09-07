---
tags:
  - '#audit'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:cbe7255072fb5e32dd4b2225b01e8fc1d7860ef42ba6d8c0c1c9d2b387067f14'
related:
  - "[[2026-09-07-tuimodelo-plan]]"
---

# `tuimodelo` audit: `retired mechanisms a plan row may no longer assert`

## Scope

The campaign's first wave closes, in part, when no row asserts a retired mechanism. That
condition is not evaluable while the set of retired mechanisms is implicit, so this audit
enumerates them and, for each, states the decision that retired it, the evidence of retirement,
what a plan row may no longer assert, and every live citation found in the three plans this
campaign touches plus the production tree.

The audit draws a distinction that does the actual work. A row that names a retired mechanism in
order to REMOVE it is not asserting it; that row is the remedy. A row that names one as a gate,
an admission condition, an owner, or a still-pending premise IS asserting it, and cannot be
closed on its own wording. Only the second class blocks the wave.

Three plans were swept in full over their open rows: the modelo interface plan, the workbench
architecture plan, and this campaign's own plan. Production citations were swept separately,
because a retired mechanism surviving in a shipped module is a stronger defect than one
surviving in a plan row.

## Findings

### exit-receipt-family | critical | The C1 to C5 modelo workspace exit receipts are retired in decision and in code, and are still cited as a live gating condition by a shipped application module.

The accepted modelo workspace-interface decision retired the five exit-receipt schemas, their
five validators and the shared discriminated proof type outright: not renamed, not relocated.
The code followed on 2026-08-30, when commit `51023bdad2` deleted
`dev/quality/modelo_workspace_receipts.py` and its test module, 926 deletions against 63
insertions. That commit's own message records why the deletion was necessary rather than
cosmetic: the module's test suite passed even when the rest of the tree could not import,
because the module depended on nothing in the product, so a green suite over a mechanism no
decision still recognises manufactured confidence rather than provided it.

The same commit records the boundary that a later reader most often gets wrong. The action
denominator survived untouched, because it asserts implementation shape, which the same decision
explicitly retained. The denominator is therefore not a member of this retired family and must
not be treated as one.

A plan row may no longer assert a cohort gate, a green receipt, admission by receipt, or a
disposition whose reconsideration condition is the existence of one. Rebuilding any of the five
is a named hazard for this campaign.

Live citations follow. In the modelo interface plan, `W01.P01.S96` names the retired receipt
vocabulary as the subject of a rename, and `W06.P13.S93` asserts a C5 aggregate matrix across
the cohort. In the workbench architecture plan, `W07.P17.S338` carries a C4 label as historical
provenance for six modelo actions rather than as a gate. In production,
`src/cadrumo/application/modelo/_edit_facade.py` carries the strongest surviving citation: its
module prose at line 11 states that no C3 financial-operand dependency receipt is green yet and
that the facade therefore never advertises a usable C3 path, and line 71 encodes that as a
machine-readable reconsideration condition reading that the capability becomes available once
the green C3 financial-operand dependency receipt exists. That condition can never be satisfied,
because nothing can make a deleted receipt green.

### authenticated-visibility | high | The untrusted-remote-consumer redaction assumption is retired for operator-facing surfaces but survives for logs and off-host payloads, and the two are routinely conflated.

The accepted workbench visibility decision of 2026-09-04 retired the premise that the
full-screen surface should be built as an untrusted remote consumer of the application layer.
Its implementation section directs that surfaces whose projections were shaped by the retired
assumption are re-derived from the decision rather than patched, and that any model documented
as safe or as carrying no values is revisited. It also removes rather than rewords the standing
notice promising that financial details remain protected, on the express ground that the notice
describes a policy that no longer exists.

A plan row may no longer assert that an authenticated surface withholds the operator's own
values, that a projection is safe because it carries no values, or that a standing protection
notice must be preserved.

The exclusion is as load-bearing as the rule, and is the reason this finding is recorded rather
than assumed. Redaction of logs, exceptions, caches, temporary files and off-host payloads is
unaffected and remains required under the sensitive-data rule. Two open rows in the workbench
architecture plan sit on the correct side of that line and must not be swept: `W07.P16.S93`
retains only redacted diagnostics, which is log-shaped and survives, and `W07.P16.S340` names an
operation-supervisor receipt object, which belongs to a different and entirely live receipt
family. The one open row that genuinely carries the retired assumption is `W08.P30.S424`, and it
carries it as the subject of its own removal.

### navigation-join-premise | medium | The five-implementation-area join premise and the parallel console-script spelling are retired, and one plan row survives only as a marker of that retirement.

The accepted navigation-join decision rejects five implementation areas as an operator
information architecture, on the ground that profile, secret, flows, operations and modelo are
internal asymmetries and several are not joinable roots. Its amendment states directly that the
earlier five-existing-areas, no-shape-changes implementation text is retired. The same decision
records that the parallel console-script spelling is retired and does not return, while the
single-flag entrypoint into the out-of-process module remains in force.

A plan row may no longer assert a five-area join, a cohort receipt gating those areas, or the
retired console-script spelling as an entrypoint.

There is one live citation. The workbench architecture plan's `W06.P13.S73` is already annotated
as a retained retired-premise marker: nothing remains to implement under its own wording, and it
must not be closed by asserting the old shape. That row is correctly handled today and needs no
further action beyond not being reopened.

### evaluability | medium | The wave closure condition is now evaluable, and its evaluation is a two-class sweep rather than a keyword search.

With the three mechanisms above enumerated, the closure condition that no row asserts a retired
mechanism can be evaluated mechanically over the open rows of the three plans. The sweep is not a
keyword search. Of the seven open rows matching the vocabulary of a retired mechanism, two are
false positives resting on the exclusion above or on a live sibling family, two name a retired
mechanism as the subject of its own removal, one is an already-annotated marker, and one carries
a retired label as historical provenance. The count that matters for closure is the count of rows
asserting a retired mechanism as a live gate, owner, or pending premise, and the production
citation in the edit facade is the only unambiguous member.

## Recommendations

Adjudicate the two modelo interface plan rows that assert the retired cohort as superseded,
citing the retirement commit, rather than completing or deleting them. Completing them would
require asserting a gate that no decision recognises, and deleting them would erase the evidence
that the premise was retired rather than met. This is the campaign's `W01.P01.S02`.

Reopen the edit-facade capability projection under the surviving mechanism, replacing the C3
receipt condition it still cites. This is the campaign's `W01.P03.S141`, and this audit
establishes that the condition at line 71 of `src/cadrumo/application/modelo/_edit_facade.py` is
unsatisfiable rather than merely stale, which is why the row cannot be closed by waiting.

Treat the two exclusions as binding when any later step sweeps for the retired redaction
assumption. A sweep that removed a log-shaped or off-host redaction gate would weaken a control
the sensitive-data rule still requires, and the visibility decision says so in terms.

Do not treat the action denominator as a member of the retired receipt family. The retirement
commit retained it explicitly, and the campaign's admission-gate work extends it; a reader who
retired it by association would remove the wave's own closure instrument.

Carry the C4 provenance label in the workbench architecture plan's `W07.P17.S338` as naming
residue rather than as an assertion. It does not block closure, but it must not be used to
justify a new cohort reference elsewhere.
