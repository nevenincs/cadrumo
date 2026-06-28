---
tags:
  - '#exec'
  - '#binding-resolver-contract-unification'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S17'
related:
  - "[[2026-06-26-binding-resolver-contract-unification-plan]]"
---




# Extend the phase-2.1 mesh parity gate to assert the disposition registry covers every BindingSourceKind member and equals the union of enrolled resolver owned_sources, reading the LIVE mesh sets at run time with no hard-coded dispositions so r2's newly-enrolled withholding source is reflected automatically, making no-dormant-source-resolvers enforceable across the union

## Scope

- `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py`

## Description

- Extend the phase-2.1 mesh parity gate with the disposition-registry assertions: the registry covers every `BindingSourceKind` member; the ENROLLED partition equals `_BUCKET_AGGREGATION_OWNED_SOURCES` exactly (the union the ADR mandates); the DEFERRED partition equals `DEFERRED_SOURCE_KINDS`; the RESERVED partition equals `RESERVED_SOURCE_KINDS`; and the three dispositions are a total disjoint cover.
- Re-point the existing reserved carve-out in the test at the canonical `RESERVED_SOURCE_KINDS` so the test no longer re-lists the members.

Modified files: `src/aeat/application/modelo/tests/test_binding_source_kind_mesh_parity.py`.

## Outcome

Landed in the P04 commit `9e59719a9`. The gate now reads the LIVE mesh sets at run time with no hard-coded dispositions, so r2's newly-enrolled withholding source (and the folded profile / borrador) are reflected automatically; a drift between the registry and the enrolled owned_sources fails the gate. This makes no-dormant-source-resolvers enforceable across the union. The extended gate plus the binding + E2E suites green; collect-only clean.

## Notes

The parity test is clean of peer WIP, so it was staged with a direct explicit-pathspec `git add`. The new disposition assertions are anti-tautological: the total-disjoint-cover assertion would fail if any member silently fell out of all three partitions.
