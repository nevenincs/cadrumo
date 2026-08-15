---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:b3e940fac6f8822d09ba8b2eb31cba600e4f3a92e0c767db40372d83cb7e0a16'
step_id: 'S105'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium close the gap that lets a decision be made without a record, since a ruling delivered as a report and never persisted is indistinguishable from no ruling and cost a full search to establish, which is the campaign-close discipline failing in the direction nobody watches

## Scope

- `.vault/audit/`

## Description

- Census every closed "rule/decide/triage/confirm-or-refute/reconcile" row in
  the plan against its execution record, and against the rest of the corpus,
  for a ruling delivered but never persisted.
- Cross-check every closed step's exec-record existence mechanically.
- State a mechanically checkable closure condition and confirm what
  `vaultspec-core` can and cannot already enforce of it.
- Name the direction nobody watches: a ruling recorded narrower than what it
  decided.

## Outcome

Twenty closed ruling rows were read in full and cross-checked against
`.vault/`. One confirmed instance of the failure exists, and it is already
closed: `S59`'s own execution record documents that the ruling it was
dispatched to act on had been "delivered as a report and never persisted,"
and that establishing its absence cost a full corpus search. I re-ran that
search independently and confirmed no other document anywhere in `.vault/`
carries that missing predecessor ruling — `S59`'s account is the only trace of
it. `S59` already repaired the defect at the point it was found; there is
nothing further to remediate there.

The other nineteen ruling rows were each read end to end and each states a
verdict a later reader can act on without re-deriving it, including several
that visibly self-correct a wrong first ruling inside the same document
(`S62`, `S91`, `S121`, `S133`) rather than leaving the wrong claim standing.
Mechanically, all eighty-five closed plan steps have a matching exec record;
zero are missing.

The mechanically checkable closure condition: every closed (`[x]`) plan Step
must have a corresponding `.vault/exec/.../<step>.md` file. `vaultspec-core
vault check exec-mapping` verifies only the reverse direction today (every
exec record maps to a live Step); it does not walk closed Steps checking for a
matching record, so this campaign's clean 85/85 result is author discipline,
not a CLI gate. Content fidelity — whether an Outcome section states an actual
verdict, and whether that verdict answers the full question the row posed —
cannot be checked mechanically at all; it requires a reader.

The direction nobody watches, a ruling recorded narrower than what it
decided, produced no confirmed instance in this pass. Every observed scope
narrowing in the twenty rows read was explicitly named as a deliberate limit
in its own record (`S91`, `S133`, `S126`), not hidden inside an apparently
complete answer. That is a clean result for this pass, not a standing
guarantee, since nothing mechanical checks for it.

Full findings, evidence and recommendations are in
`2026-08-15-profile-password-custody-unrecorded-ruling-closure-audit`.

## Notes

No new rule was authored, per the retirement of rule codification. The
closest existing clause is in `aeat-agent-orchestration` ("no plan step marked
complete without a matching exec record"); it was followed here and is
insufficient only in scope, not in substance — it presumes a ruling is always
dispatched against a plan Step, while the confirmed defect was a ruling
apparently reported before it had one. The sentence that would extend the
clause to cover that case is named in the audit's recommendations for whoever
next edits that rule, and is not added here.
