---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:7fb27a7b831381cfd2f5cb7dea7638a5c801d5ef6d6a32a4524d7313c6c669f8'
related:
  - "[[2026-08-22-source-casilla-integration-adr]]"
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# `source-casilla-integration` audit: `W01.P01.S02 core contract review`

## Scope

Commit `084465c18f` was audited against the accepted source-casilla integration
ADR, `W01.P01.S02` of the implementation plan, the deterministic clock rule,
and the census requirement that unresolved rows carry re-fetchable grounding,
ownership, an explicit review condition, expiry where deferred, and a linked
bounded follow-up. The review is limited to the S02 typed grounding and census
row contract; the separately authorized connected-slice proof remains S03 work.

## Findings

### ambient-clock-validation | high | Model validity changes with wall-clock date and violates the canonical clock gate

`SourceConnectivityCensusRow._require_actionable_unresolved_state` calls
`date.today()` while validating blocked rows. The same serialized census row can
therefore load successfully on one day and fail on the next, replay cannot pin the
decision date, and Madrid civil-date authority is bypassed. The production AST
gate `test_no_bare_wall_clock_reads_in_production` fails on this exact call. A
durable census model must remain deterministic at parse time; expiry posture
belongs in an explicit, caller-supplied `as_of` evaluation or ratchet operation,
not ambient model construction.

### follow-up-is-unstructured-prose | high | The declared bounded follow-up is neither linked nor temporally bounded

`bounded_follow_up` is the same general-purpose text alias used for summaries
and owners. Its only bound is 500 characters, so values such as `investigate
later` satisfy blocked and candidate rows without an action identity, accountable
owner, due date, lifecycle link, or completion criterion. This does not implement
the ADR's linked bounded-follow-up contract and cannot support the later ratchet
that must detect expired deferrals without linked action. The row-level `owner`
does not repair the omission because it cannot identify or close a particular
follow-up action.

### grounding-locator-shape | medium | Grounding claims re-fetchability without a locator contract

`SourceConnectivityGrounding.locator` accepts every non-empty string up to 2,048
characters. Consequently `x` or `evidence somewhere` validates even though no
consumer can deterministically re-fetch it. The type should encode the supported
locator identity or scheme sufficiently for deterministic loading and later
verification, rather than relying on its docstring.

### s03-boundary | low | Connected proof is correctly kept out of the S02 change

The implementation does not pre-empt the S03 resolver-ownership, encrypted
revision-persistence, and operator-reachability proof model. A `connected` row is
temporarily constructible without that proof, but the plan explicitly assigns
refusal of unsupported connected claims to the S03/S05 contract. S03 must close
that temporary state before any census persistence or ratchet consumer is added.

## Recommendations

- For `ambient-clock-validation`, remove time-dependent validation from model
  construction and expose an explicit `as_of` expiry evaluation used by the
  census ratchet. Prove it with fixed boundary dates and the existing clock-seam
  gate.
- For `follow-up-is-unstructured-prose`, replace the prose field with a typed,
  linked action contract carrying stable action identity, responsible owner,
  deadline or other finite closure boundary, and a completion/review condition.
  Validate disposition-specific completeness structurally.
- For `grounding-locator-shape`, introduce a closed locator kind plus a validated
  canonical reference, or another typed locator model whose accepted values can
  actually be resolved by the census loader.
- Preserve the S03 boundary, then require its proof for `connected` before S05
  closes the phase. Do not begin S03 while either high-severity S02 finding is
  open.
