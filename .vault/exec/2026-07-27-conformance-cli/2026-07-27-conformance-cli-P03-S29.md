---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-27'
modified: '2026-07-27'
body_hash: 'sha256:89b56aee674ca167c85eca18ab663e66a1a7c096c344bc27f0bb7af11670cfbf'
step_id: 'S29'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# surface unattributed oracle payloads and unmatched evidence as report and coverage rows with a shrink-only floor so the attribution gap gains a reader instead of remaining a field nothing consumes

## Scope

- `dev/registry/conformance`

## Description

- Add the typed `OraclePayloadGapRow` projection and carry both gap directions on the
  report envelope.
- Render each gap as an `oracle_gap` record line naming its corpus, payload, and gap kind.
- Add the coverage axes `oracle_payloads.unattributed` and `oracle_evidence.unmatched`,
  each with its own caveat and a real denominator.
- Read the bundled oracle inventory for that denominator, so the counts are reported
  against the total payload population rather than against themselves.
- Add both counts to the shrink-only ratchet ceilings, seeded at zero.
- Prove all three readers by injecting one real gap record.

## Outcome

The finding this Step answers was that `unattributed_payloads` and `unmatched_evidence`
were typed, computed, and recorded, and then consumed by nothing: no test read them for
size or content, and `unmatched_evidence` had zero readers of any kind. A second year-less
payload landing tomorrow would reach no revision and move no number anybody sees.

Both directions now have three readers, and the three are deliberately different in kind.
A rendered `oracle_gap` row carries the fold's own explanatory sentence so a human reading
the report sees WHICH payload and WHY. A coverage axis carries the count against the
bundled payload population, so `1 of 21` cannot be read as a whole-corpus failure or
dismissed as a rounding error. And a shrink-only ratchet ceiling makes growth a gate
failure rather than a screen entry, which is the difference between a gap that is watched
and a gap that is merely displayed.

The denominator is taken from the bundled oracle inventory rather than derived from the
gap list, because a count reported against itself teaches nothing: the honest question is
what fraction of the shipped AEAT figures sit outside the grounding relation.

Both ceilings are seeded at ZERO. Peer Step S30 landed the M303 prorrata payload rename
and its scenario-input split before the baseline was captured, so the live count is now 0
where it read 1 earlier the same day. Seeding at 1 would have permanently licensed a
regression back to the broken state, which is the precise failure mode a shrink-only
ratchet exists to prevent.

That zero also creates the verification problem this Step had to solve honestly. With an
empty gap set, any assertion on the live count passes whether or not anything consumes the
field — the very condition that produced the original finding. The proof therefore injects
one real `UnattributedOraclePayload`, projects it through the real builder, and asserts it
reaches all three surfaces while the unmodified report shows none of them.

Verification. Live state, actual output:

```
axis axis=oracle_payloads.unattributed scope=payload measured=0 population=21 fraction=0.0000
  caveat="bundled AEAT figures sitting outside the grounding relation entirely"
axis axis=oracle_evidence.unmatched scope=payload measured=0 population=21 fraction=0.0000
  caveat="attributed oracle evidence that reaches no registry revision"
ceiling counter=unattributed_oracle_payloads current=0 allowed=0
ceiling counter=unmatched_oracle_evidence current=0 allowed=0
```

Earlier the same day, before peer Step S30 completed, the same surfaces rendered the gap
rather than hiding it — the report line was:

```
oracle_gap kind=unattributed_payload corpus=aeat_manual_worked_example
  payload=modelo-303-prorrata-general-regularizacion.json gap=payload_name_lacks_modelo_and_filing_year
```

which is the behaviour this Step exists to guarantee, observed on the real tree rather than
only in a fixture.

The injected-gap gate asserts the clean report contains no `oracle_gap` line, the seeded
report names the injected payload, the coverage axis moves from `measured=0` to
`measured=1`, and the ratchet turns from passing to a named violation
`unattributed_oracle_payloads grew`. All four move together; none of them can pass while
the field is unread.

## Notes

The RAG discovery mandate was WAIVED for this campaign by explicit operator direction;
grounding was by whole-file reads and `rg`.

This Step's code shipped inside the S13, S14 and S15 commits rather than a commit of its
own, because the gap projection, its rendering, and its ceiling are parts of the same three
artefacts those Steps built; its dedicated verification landed with S17. The one thing that
would have been wrong to defer — the ceiling value — was decided at baseline-capture time
and is recorded above.

The gap set was watched moving during execution: 1 unattributed payload and 0 grounding
findings before the peer's rename, 0 and 3 after the rename but before the split, 0 and 0
after both. The middle state is the one the fact-lifts audit predicted for a rename landing
ahead of its split, and it was visible on this surface at the time — which is the first
evidence that the readers added here work on a real change rather than only on an injected
one.
