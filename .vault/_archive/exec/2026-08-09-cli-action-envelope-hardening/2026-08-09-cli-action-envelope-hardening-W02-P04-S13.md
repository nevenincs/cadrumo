---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:e0c1ae9cb647f53c2e3c3c9465147b57b85e1983de4e3eb71c042ee51a0901c8'
step_id: 'S13'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Add manifest action-profile records that reference condition and action identities without predicates

## Scope

- `src/cadrumo/application/operator_surface/_models.py`

## Description

- Locate the canonical manifest and action-catalogue boundaries with calibrated
  semantic code and ADR searches, then confirm the live symbols and target-file
  ownership with exact reads and `rg`.
- Add one strict immutable manifest profile for each canonical subject,
  condition, and scenario identity.
- Preserve the exact recovery association through one action reference or one
  explicit no-recovery outcome, without predicates or presentation data.
- Export the record through the owning package facade and prove the contract
  through direct production imports.

## Outcome

`ManifestActionProfile` now represents the canonical live-coverage key
`(subject_leaf_key, condition_id, scenario_id)` and exposes it through
`identity`. Each record accepts exactly one canonical `ActionReference` or one
explicit `NoRecoveryOutcome`. The model is strict, frozen, and extra-forbidding;
its declared fields cannot carry a predicate, runtime evidence or argument
value, binding-resolution result, localized prose, target command key, or CLI
command string.

The public operator-surface facade exports the new record. The focused contract
tests import production models and prove actionable and safety outcomes, exact
association cardinality, namespaced identity enforcement, frozen
serialization, and refusal of policy, presentation, command, and runtime-value
fields. Catalogue lookup, live input-schema resolution, binding sufficiency,
manifest assembly, and MCP projection remain deliberately absent for the next
two accepted Steps.

## Verification

```text
uv run --no-sync vaultspec-rag search "operator surface manifest declarative leaf capability action profile condition identity only:prod" --type code --port 8766 --timeout 120
Exit code: 0; canonical production cluster: operator-surface manifest

uv run --no-sync vaultspec-rag search "application guard condition identifiers canonical action catalogue manifest references without predicates only:prod" --type code --port 8766 --timeout 120
Exit code: 0; top result: canonical operator action catalogue

uv run --no-sync vaultspec-rag search "application-owned precondition verdicts manifest action profiles schema-resolved action chains" --type vault --doc-type adr --port 8766 --timeout 120
Exit code: 0; top result: accepted CLI action-envelope ADR

uv run --no-sync pytest -q -o addopts='' src/cadrumo/application/operator_surface/tests/test_action_profiles.py
10 passed in 0.86s

uv run --isolated --locked pytest -q -o addopts='' src/cadrumo/application/operator_surface/tests/test_action_profiles.py src/cadrumo/application/operator_surface/tests/test_contract.py src/cadrumo/application/operator_surface/tests/test_manifest_reconciliation.py
41 passed in 29.39s

uv run --no-sync ruff check src/cadrumo/application/operator_surface/_models.py src/cadrumo/application/operator_surface/__init__.py src/cadrumo/application/operator_surface/tests/test_action_profiles.py
All checks passed!

uv run --no-sync basedpyright src/cadrumo/application/operator_surface/_models.py src/cadrumo/application/operator_surface/__init__.py src/cadrumo/application/operator_surface/tests/test_action_profiles.py
0 errors, 0 warnings, 0 notes

git diff --check -- src/cadrumo/application/operator_surface/_models.py src/cadrumo/application/operator_surface/__init__.py src/cadrumo/application/operator_surface/tests/test_action_profiles.py
Exit code: 0
```

## Notes

- A broader collection attempt including `test_contract.py` stopped before
  S13 tests executed because the shared environment could not import
  `cryptography.hazmat._oid` after a concurrent dependency merge. The same
  41-test selection then passed in a lockfile-pinned isolated environment,
  proving the source change without mutating the shared `.venv`.
- The shared worktree contains concurrent S12 migration edits outside the three
  S13 source/test files. They were preserved without staging, reverting, or
  environment mutation.
- S14 still owns action-catalogue lookup, live command/input-schema resolution,
  duplicate/orphan profile reconciliation, and binding sufficiency. S15 still
  owns MCP projection.
