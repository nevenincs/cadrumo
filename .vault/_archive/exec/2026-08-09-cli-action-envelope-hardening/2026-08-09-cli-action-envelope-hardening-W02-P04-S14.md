---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:30d1a8c305acb12386eaa084895b86a8c15a6ba2b2d485fb4d205e80b55480c4'
step_id: 'S14'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Resolve catalogue actions against live command and input schemas and reject insufficient bindings

## Scope

- `src/cadrumo/application/operator_surface/_manifest.py`
- `src/cadrumo/application/operator_actions/__init__.py`
- `src/cadrumo/application/operator_surface/__init__.py`
- `src/cadrumo/application/operator_surface/tests/test_action_resolution.py`
- `src/cadrumo/application/operator_surface/tests/test_action_resolution_live.py`
- `src/cadrumo/entrypoints/mcp/__init__.py`

## Description

- Locate the canonical catalogue, manifest reconciliation, and live input-schema
  owners through calibrated semantic discovery and exact symbol confirmation.
- Promote the existing catalogue declarations and live input-schema builder
  through their owning package facades.
- Resolve every catalogue target against exact live leaf, result-schema, and
  input-schema identities, including currently unreferenced catalogue entries.
- Reject missing required argument source specifications while retaining extra
  specifications whose optional-input validity is outside the S06 projection.
- Resolve manifest profiles by exact subject, condition, scenario, and action
  identity while preserving explicit typed no-recovery outcomes.
- Prove duplicate, orphan, ambiguous, unknown, schema-mismatched, and
  insufficient-source failures through direct production-model tests.
- Materialize the production Click tree and result-schema registry to validate
  every canonical action target against live required inputs.

## Outcome

`ResolvedCatalogueAction`, `ResolvedManifestActionProfile`, and
`ManifestActionResolution` now retain deterministic resolution evidence without
becoming a second action authority. `resolve_action_catalogue` validates the
entire canonical catalogue against the reconciled live surface;
`resolve_manifest_action_profiles` joins declarative failed-condition profiles
to those resolved actions or to their explicit `NoRecoveryOutcome`.

The resolution layer contains no predicate, localized prose, CLI command
string, runtime argument value, or MCP action projection. Extra source
specifications remain accepted because the live application projection exposes
the complete required-name set, not the optional-name universe.

Focused unit proof passed with nine tests and the live Click/schema-registry
proof passed with one integration test. The adjacent S09-S14 owner selection
passed 62 tests, and all operator-action contract tests passed 39 tests. Focused
Ruff check and format validation passed, BasedPyright reported zero errors and
warnings, and the independent Terra xhigh review closed its only low formatting
finding after the out-of-step file was restored exactly to HEAD.

## Notes

- The public operator-surface facade already carried completed uncommitted S13
  exports. The S14 additions were narrowly additive and preserved those lines.
- The broader import-hygiene gate passed 14 tests and failed five after the S14
  live test's private reach was removed. Its remaining failures are three
  production private imports and six test-only imports from concurrent or prior
  work, including the unchanged S07 operator-surface contract test; no S14 path
  remains in the violation set.
- S15 remains responsible for projecting the shared resolved action through
  MCP. This Step added only public access to the existing live input-schema
  builder.
- No commit was made in the shared worktree.
