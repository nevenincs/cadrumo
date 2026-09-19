---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:8ef9ceb6b8666638328d815c5255609e5b29a61d4b3f15e8c3e959c75d565413'
step_id: 'S15'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Use the shared action resolver for MCP action projection

## Scope

- `src/cadrumo/application/operator_surface/__init__.py`
- `src/cadrumo/entrypoints/mcp/_input_schema.py`
- `src/cadrumo/entrypoints/mcp/_tools.py`
- `src/cadrumo/entrypoints/mcp/tests/test_action_projection.py`
- `src/cadrumo/entrypoints/mcp/tests/test_client_handshake.py`

## Description

- Locate the MCP descriptor, live Click input-schema, shared catalogue resolver,
  and canonical envelope wire through calibrated semantic discovery and exact
  source confirmation.
- Promote the reconciliation inventory inputs through their owning application
  facade so the MCP adapter consumes no cross-package private module.
- Build immutable MCP action capabilities only from shared
  `ResolvedCatalogueAction` evidence and index deterministic tuples by the
  canonical target command key.
- Join the complete exposed result/input-schema identity sets and fail closed on
  duplicate rows, mapping/model mismatches, ambiguous Click paths, orphan action
  targets, and insufficient required-input source declarations.
- Preserve distinct action identities that legitimately share a target command
  without overwriting either capability.
- Project capabilities as a namespaced extension on the target tool's real JSON
  input schema, without predicates, runtime values, localized prose, or invented
  manifest applicability.
- Replace the stale hand-authored MCP Notice schema with the canonical generated
  `Notice` and `ErrorEnvelope` models, exposing typed `action` and removing the
  retired `suggestion` compatibility field.
- Prove the projection through production Click and result schemas, SDK tool
  adaptation, an initialized in-memory MCP `tools/list` session, and the shared
  output-envelope contract.
- Close the independent Terra xhigh review's mapping-identity and wire-evidence
  findings with discriminating real-schema regressions.

## Outcome

Every entry in the canonical application action catalogue now resolves through
the S14 operator-surface resolver before MCP advertises it. The resulting strict
capability retains the stable action ID, canonical target key, resolved Click
path, live required inputs, and canonical argument-source specifications. MCP
groups those capabilities on the target tool schema in deterministic action-ID
order; it does not claim which condition or scenario makes an action applicable.

The MCP output schema now derives Notice and ErrorEnvelope definitions from the
canonical wire models. Actual tools/list output carries the action-capability
extension, exposes `action` in notices, and contains no `suggestion` field.

Post-review focused proof passed 12 integration tests. The final frozen
MCP/live selection passed 95 integration tests, and the adjacent action/resolver
contracts passed 59 tests. Ruff check and format passed on every S15 path, and
targeted BasedPyright reported zero errors, warnings, and notes. The independent
audit closed one medium exact-identity finding and one low wire-proof finding;
no review item remains open.

## Notes

- No production `ManifestActionProfile` declaration exists yet, so this Step
  deliberately publishes capabilities only and does not fabricate condition or
  scenario applicability ahead of the producer migrations in W03 and later.
- The full repository BasedPyright run reached one unrelated peer-owned unused
  import in `application.user_profile`; every S15 path remained clean.
- The import-hygiene gate passed 14 tests and retained the same five broader-tree
  failures recorded at S14: three unrelated production private imports and six
  unrelated/test-contract private reaches. No S15 path appears in the violation
  set.
- The operator-surface facade already carried uncommitted S13/S14 exports. S15
  added only the five reconciliation inventory exports required by the public
  resolver input and preserved every peer line.
- No commit was made in the shared worktree. The frozen zero-byte Git index lock
  remains governed by the repository's absolute prohibition on modifying any
  file under `.git`.
