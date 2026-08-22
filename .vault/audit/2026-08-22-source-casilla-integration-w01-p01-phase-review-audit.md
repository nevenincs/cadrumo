---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:3d20067135e64a118c5b5ae84d23fe915f1f6603f678820b7915890e4055d38d'
related:
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-plan]]"
  - "[[2026-08-22-source-casilla-integration-research]]"
---

# `source-casilla-integration` audit: `W01.P01 census contract phase review`

## Scope

Reviewed the final tree delivered by `W01.P01.S01` through `W01.P01.S05`,
including the initial identity and governance commits, the S03 corrective chain
through `fdaa3930ad`, the public facade in `a31df525b9`, and the focused test
suite in `497a6e648c`. The review checked the accepted source-casilla integration
ADR and plan, prior step audits, core placement and facade ownership, closed
taxonomy behavior, deterministic expiry, connected-proof relational identity,
live-authority responsibilities, security posture, and test independence.

The focused source-connectivity suite passes 34 tests, Ruff passes over the
owner module, facade, and test module, and the facade maps all sixteen public
owners to the canonical module. A tree-wide deterministic-clock gate is
currently red on concurrent user-profile changes outside this phase; it reports
no source-connectivity offender. No production or test source was modified by
this review.

## Findings

### authority-test-double | high | Connected admission is tested only through a configurable fake authority

`_ProofAuthority` is a hand-built test double whose enrollment, workflow, and
digest answers are supplied by the test itself. It does not consult the real
source-disposition mesh, supported command catalogue, repository content, or
encrypted `CalculationRevision` storage. It also ignores the source object,
resolver, and calculation-revision portions of the connection when answering
enrollment, and discards the whole connection when answering workflow support.
The tests would therefore remain green if exact connection identity ceased to
reach those authority decisions, provided the source-kind and prose ids retained
their current values. This violates the project's no-fakes rule and does not
provide the required non-tautological proof that an invented or deferred
connected claim is rejected by production authorities. The core protocol and
fail-closed requirement for an authority are sound seams, but S05 has not yet
proved their real implementation.

### https-grounding-trust-boundary | medium | External grounding still has no safe dereference policy

The prior S02 audit's HTTPS finding remains open. URL validation rejects
non-HTTPS and userinfo-bearing references, but still admits local/private hosts,
query secrets, and arbitrary authorities. This is safe only while the value is
treated as an operator-opened citation and never automatically dereferenced. A
future census loader or evidence refresher must establish an explicit host,
network, redirect, and credential policy before fetching these references.

### final-contract-shape | low | The production contract is closed, deterministic, relational, and facade-owned

The final model exposes exactly the ADR's eight dispositions, requires grounding
and ownership, makes blocked states finite and attributable, evaluates expiry at
an explicit date seam, and couples `connected` bidirectionally to a complete
proof. Candidate, source kind, source object, resolver, calculation revision,
evidence role, evidence digest, and operator identity are structurally joined.
Direct connected-row construction without an authority fails closed. The module
depends only on core-owned types, performs no I/O or ambient clock read, and its
sixteen owners are lazily exported through the sole core facade.

### prior-corrective-findings | low | Earlier S01-S04 high findings remain closed in the final production tree

The final tree retains strict booleans, deterministic expiry, typed bounded
follow-up, locator kinds, shared connection identity, role-specific executable
evidence, mandatory authority validation, and complete facade exposure. Focused
mutation and refusal tests cover unknown dispositions, missing actionability,
identity divergence, wrong evidence roles, changed digests, deferred source
kinds, unsupported commands, and non-test evidence shapes. None of the earlier
corrected production-contract findings regressed.

## Recommendations

- Close `authority-test-double` before issuing the W01.P01 phase summary. Add or
  reuse a production authority implementation backed by the canonical enrolled
  source mesh, supported operator catalogue, real repository digest lookup, and
  encrypted calculation-revision proof, then exercise it without mocks, fakes,
  stubs, monkeypatching, skips, or xfails. The tests must bite when any exact
  candidate/source/resolver/revision/workflow identity is altered.
- Keep the current core protocol as the dependency-inversion seam; do not move
  application, filesystem, CLI, or persistence policy into core to close the
  test finding.
- Resolve `https-grounding-trust-boundary` before any automated dereference.
  Until then, document and enforce that HTTPS values are passive citations.
- Preserve the final closed taxonomy, deterministic expiry API, strict proof
  assertions, relational identity validators, and canonical lazy facade.
- W01.P01 is not ready for a phase summary and W01.P02 should not proceed while
  the HIGH test-validity finding remains open. The unrelated user-profile clock
  failures do not belong to this phase and should remain with their owner.
