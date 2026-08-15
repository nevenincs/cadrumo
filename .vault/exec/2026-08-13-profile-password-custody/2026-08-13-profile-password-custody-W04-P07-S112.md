---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:e0130f423afc15dc53d85f87de830577f7b4d2200f490038df88e22dfa9a41a5'
step_id: 'S112'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium give a verb's existence one authoritative declaration, since six independent surfaces must currently agree that a verb exists and none of them is the authority, so the operator manifest declared none of seventeen verbs while five other surfaces still described them and each surface broke in turn as the previous was repaired

## Scope

- `src/cadrumo/application/operator_surface/ and src/cadrumo/entrypoints/mcp/`

## Description

- Establish by evidence whether the crashing custody declaration names a verb
  that should exist, before touching it.
- Delete the three retired custody family declarations and their root
  required-children entries, since the crash names one and hides two.
- Make every cross-surface refusal in the join typed and accumulating, so a
  failed reconciliation reports its whole census rather than one item per crash.
- Remove the contract's hand-authored per-family command inventory and derive
  family membership from the live command tree instead.
- Replace the single-family spot check with a property over every family, and
  repoint the entrypoint drift gate at the half whose subject survives.

## Outcome

**The verb is retired, so the declaration goes.** Established by evidence, not
by reading the declaration: the per-profile custody cutover retired the global
recovery facade, and a shipped grammar gate asserts that the passphrase,
recover and recovery spellings must all fail to resolve, with its rationale
written out. The earlier row that retired the dead operator instructions and
the ruling on the unresolved command subtrees both treat these as residue of a
retirement already executed. Nothing anywhere asks for the verb back, and while
this step ran a peer landed the deletion of the matching sequence contracts
independently.

**The crash named one orphan and concealed two.** The refusal raised on the
first mismatch it reached, so it reported the passphrase family; recover and
recovery were equally orphaned and equally fatal, and removing only the named
one would have moved the crash rather than cleared it. That is the defect
behind the row's own history of each surface breaking in turn as the previous
was repaired, reproduced inside a single function. The refusal now accumulates
every disagreement and raises once, typed, through the registered
operator-surface contract error rather than a bare `ValueError` that reached
the wire as an untyped protocol error carrying an internal provenance string.

**The six surfaces that must agree a verb exists**, found by evidence and
confirmed against the live join, are the live registered command tree; the
result-schema registry; the verb input-schema projection; the mounted-family
contract declaration; the profile write-policy classification; and the MCP
exposure decision. Of these, four are already computed from the tree. Only two
are hand-authored, and both had drifted: the write-policy allowlist, which the
CLI-contract rule already names as unscanned, and the contract's per-family
command tuple.

**The ruling: the live command tree is the sole authority for existence, and
the contract declares only what the tree cannot know.** A family's domain,
operator question, service owner and mutability are editorial judgments and
stay declared. Its command inventory is not a judgment, it is a restatement,
and a restatement is a thing that can disagree — it did, in both directions at
once. Eight verbs were declared that the CLI does not mount, and two families
were missing verbs the CLI does mount. So the command tuple is deleted from the
model rather than checked, and membership is derived from the reconciled
canonical CLI paths.

Derivation was chosen over a conformance gate because it was reachable: every
consumer was a test or a comment, so nothing had to keep a parallel list alive.
It is deliberately derived from the CLI paths and not from the schema-key
spelling, which drops the app root segment for some families and keeps it for
others; a prefix match reported seven families as empty before that was caught.

**What now guards it** is the production join, not a test: the reconciliation
runs on every CLI invocation and every tool listing, and it now checks the
family relation in both directions, so a mounted family no surface declares
refuses as loudly as a declaration nothing mounts. The entrypoint drift gate
keeps its family half and loses its sub-verb half, because that half's subject
no longer exists and asserting a derivation against its own source would be
tautological. Membership correctness is instead a property over every family
against an independent raw walk, which is what the old single-family spot check
was not.

**Proven to bite**, from a script outside the repository so no tracked file was
mutated: the clean tree reconciles; a declared-only family refuses by name; a
live-only family refuses by name; both at once produce one refusal naming both,
which is the accumulation the row turned on; and a deliberately truncated
derivation reds the membership property. All gates return green when the
patches are lifted.

Before and after on the integration lane: forty-five failed, two hundred
seventy-three passed, becoming twenty-six failed, two hundred ninety-three
passed. Nineteen fixed, none new, and no occurrence of the orphan refusal
remains. Every one of the twenty-six was failing beforehand: a registry
validation and load cluster, two output and tool-name budget gates, the
closed-value-axis exemption gate, the risk-table pair, and the live
reconciliation's divergence over the declared-unimplemented profile keys, which
belongs to the capability question another row holds.

## Notes

**The risk table is a seventh surface, and it is the same defect.** Twenty
mutating commands carry no declared risk row, and the two families most
represented are exactly the two the contract's command tuple was missing:
counterparty and deudas. The same verbs landed live and failed to reach two
independent hand-maintained surfaces, which is the strongest available evidence
that the problem is the absence of an authority rather than a run of unrelated
misses. It is not fixed here: each missing row is a destructive, handoff and
live-write judgment per verb, it was flagged as another agent's, and absorbing
it silently is what this campaign's discipline forbids. Unlike the command
tuple it is not purely derivable — the risk axes carry genuine judgment — so it
belongs under the weaker shape of one declaration plus a parity gate, which it
already has and which is currently red for a real reason.

**A peer's sweep commit captured this step's working tree mid-flight.** The
contract, model, manifest and three test modules were committed under a
registry-sweep subject that describes none of them. Nothing was lost and
nothing was reverted, but the change did not land as one attributable commit,
and a later reader looking for why the command tuple disappeared will not find
it at that subject.

**Two out-of-scope test modules had to move with the field.** Removing a model
field is not separable from its consumers, so the entrypoint drift gate and the
login-gated exemption anchor were updated in the same change. The second was
already consistent when reached, most likely repaired by whoever ran into the
captured commit.

**One rough edge left standing.** When an entire family is undeclared the
accumulated refusal also lists every one of its leaves as unaccounted, so a
single structural fault can produce a very long message. It is complete and
correct rather than wrong, and suppressing the consequential lines risks hiding
genuine per-leaf gaps, so it was left as it is and recorded here instead.
