---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:03edc48ab1a9ecaad45f3b83ef52bd5c8212d0da078b410f61599120a1fa9855'
step_id: 'S169'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Constrain the withdrawal survey's completeness

## Scope

- `src/cadrumo/application/ledger`
- `src/cadrumo/llm`
- `src/cadrumo/entrypoints/cli`

## Description

- Wire the consent ledger into the withdrawal survey at the CLI, which is the one production site that can compose them: the application layer that owns the survey deliberately does not import the adapter-side ledger.
- Filter the projection on each entry's own recorded bucket, so a row belonging to another profile cannot surface under this one.
- Make the survey's consent-entry parameter required, since its only plausible default is the empty tuple and the empty tuple is a claim.
- Add two CLI regressions for the enumerate leg: a recorded dispatch reaches the operator, and a profile with a recorded dispatch is never told that nothing has left this host.
- Add a cross-profile scoping regression written through the real repository at the ledger's own namespace.
- Add five completeness gates to the module that owns the dispatch choke point: every consented dispatch recorded exactly once, a cache hit recorded too, an unwritable record refusing rather than degrading, the audit trail surviving the retention sweep, and the read refusing an unreadable row rather than skipping it.
- State the empty history explicitly at the nine existing call sites the required parameter now reaches.
- Type the CLI test envelope helper at the value position, clearing every type error in that module.

## Outcome

The row asked for a gate and found a live defect first. The sole production caller never passed the entries, so `consent list` reported an empty off-host history on every profile, always, while the ledger filled up beside it. The enumerate leg of the survey's own three-part contract had no production wiring and no test: every existing case exercised the marking leg, and the one assertion about dispatches asserted they were empty on a profile where they should be.

The reachable harm is sharper than a missing list. The affirmative no-history notice fires when both the dispatch list and the artefact list are empty, and the dispatch list was empty unconditionally. So after a successful re-derivation, when no cloud-derived artefact survives, the verb told an operator that nothing had left their machine over a profile that demonstrably had sent something. That is the exact inversion the survey's own design forbids, since re-derivation asserts a new derivation rather than claiming the transmission never happened.

On the row's hard half: "complete over a period" is currently satisfiable as "complete over all time", because the ledger read applies no period filter and returns every entry for the profile. Rather than gate something weaker and call it done, completeness is decomposed into four properties that are each falsifiable today, and the module records that a period filter would need a boundary case this set does not yet contain.

The two preconditions named in the brief were confirmed rather than assumed. The append sits inside the branch honouring the token and ahead of the cache read, so a cached response is recorded too; and any storage failure refuses the dispatch, which is what makes any completeness claim possible at all.

## Verification

Unit lane, sequential:

    uv run --no-sync pytest <six consent, ledger and eligibility suites> -n0 -q -m unit
    61 passed, 38 deselected in 43.81s

Integration lane, sequential, same surfaces:

    uv run --no-sync pytest <the CLI consent, extract-consent and batch suites> -n0 -q -m integration
    38 passed in 84.89s

Both lanes run and both are reported; neither is offered as covering the other.

Mutation proofs ran from two out-of-repo pytest plugins at module scope, loaded with `-p`. Each prints a banner AND counts its own invocations, refusing the run at session finish if the patched callable was never reached, so a banner alone is never taken as evidence the patch landed.

The survey wiring, reproducing the previous behaviour exactly:

    MUTATION=none      10 passed                                   (control)
    MUTATION=unwired   2 failed, 7 passed   invocations=7
    MUTATION=nofilter  1 failed, 9 passed   invocations=8

The unwired mutation reds exactly the two enumerate-leg regressions and nothing else; the filter mutation reds only the cross-profile case.

The ledger completeness gates:

    MUTATION=none       35 passed                       (control)
    MUTATION=swallow    1 failed   invocations=9        refuse-not-degrade only
    MUTATION=skiprow    1 failed   invocations=7        read-refuses only
    MUTATION=dedupe     4 failed   invocations=9
    MUTATION=dropfirst  5 failed   invocations=9
    MUTATION=prune      1 failed   invocations=3        retention-sweep

## Notes

The retention-sweep gate did not bite on its first two mutation runs, and the run reported thirty-five passes with the mutated callable invoked fourteen times. The mutation was inert: the repository's key listing returns HMAC digests while its delete takes the natural key, so the deletion silently removed nothing and the run read as a sound gate. Rebuilding the natural key from the decrypted payload made the deletion real, and the gate reddened. A fully-green mutation run was a claim about the probe before it was a claim about the code.

The dedupe and drop-first mutations carry process-global state, so their blast radius is wider than the property under test; the precise cases are the two single-red mutations.

No live inference was triggered. Every dispatch runs against a loopback endpoint over real HTTP, and the queue of received bodies is what distinguishes "did not transmit" from "raised on the way there".

A concurrent lane left an unrelated adapter module with a syntax error mid-edit, which blocked collection tree-wide for several minutes. It was not touched; the run was repeated once the peer's edit completed.
