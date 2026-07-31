---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-17'
modified: '2026-07-19'
body_hash: 'sha256:180519e3b99f101b3ff482ea73c0206b7323367a4060e8bbbbf04626d611e2f9'
step_id: 'S24'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Assert binding validator-dispatch completeness: every BindingSourceKind member has a dispatch entry in the validator registry or a documented mesh-only deferral, so a new source kind cannot ship unvalidated

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_binding_build_validation.py`

## Description

- Add `test_every_binding_source_kind_is_validator_dispatched_or_documented_mesh_only`: a completeness gate partitioning the whole `BindingSourceKind` enum into validator-dispatched sources and an explicitly pinned documented mesh-only set.
- Pin `_DOCUMENTED_MESH_ONLY_SOURCE_KINDS = {BORRADOR, IVA_WALLET_DECISION}` — the two source kinds resolved before the registry binding mesh (a pre-mesh gate / source-mesh decision), which never appear as a `DataBindingDefinition.source` and therefore carry no per-family selector or validator.
- Assert `set(_BINDING_VALIDATOR_REGISTRY) == set(_BINDING_SELECTOR_REGISTRY)` so every legal binding source has exactly one dispatch validator and every validator has a selector model (no legal source ships unvalidated, no validator dangles).
- Assert the validator set and the mesh-only set are disjoint, and that their union covers the whole enum, so a newly added member that is classified as neither fails loudly with an instructive message naming the remedy.
- Import `_BINDING_SELECTOR_REGISTRY` alongside the existing `_BINDING_VALIDATOR_REGISTRY`.

## Outcome

Current tree: 27 `BindingSourceKind` members = 25 validator-dispatched (validator/selector parity exact) + 2 documented mesh-only. The pre-existing `test_dispatch_table_covers_every_validated_family` only checked the test's own `_FAMILY_CASES` were covered; this new gate closes the gap where a NEW registry-declarable source could compile and silently skip build-time binding validation. Non-vacuous by construction: a new unclassified member makes `frozenset(BindingSourceKind) - validated - mesh_only` non-empty. 16 tests pass in the file; ruff clean.

## Notes

No production code changed — this is a coverage-gap gate only, per the plan's "turn honestly-flagged coverage gaps into non-vacuous gates". Companion to the `binding-validation-single-contract` and `binding-source-kind-single-taxonomy` disciplines. git-diff-gated the test file clean at HEAD before editing (last touched 5 days ago by the package rename, no peer WIP).
