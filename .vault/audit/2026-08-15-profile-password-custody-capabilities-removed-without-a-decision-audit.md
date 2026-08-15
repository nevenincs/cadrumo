---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:9743bc4b166d7bb013039e03132b847f02f605c07584d9af215f134ee3831d4c'
related: []
---

# `profile-password-custody` audit: `capabilities removed without a decision`

## Scope

Two operator capabilities are absent from every surface, neither retirement is
recorded anywhere in the decision corpus, and in both cases an accepted decision
record still governs the capability while shipped surfaces still promise it.
Both were found while investigating something else, and both require an operator
ruling rather than an engineering one.

## Findings

### credential-rotation-has-no-surface | critical | The profile passphrase cannot be changed by any route

An operator cannot rotate their profile credential. The command does not resolve;
there is no application-layer rotation function; and the custody package exposes
only unorchestrated primitives -- envelope creation, material wrapping, password
validation -- with nothing built on them.

This application's load-bearing guarantee is that all sensitive financial data
lives solely under that credential. A credential that cannot be rotated cannot be
retired after exposure, cannot be changed when shared, and cannot be strengthened.
The absence is therefore a property of the security posture rather than a missing
convenience.

The orphaned test that asserted it is the cheapest surviving specification: its
documentation describes three passphrases riding one bounded secret-input object.
That assertion is deliberately left RED with an inline comment stating the
capability is absent and the question open, so the gap cannot be closed by
deleting a test.

### scripted-profile-creation-dead-ends | critical | Two layers hold contradictory intent, in live code

Creating a profile non-interactively refuses unconditionally, and the refusal was
introduced silently inside a commit whose message described custody authority and
never mentioned retiring a creation door. That commit is already recorded as the
traced origin of eight separate defects in this campaign.

**The retirement is unrecorded.** Searching the whole decision corpus for the
refusal's own wording returns nothing -- no decision record, no audit, no
execution record.

**An accepted decision record still governs it.** The profile setup-flow record
remains `accepted` rather than superseded and explicitly governs the creation
verb, including that a re-run resolves to resume and that several doors converge
on one flow. The campaign's own rollup record covers custody mechanics and never
touches the creation door.

**The replacement does not reach the scripted case.** Registration with
credentials is a genuine non-interactive function at the application layer, but
its only operator surface is a full-screen interactive one. And the routing layer
deliberately sends the scripted invocation AWAY from that screen: its rule
returns false for scripted invocations, and its own documentation states that
"what still belongs to the flow is the genuinely non-interactive contract". So
the router documents scripted creation as the contract, routes to it, and the
flow refuses it.

That contradiction is in **live executable code with a load-bearing docstring**,
not in prose making a stale claim -- which distinguishes it from the five
documentation defects this campaign has already found and fixed.

The consequence is measurable: two hundred and ninety-four tests assert this
capability, roughly twenty-three percent of the entire integration lane's
failures, and they are currently the only executable evidence in the tree that
scripted creation was ever the contract.

## Recommendations

Both need an operator decision, and neither can be closed by an implementer
without ratifying a change nobody recorded.

For scripted creation the reviewer recommends RESTORE, on the grounds that the
router's documented contract, the shipped flags, the shipped help text in all
four catalogues and the published documentation all still promise it, and that a
headless creation door is what automated operators require. The alternative is a
formal retirement -- which needs an amendment superseding the setup-flow record's
creation clauses, and which under this project's rules is not self-executing: the
implementing rows must be opened in the same action, and the router documentation,
the locale help strings and the published documentation swept with it.

Do not rewrite the two hundred and ninety-four tests before that decision.
Retiring them would ratify the drift and destroy the last executable evidence of
the contract.

The common shape is worth recording independently of either outcome: **a
capability disappearing inside a commit whose subject describes something else,
leaving an accepted decision record still governing it and every operator-facing
surface still promising it.** Both instances were found while investigating an
unrelated failing test, which means the detection was accidental in both cases
and there is no standing mechanism that would have caught either.
