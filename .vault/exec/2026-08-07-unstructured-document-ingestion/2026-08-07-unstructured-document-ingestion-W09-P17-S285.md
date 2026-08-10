---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:723cbbdf1a90985b8c420e6ccdf5fc873e9118a25381650563e80238c2b1e433'
step_id: 'S285'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# The key-echo ratchet: ruled, and already closed by an admission gate

## Scope

- `dev/locales`

## Description

- Take the ruling first, since the row framed this as a decision. A new translation key may NOT be admitted without a real value in every catalogue. There is no sanctioned untranslated state: the scaffold's self-referencing placeholder is refused by a shipped gate, and omitting a locale trips parity. The identical-allowlist is for deliberately-identical strings carrying a stated reason, never a mute button for a string nobody translated.
- Then measure, rather than assume the backlog the row describes still exists. Use the honesty gate's OWN leaf-state predicate rather than a plain equality, because the shipped predicate also folds a trailing dot or colon before comparing, so a narrower probe would under-count and report a clean tree that is not clean.
- Find the count is ZERO in all four catalogues, tree-wide, against a row that records 182.
- Find the mechanism the row was reaching for already shipped, and in the stronger of the two available shapes.

## Outcome

The row's question is answered and its implementation is already at HEAD, so nothing was authored here beyond the record.

The shipped gate is an ADMISSION gate rather than a state gate, and that distinction is the whole value. A state gate asks whether the tree currently carries an echo, and can only ever be satisfied by draining — which loses to the next bulk scaffold, exactly the treadmill the row describes when it says the inflow exceeds any single lane's drainage. An admission gate asks whether an unvalued key can ENTER at all. It ends the loop rather than running it faster, which is why the row was right that no amount of draining could close this and wrong that the question needed an operator.

**One refinement the ruling did not account for, deliberate rather than a loophole.** The shipped contract is not "four real values everywhere". A modelo-schema key with no value carries an explicit null, which holds inter-locale parity while the modelo resolver applies its Spanish-source fallback; every OTHER unvalued key is omitted entirely, so the parity check reports it missing until an author supplies real values. Both outcomes are honest and they are honest in different ways, and the difference is not cosmetic: the modelo case has a resolver that can fall back, and the ordinary case does not.

The trade that design makes is worth restating because it is what makes the gate bite. An unvalued key was already red before it; it reddened the honesty ratchet rather than the parity check. What changed is that the ratchet carried a raisable ceiling — which is precisely how 176 leaves were once committed — while a missing key has no such knob. The red moved from a dismissable gate to one that can only be cleared by authoring the values.

**What this excludes.** This closes the ADMISSION question only. It does not claim the four catalogues are complete, and they are not: the same measurement shows large numbers of null-valued keys awaiting authorship in every locale. It also does not touch the fleet-wide inflow condition, which is not this lane's to absorb and is escalated separately.

## Verification

Measured at HEAD `613973cc50`, parsing all four catalogues and classifying every leaf with the gate's own predicate, including the trailing-punctuation fold the narrower probe would have missed:

    es  key_echo 0
    en  key_echo 0
    ca  key_echo 0
    hu  key_echo 0

The shipped admission gate:

    dev/locales/tests/test_scaffold_admits_no_unvalued_key.py

which states the state-versus-admission distinction in its own docstring, and names the raisable ceiling as the mechanism that let 176 leaves reach HEAD.

Gate run requested from the single test-run authority rather than executed here.

## Notes

The row is a clean example of a premise decaying between authoring and execution. It was true and well-measured when written. Nothing about reading it revealed that, and only re-measuring with the gate's own predicate did — a plain equality check would also have returned zero here, but only by luck, since it cannot see the trailing-punctuation form the shipped predicate folds.
