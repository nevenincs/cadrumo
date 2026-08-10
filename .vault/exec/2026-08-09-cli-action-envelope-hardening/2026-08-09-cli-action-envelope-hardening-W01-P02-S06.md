---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:9fb3e6f2b67f2044fd3583999a5808628186ade12e0ccaa652a6bcf2f3b416e1'
step_id: 'S06'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Build the identity reconciliation across leaves, schemas, manifest declarations, policies, and MCP exposure

## Scope

- `src/cadrumo/application/operator_surface/_manifest.py`

## Description

- Add strict application-owned rows for live leaves, result schemas, input schemas, mounted families, profile policies, MCP exposure, and attributable exclusions.
- Reconcile the rows by stable subject identity while deriving family ownership only from canonical paths and retaining aliases as alternate paths.
- Fail duplicate, orphan, ambiguous, missing, silently excluded, and policy-conflicting observations rather than emitting an incomplete manifest.
- Add pure-contract regressions for canonical aliases, root-status callbacks, exclusions, provenance, orphan families, and policy-filtered MCP exposure.
- Apply the S06 identity-reconciliation review remediation for root callbacks, orphan mounted families, and whitespace-only provenance.

## Outcome

The operator-surface application layer now produces a typed, fail-closed reconciliation report instead of trusting independently maintained action hints. The S06 review found and remediated three gaps before closure: the `root.status` callback identity, unused mounted-family declarations, and blank evidence provenance.

## Verification

`uv run --no-sync pytest -q src/cadrumo/application/operator_surface/tests/test_manifest_reconciliation.py src/cadrumo/application/operator_surface/tests/test_contract.py`

`30 passed in 22.70s`

`uv run --no-sync ruff check src/cadrumo/application/operator_surface/_manifest.py src/cadrumo/application/operator_surface/tests/test_manifest_reconciliation.py`

`All checks passed!`

`uv run --no-sync basedpyright src/cadrumo/application/operator_surface/_manifest.py src/cadrumo/application/operator_surface/tests/test_manifest_reconciliation.py`

`0 errors, 0 warnings, 0 notes`

## Notes

No index, commit, lock-file, or unrelated worktree mutation was performed during this Step.
