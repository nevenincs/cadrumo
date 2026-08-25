---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:ba8825cb27a9755cce96c084526c25440ac4d7d691fa7d14215893308f77cbb4'
step_id: 'S171'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Hard-move the complete Workspace V1 model family from application/modelo/_workspace_models.py into the sole public application/modelo/workspace_models.py defining module, atomically migrate every exact production, test, documentation, tooling, annotation, registration, dynamic-target, and receipt consumer to direct imports, delete the private module plus every Workspace-model application.modelo package binding, __all__ entry, lazy name, and re-export, and gate the application.modelo namespace as inert in the same commit, replace the single revision_assertion with required requested_revision_assertion and stored_revision_assertion axes that each carry their fixed source, optional asserted revision, and not_present, matched, or mismatched outcome, carry both axes through resolved targets and a typed mismatch refusal preserving every evaluated axis and all mismatching sources, require one identical contributor_epoch_digest across the baseline, every bounded facet, and every typed cursor, and reject the old fields without an evaluator, alias, default synthesis, compatibility parser, shim, fallback, bridge, re-export, or private-path remnant

## Scope

- `src/cadrumo/application/modelo/workspace_models.py`
- `retired src/cadrumo/application/modelo/_workspace_models.py`
- `src/cadrumo/application/modelo/__init__.py inert-namespace gate for Workspace-model bindings`
- `src/cadrumo/application/modelo/tests/test_workspace_models.py`
- `every affected production/test/documentation/tooling/annotation/registration/dynamic-target/receipt consumer`
- `docs/api/cadrumo.application.modelo.rst`
- `retired docs/api/cadrumo.application.modelo._workspace_models.rst`
- `dev/quality/regulatory_drift_dispositions.toml`
- `and focused direct-import/current-only/independent-axis/digest-consistency/package-binding/zero-remnant tests`

## Description

- Preserve the public Workspace model defining module introduced by shared relocation commit `3ec3f7908a` and delete the retired private import surface through direct consumer convergence.
- Replace the single revision assertion with required requested and stored source-fixed assertion axes and a typed mismatch-refusal arm.
- Bind the contributor epoch digest across baseline, bounded facet, and typed cursor coordinates with fail-closed equality checks.
- Regenerate the two affected API-reference stubs, update the regulatory-drift path, and prove the inert package plus active-tree fixed point.

## Outcome

- Focused integration suites passed: Workspace models 22, producer contracts 6, and field manifest 8.
- Scoped compilation, Ruff, whitespace, exact AST import, exact private-path, and semantic discovery checks passed. The AST census found five direct public-module consumers and no private import edge.
- The record remains open for independent code review; this execution does not close the plan row.

## Notes

- Shared commit `3ec3f7908a` swept the filesystem renames before the S171 consumer and schema cutover. The current commit records the direct-import and validation closure from that provenance.
- API-stub scaffolding initially produced unrelated shared-tree drift. The 234 tracked and 161 untracked non-S171 generator outputs were restored or removed using the captured pre-run clean status; only the two S171 generated stubs remain in scope.
