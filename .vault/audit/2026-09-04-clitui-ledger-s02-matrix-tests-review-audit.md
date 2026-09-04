---
tags:
  - '#audit'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:9d638bfd35494dcac6fbd825d8207fe5aaffc3169fe75e574c623ef39cfc7743'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
  - "[[2026-09-04-clitui-ledger-adr]]"
---

# `clitui-ledger` audit: `S02 matrix detector test review`

## Scope

Mandatory fresh review of plan step `W01.P01.S02` at test commit
`2f3ebbab544f6031d9d3687b6d90ad081ef3ddc0`, SHA-256
`5cabb871884d7081f943346810192f3faa177229c8fa5c8d47828808b0c39892`,
against the accepted `clitui-ledger` ADR, research, reference census, plan,
prior S01 audit, and current S01 contract commit
`7b0ae292399ae9bca3e67944f174ae7d36018c42`. The review assessed identifier
stability, live denominator completeness, legal state transitions, evidence
integrity and freshness, exact G0--G4 predicates, copied-model trust boundaries,
closed-gate reopening, assertion quality, and isolation.

The focused suite passes all 51 cases; Ruff, BasedPyright, byte-compilation, and
diff-whitespace checks are also clean. Independent adversarial probes verified
that the implementation has detector teeth for the omitted cases below, but
those probes are not durable repository tests. S02 is therefore not accepted in
the reviewed revision.

## Findings

### copied-graph-detectors | high | Canonical validation is not durably tested across every public boundary

The suite preserves the two exact prior `model_copy` exploits for an empty
attestation reviewer and an attacker-recomputed all-`NOT_APPLICABLE` row, plus a
missing census stream and invalid denominator-reopening snapshot. It does not
exercise a malformed copied observed subject, a malformed nested authority
snapshot, or those invalid graphs through
`validate_ledger_matrix_currentness` and ordered
`evaluate_ledger_capability_gates`. Weakening subject or authority
canonicalization, or validating only G0 rather than every public evaluation
boundary, can therefore survive S02. Independent probes showed the current
implementation correctly returns redacted deterministic blockers for the
subject and leaves every ordered gate open for the malformed authority graph;
the gap is missing regression protection for a previously CRITICAL trust
boundary.

### exact-gate-predicate-coverage | high | Multiple accepted hard-gate branches have no negative detector

G0 has a positive closure test but no mutation removing exact `BASELINE`
evidence from a proven applicable axis. G2 tests the backend surface and direct
backend evidence, but not the independent composition, artifact, provenance,
registry, and proof axes or their blocking gap classes. G3 removes success,
refusal, and artifact evidence, but does not detect loss of the proven CLI
surface, canonical delegation, or the four CLI-scoped blocking gap classes. G4
tests a finding on a TUI-non-applicable row, but not loss of `INSTALLED`, TUI
proof/surface state, hold enforcement, or any of the three campaign-wide parity,
reachability, and publication roles. Independent mutations confirmed each
current implementation branch opens its intended gate, so this is a test-suite
completeness defect: substantial portions of the accepted closure predicates
could regress to false closure while all 51 tests remain green.

### fixture-empty-state-masking | medium | Truthy fixture fallbacks erase explicit empty evidence input

`_matrix` selects `campaign_evidence or _campaign_evidence()`, so an explicit
empty tuple silently becomes all four happy-path coordinates. `_report` uses the
same pattern for `streams`. This makes an empty state look populated and can
prevent the most direct absence detector from being written or understood.
Optional fixture parameters must distinguish `None` from a deliberately empty
collection. Current tests work around an incomplete census with `model_copy`,
but no equivalent test exposes the campaign-evidence masking.

### review-attestation-adjudication | low | Typed acceptance is stronger than the generic review evidence role

The executor note is not a runtime contract regression. Plan step S14 requires
an independent engineering review to accept the exact frozen matrix. The typed
`LedgerMatrixAcceptanceAttestationV1` enforces an explicit `ACCEPT` ruling and
binds reviewer, canonical plan owner, matrix digest, denominator digest and
revision, and a fresh review subject. The generic
`INDEPENDENT_ENGINEERING_REVIEW` coordinate carries neither a ruling nor those
bindings, so requiring it instead would be weaker and requiring both would be
redundant. An independent probe confirmed G0 correctly closes when the generic
coordinate is absent but the typed attestation is valid. The suite should state
that substitution explicitly; its default fixture currently includes the
generic role and can leave future maintainers believing G0 consumes it. This is
an informational design adjudication and not an open LOW defect.

## Recommendations

1. For `copied-graph-detectors`, add durable mutations for invalid copied live
   subjects and nested authority snapshots through the single-gate, ordered-gate,
   and currentness entry points. Assert deterministic fail-closed results and
   rejected-value redaction.
2. For `exact-gate-predicate-coverage`, parameterize negative tests over every
   G2 axis and gap class, every G3 state/delegation/gap obligation, and every G4
   installed/state/campaign-evidence obligation. Add a G0 proven-axis mutation
   with its exact baseline role removed. Keep a positive control beside each
   gate family.
3. For `fixture-empty-state-masking`, use explicit `is None` selection in
   `_matrix` and `_report`, then add empty campaign-evidence and empty-stream
   refusal cases.
4. For `review-attestation-adjudication`, add a focused test proving that a
   valid digest-bound `ACCEPT` attestation satisfies S14 without the generic
   review coordinate, and that a generic coordinate cannot compensate for a
   missing, stale, or non-accepting typed attestation.
5. Disposition: **NOT ACCEPTED**. Open severity counts are CRITICAL 0, HIGH 2,
   MEDIUM 1, LOW 0. The LOW adjudication records that typed attestation is the
   stronger canonical review authority and is not itself an open finding.
