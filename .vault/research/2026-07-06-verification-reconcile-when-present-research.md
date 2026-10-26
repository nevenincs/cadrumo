---
tags:
  - '#research'
  - '#verification-reconcile-when-present'
date: '2026-07-06'
modified: '2026-10-03'
body_hash: 'sha256:4c2958f55ac40bba361c2d9b6a0c23fc3387f7474b8a7d1820e166cf34de7672'
related: []
---

# `verification-reconcile-when-present` research: `coverage-safe situational casilla reconciliation grounding`

This research backfills the same-feature grounding for the accepted
`2026-07-01-verification-reconcile-when-present-adr`. It re-read the ADR,
searched the vault and code indexes with `vaultspec-rag`, and confirmed the
current schema, validators, verification loop, coverage calculation, and tests
with targeted grep/read slices before recording the bridge.

## Findings

- The accepted decision resolves a structural coverage/reconciliation conflict.
  The old `computed_casilla_ids` class meant "reconcile this value" and "require
  this value for 100 percent coverage"; enrolling situational computed casillas
  would have lowered coverage for legitimate filings that omit them. The chosen
  split adds a class that reconciles a casilla only when the filing prints it,
  without placing it in the coverage denominator. Source:
  `2026-07-01-verification-reconcile-when-present-adr`, Problem Statement and
  Considered options.
- The schema carries the split as first-class registry data. Each
  `VerificationExpectationDefinition` has `reconcile_when_present_casilla_ids`;
  it is unique, disjoint from `computed_casilla_ids`, and participates in the
  reconciled set used by `externally_grounded_casilla_ids`. Sources:
  the former source file and

- The folded policy keeps the safety boundary explicit. `RegistryVerificationPolicy`
  documents `computed_casilla_ids` as coverage-gated targets and
  `reconcile_when_present_casilla_ids` as value-reconciled-when-printed targets
  excluded from coverage. `RegistrySnapshot.verification_policy()` unions both
  sets independently while preserving the max `min_coverage` fold over only the
  coverage class. Sources:
  the former source file and

- Registry validation defends the new field. Reference validation checks every
  `reconcile_when_present_casilla_ids` entry against declared casillas, and the
  surface validator reports unknown reconcile-when-present casillas beside the
  existing computed-casilla check. Sources:
  the former source file and

- The verification loop consumes the field without changing coverage semantics.
  `verify_declaracion` reconciles extracted values against
  `policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids`, so
  a present situational casilla can still surface a filed-vs-engine divergence.
  Coverage is then computed by `_compute_coverage` using only
  `policy.computed_casilla_ids`; the reconcile-when-present set never enters the
  denominator. Sources: the former source file,
  the former source file, and

- The completeness invariant is live. `test_every_computed_casilla_is_enrolled_in_a_verification_contract`
  loads the committed registry and fails when any computed casilla is in neither
  `computed_casilla_ids` nor `reconcile_when_present_casilla_ids`, making the
  "every computed casilla is reconcilable" rule durable without weakening
  coverage. Source:

- Behavioral regression coverage proves the class is not dormant. The M130 clean
  filing stays `VERIFIED` with `coverage == 1.0` while carrying a
  reconcile-when-present expectation, and a filed divergent value for casilla
  `15` drives `NEEDS_REVIEW`. Source:
  the former source file and

- No new ADR or implementation plan is recommended from this bridge. The live
  implementation matches the accepted ADR's boundary: situational casillas are
  reconciled when present, always-present finals keep their coverage gate, no
  coverage floor was weakened, and no dormant reconcile-when-present path was
  found in this pass.
