---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:dad5a0b1df054c9040629b77e21af2ae5e2bc5ccdf1fb92ba83f13526f324ecc'
step_id: 'S69'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Retract the proposed granularity extension: a nested subject inherits its family's root structurally, and per-subject declaration is what the contract deliberately removed as tautological

## Scope

- `.vault/audit/`

## Changes

- `verify:` `python -c "...COMMAND_GRAPH subject roots..."` -> `every subject inherits its root from path[1]; none differs from its family`

## Notes

No code changed. This retracts a piece of guidance this campaign wrote one tick
earlier, before the next tick could act on it.

S68 described the residual gap as: the contract binds at `root -> child`
granularity while the criterion was judged over 65 leaf subjects, so "a new
subject nested inside an already-declared family is not covered". It then
proposed extending the contract's granularity to subjects. Both halves are
wrong, for different reasons.

**The structural half is wrong.** A subject's root is `path[1]`. Checked over the
live tree: every one of the 65 subjects takes its root from its path, and none
differs from its family's. `app ledger inventory` is under `app` by
construction; there is no mounting that makes it otherwise. So the placement
decision exists only at the family level -- which the symmetric-difference gate
already enforces in both directions. A nested subject cannot be mis-rooted.

**The proposed fix is worse: the codebase already removed it, deliberately.**
`test_operator_surface_contract_covers_the_live_tree` says so in its own
docstring: "The sub-verb half of this gate is gone because its subject is gone. A
family no longer declares a command tuple to compare against -- membership is
derived from the live tree -- so there is nothing left that can drift, and
asserting a derivation against the thing it derives from would be tautological.
That half caught real drift in both directions while it existed, which is the
argument for deriving rather than declaring, not for keeping the assertion."
Re-adding per-subject declaration would reintroduce exactly that, against a
stated reason.

**What the real residue is, stated correctly this time.** It is semantic, not
structural: a config-shaped concern can be nested inside an app family -- adding
credential management under `app ledger`, say -- and no symmetric difference over
names will see it, because the family is already declared and the subject's root
is inherited. That needs judgement, which is what S60 supplied and what no gate
proposed so far would replace.

The pattern is worth naming: following this campaign's own written guidance would
have produced work the codebase rejected on stated grounds. Guidance a campaign
writes about itself decays the same way an ADR does, and deserves the same check
before being acted on.
