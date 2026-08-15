---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:3592b0554b57dbf94dd943ad84148b20c12da26e496bd800854ee37e379128c0'
step_id: 'S112'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium give a verb's existence one authoritative declaration, since six independent surfaces must currently agree that a verb exists and none of them is the authority, so the operator manifest declared none of seventeen verbs while five other surfaces still described them and each surface broke in turn as the previous was repaired

## Scope

- `src/cadrumo/application/operator_surface/ and src/cadrumo/entrypoints/mcp/`

## Description

- Establish by evidence whether the crashing custody declaration names a verb
  that should exist, before touching it, and revise the reading when the
  evidence turns out to point the other way.
- Delete the two custody family declarations an accepted ruling retired, and
  keep the third, whose unreachability is an open capability gap rather than a
  retirement.
- Give the contract a typed way to say which of those two things a declaration
  means, so the crash can stop without the fix asserting a product decision.
- Make every cross-surface refusal in the join typed and accumulating, so a
  failed reconciliation reports its whole census rather than one item per crash.
- Remove the contract's hand-authored per-family command inventory and derive
  family membership from the live command tree instead.
- Replace the single-family spot check with a property over every family.

## Outcome

**The passphrase verb is NOT retired, and the first reading of this row was
wrong.** The correction came from another agent's evidence and it is decisive:
a deliberately-failing assertion in the custody lifecycle module carries the
closed ruling in its docstring, and it says credential rotation is absent from
every layer -- no application-layer rotation function, only unorchestrated
primitives in the custody package -- so what is missing is the capability to
rotate a profile credential, not one spelling of a verb. It states plainly that
asserting the verb retired would encode a product decision nobody has taken.
Deleting the declaration, which is what this row first did, would have silenced
the crash by making exactly that assertion, and would have destroyed the only
structural record that the capability is owed. The declaration is restored. The
retirement of the recovery facade is a genuine accepted ruling and is a
different case, so those two declarations stay deleted; the three were never
one case.

**Two shipped gates encode opposite rulings on this one verb.** The custody
lifecycle module asserts the verb must be mounted; the root grammar module
asserts it must not resolve, in the same list as the genuinely retired
spellings. The tree can never be green on both. That is not drift, where two
surfaces fell out of step by neglect -- it is two surfaces disagreeing in
principle, each internally coherent, with nothing above them to settle it. It
is the sharpest available evidence for this row's thesis: when a verb's
existence is declared in six places and none is the authority, the surfaces do
not merely diverge, they can hold contradictory positions indefinitely and each
looks correct from where it stands. No side was picked here, and picking one
would have been the oscillation the quality-gate discipline warns about.

**The crash named one orphan and concealed two.** The refusal raised on the
first mismatch it reached, so it reported only the passphrase family while
recover and recovery were equally orphaned and equally fatal. That mattered
twice over: removing the named one would have moved the crash rather than
cleared it, and the incomplete census is what let the first reading treat three
unlike cases as one. The refusal now accumulates every disagreement and raises
once, typed, through the registered operator-surface contract error rather than
a bare `ValueError` that reached the wire as an untyped protocol error carrying
an internal provenance string.

**A declaration now states which of the two things it means.** The contract
carries a typed mount state with a required, non-blank reason bound to it in
both directions: a family declared unimplemented must name the capability it
waits on, and a mounted family may not carry such a note. The join treats an
unreachable family with a stated reason as agreement rather than
disagreement -- contract and tree concur it is not reachable, and the
declaration exists to record what is owed. The teeth are on the reverse arm:
once the tree does reach it, the note has outlived its gap and refuses, so the
marker cannot become a permanent silencer describing a shipped capability as
missing. A retired family is neither state; it is deleted, because nothing is
pending.

**The six surfaces that must agree a verb exists**, found by evidence and
confirmed against the live join, are the live registered command tree; the
result-schema registry; the verb input-schema projection; the mounted-family
contract declaration; the profile write-policy classification; and the MCP
exposure decision. Four are already computed from the tree. Only two are
hand-authored, and both had drifted: the write-policy allowlist, which the
CLI-contract rule already names as unscanned, and the contract's per-family
command tuple. The risk table is a seventh, recorded below.

**The ruling: the live command tree is the sole authority for existence, and
the contract declares only what the tree cannot know.** A family's domain,
operator question, service owner, mutability and -- now -- whether its absence
is an owed capability are editorial judgments and stay declared. Its command
inventory is none of those. It is a restatement, and a restatement is a thing
that can disagree; it did, in both directions at once, with eight verbs
declared that the CLI does not mount and two families missing verbs it does. So
the command tuple is deleted from the model rather than gated, and membership
is derived from the reconciled canonical CLI paths.

Derivation was chosen over a conformance gate because it was reachable: every
consumer was a test or a comment, so nothing had to keep a parallel list alive.
It is derived from the CLI paths and deliberately not from the schema-key
spelling, which drops the app root segment for some families and keeps it for
others; a prefix match reported seven families as empty before that was caught.

**What guards it is the production join, not a test.** The reconciliation runs
on every CLI invocation and every tool listing, and it now checks the family
relation in both directions, so a mounted family no surface declares refuses as
loudly as an unreasoned declaration nothing mounts. Membership correctness is a
property over every family against an independent raw walk, which is what the
single-family spot check it replaces was not.

**Proven to bite**, from a script outside the repository so no tracked file was
mutated: the clean tree reconciles and does carry a declared-unimplemented
family, so the accepting path is exercised rather than assumed; an unreasoned
orphan refuses by name; a live-only family refuses by name; both at once
produce one refusal naming both; a note on a family the tree does reach refuses
as stale; an unreasoned orphan is still refused in the same run that accepts a
reasoned one, so no change that simply ignored unreachable families could pass;
and a truncated derivation reds the membership property. Every gate returns
green with the patches lifted.

Before and after on the integration lane: forty-five failed and two hundred
seventy-three passed, becoming twenty-six failed and two hundred ninety-three
passed. Nineteen fixed, none new, and no occurrence of the orphan refusal
remains. Five harness modules are fully clear. The remaining twenty-six were
all failing beforehand: a registry validation and load cluster, two output and
tool-name budget gates, the closed-value-axis exemption gate, the risk-table
pair, the live reconciliation's divergence over the declared-unimplemented
profile keys, and the contract drift gate discussed below.

## Notes

**One coordination item, deliberately left red rather than edited.** The
entrypoint contract drift gate refuses the restored declaration with a single
honest line naming the passphrase family as having no live mount. It was
already red before this row for three unrelated drifts, all of which the
derivation removed, so this is a reason changing rather than a new failure. The
gate belongs to the agent holding the custody gate modules and was not touched
here. The fix is one line on their side: read the typed mount state and let a
declared-unimplemented family through the orphan arm. That is not hiding the
construct from a matcher, which the quality-gate rule forbids -- the marker is
a typed, reasoned declaration in the authority, staleness-gated, and the gate
would be consuming it rather than restating it, which is the whole point of the
ruling.

**The risk table is a seventh surface, and it is the same defect.** Twenty
mutating commands carry no declared risk row, and the two families most
represented are exactly the two the contract's command tuple was missing:
counterparty and deudas. The same verbs landed live and failed to reach two
independent hand-maintained surfaces, which is strong evidence that the problem
is absent authority rather than a run of unrelated misses. It is not fixed
here: each missing row is a destructive, handoff and live-write judgment per
verb, it was flagged as another agent's, and absorbing it silently is what this
campaign's discipline forbids. Unlike the command tuple it is not derivable,
since the risk axes carry genuine judgment, so it belongs under the weaker
shape of one declaration plus a parity gate, which it already has and which is
currently red for a real reason.

**A peer's sweep commit captured this row's working tree mid-flight**, twice.
The contract, model, manifest and several test modules were committed under
registry-sweep subjects that describe none of them, including the deletion this
record now reverses. Nothing was lost and nothing was reverted by hand, but the
first, wrong reading of the passphrase question reached the branch under a
subject that gives a later reader no way to find it.

**Two modules outside this row's scope had to move with the change.** Removing
a model field is not separable from its consumers, so the entrypoint contract
drift gate and the login-gated exemption anchor were updated in the same
change, before the ownership of that directory was reassigned; the projection
site in the CLI common module was then extended by one keyword to carry the
mount state. The login-gated anchor was already consistent when reached.

**One rough edge left standing.** When an entire family is undeclared the
accumulated refusal also lists every one of its leaves as unaccounted, so a
single structural fault can produce a very long message. It is complete rather
than wrong, and suppressing the consequential lines risks hiding genuine
per-leaf gaps, so it was left and recorded here instead.
