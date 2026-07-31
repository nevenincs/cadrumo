---
tags:
  - '#research'
  - '#verification-reconcile-when-present'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:004ed341f50ea44cda4ff666d2a73a6fa223c52e84363a3dcc9c024cd0fb4c17'
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
  `src/aeat/domain/calculations/registry/_schema.py:429` and
  `src/aeat/domain/calculations/registry/_schema.py:454`.
- The folded policy keeps the safety boundary explicit. `RegistryVerificationPolicy`
  documents `computed_casilla_ids` as coverage-gated targets and
  `reconcile_when_present_casilla_ids` as value-reconciled-when-printed targets
  excluded from coverage. `RegistrySnapshot.verification_policy()` unions both
  sets independently while preserving the max `min_coverage` fold over only the
  coverage class. Sources:
  `src/aeat/domain/calculations/registry/_schema.py:1322` and
  `src/aeat/domain/calculations/registry/_schema.py:1384`.
- Registry validation defends the new field. Reference validation checks every
  `reconcile_when_present_casilla_ids` entry against declared casillas, and the
  surface validator reports unknown reconcile-when-present casillas beside the
  existing computed-casilla check. Sources:
  `src/aeat/domain/calculations/registry/_validate_references.py:238` and
  `src/aeat/domain/calculations/registry/_validate_surfaces.py:161`.
- The verification loop consumes the field without changing coverage semantics.
  `verify_declaracion` reconciles extracted values against
  `policy.computed_casilla_ids | policy.reconcile_when_present_casilla_ids`, so
  a present situational casilla can still surface a filed-vs-engine divergence.
  Coverage is then computed by `_compute_coverage` using only
  `policy.computed_casilla_ids`; the reconcile-when-present set never enters the
  denominator. Sources: `src/aeat/application/verification/_verify.py:166`,
  `src/aeat/application/verification/_verify.py:189`, and
  `src/aeat/application/verification/_verify.py:378`.
- The completeness invariant is live. `test_every_computed_casilla_is_enrolled_in_a_verification_contract`
  loads the committed registry and fails when any computed casilla is in neither
  `computed_casilla_ids` nor `reconcile_when_present_casilla_ids`, making the
  "every computed casilla is reconcilable" rule durable without weakening
  coverage. Source:
  `src/aeat/domain/calculations/registry/tests/test_every_computed_casilla_enrolled.py:1`.
- Behavioral regression coverage proves the class is not dormant. The M130 clean
  filing stays `VERIFIED` with `coverage == 1.0` while carrying a
  reconcile-when-present expectation, and a filed divergent value for casilla
  `15` drives `NEEDS_REVIEW`. Source:
  `src/aeat/application/verification/tests/test_verify.py:130` and
  `src/aeat/application/verification/tests/test_verify.py:138`.
- No new ADR or implementation plan is recommended from this bridge. The live
  implementation matches the accepted ADR's boundary: situational casillas are
  reconciled when present, always-present finals keep their coverage gate, no
  coverage floor was weakened, and no dormant reconcile-when-present path was
  found in this pass.
