---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:795d42c37189543d4a29447af4c33c63de4cd5c9cdc7528b9666d169a59f648b'
step_id: 'S350'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Stop the recovery-action census being invalidated by every relocation, which is what makes its drift recur rather than resolve: the census is keyed by physical location -- file path plus enclosing symbol -- so promoting a module from a private to a public name silently orphans every adjudication it holds, even though not one judgement has changed. That has now happened across 34 entries in a single sweep, and this campaign lands relocations continuously. The architecture rule already requires a relocation to update every production, test, fixture, tooling, annotation, registration and dynamic consumer atomically, and this census is a tooling consumer nobody has been sweeping -- so the rule is being met in letter for code and missed for the inventories that describe it. Two ways out and the choice is the Step: either key the census on something location-independent that survives a rename, or make sweeping it an explicit part of the relocation checklist so the omission fails loudly at relocation time rather than silently at the next census run. Prefer the first if a stable key exists, because a checklist item is only as good as the person remembering it -- and the evidence that people do not is that a debt inventory four lines from a comment warning about this exact class had drifted the same way

## Scope

- `the recovery-action census key derivation`
- `or the relocation checklist that must sweep it`
- `and a proof that a rename no longer orphans an adjudication`

## Changes

- `M` `dev/quality/cli_action_census_dispositions.py`
- `M` `dev/tests/test_cli_action_census_dispositions.py`
- `verify:` `pytest dev/tests/test_cli_action_census_dispositions.py -n0` -> `3 new proofs pass`

## Notes

`CandidateKey.path` is now `field(compare=False)`: carried for diagnostics,
excluded from identity. A module relocation preserves every adjudication it
held.

THE KEY IS `enclosing_symbol` + `candidate_role` + `alias` +
`action_identity`. IT IS NOT the location-free triple of role + alias +
identity. Measured against the live 191-row ledger:

    191 distinct, 0 collisions   path + symbol + role + alias + identity (old)
    191 distinct, 0 collisions   symbol + role + alias + identity   (adopted)
    130 distinct, 61 rows lost   role + alias + identity            (REFUSED)

`alias` is usually the placeholder `<command-literal>`, so every
`aeat app ledger import` site looks identical under the triple. Adopting it
would have MERGED 61 HUMAN JUDGEMENTS. This correction is recorded here
rather than in a message because a bare "the key is location-independent"
invites the next reader to re-derive the triple and silently merge them
again.

`enclosing_symbol` is the discriminator that keeps it unique, and it draws
the right line: it survives a MODULE rename -- the documented drift, 34
entries orphaned in one sweep -- and does NOT survive a FUNCTION rename,
which is a real change to the thing being judged and must force
re-adjudication. A key that survives everything is not relocation-immune, it
is judgement-destroying.

THREE PROOFS, all driven from the real checked-in ledger rather than
synthetic fixtures: a module rename preserves identity, hash and dict
lookup; a function rename still refuses to inherit the previous
adjudication (the anti-tautology counterpart, without which "drop path"
could be satisfied by dropping discriminators until nothing distinguishes
two sites); and every checked-in adjudication keeps a distinct identity,
asserted as a property rather than a tally.
