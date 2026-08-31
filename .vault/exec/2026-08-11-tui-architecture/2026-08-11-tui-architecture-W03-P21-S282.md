---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a892987fb4069af1b3e75ef847c47c2ff730fead59fde454cbe3335b50890a43'
step_id: 'S282'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Reconcile the two producers of ModeloWorkspaceSchemaIdentityV1.field_manifest_digest, which the edit baseline computes over the calculation completeness manifest while the Workspace contributor computes it over the generated field-classification manifest, so one typed field on one shared record does not carry two meanings that compare unequal for the same revision: rule which manifest the field names, repoint or rename the other producer, and amend both governing decision records in the same change

## Scope

- `src/cadrumo/application/modelo/_edit_services.py`
- `workspace_models.py`
- `workspace_manifest.py`
- `the amended modelo-workspace-interface and registry-api-gate ADRs`
- `and a focused cross-producer digest equality test`

## Changes

- `M` `.vault/adr/2026-08-24-modelo-edit-contract-adr.md`
- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md`
- `M` `src/cadrumo/application/modelo/_edit_models.py`
- `M` `src/cadrumo/application/modelo/_edit_services.py`
- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_models.py`
- `M` `src/cadrumo/application/modelo/tests/test_edit_services.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py src/cadrumo/application/modelo/tests/test_revision_persistence_guarded_writes.py src/cadrumo/application/modelo/tests/test_edit_commit_point_guard.py src/cadrumo/application/modelo/tests/test_edit_execution.py src/cadrumo/application/modelo/tests/test_edit_contract.py src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py src/cadrumo/adapters/persistence/profile/tests/test_modelos_edit_receipts.py src/cadrumo/application/modelo/tests/test_workspace_models.py src/cadrumo/application/modelo/tests/test_workspace_producers.py src/cadrumo/application/modelo/tests/test_workspace.py -q -n 0 -m "integration or unit"` -> `pass` (125 passed, 1 pre-existing unrelated failure confirmed via `git show HEAD` diff-free comparison: a benchmark source-snapshot fixture under `dev/benchmarks/cli/.baseline-source-snapshot/` predating this Step)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/modelo/_edit_models.py src/cadrumo/application/modelo/_edit_services.py src/cadrumo/application/modelo/tests/test_edit_models.py src/cadrumo/application/modelo/tests/test_edit_services.py` -> `pass` (workspace.py carries 4 pre-existing unrelated lint findings confirmed present on HEAD before this Step via `git show`)

## Notes

Decision: RENAME, not converge. `_edit_services.py`'s producer digests
`CalculationCompletenessManifest` (a tax-semantic completeness declaration);
`workspace.py`'s S278 producer digests a field-CLASSIFICATION manifest over
the public registry TYPE denominator. Neither should be repointed at the
other's source -- they answer independent questions and a real change to one
axis must not move or fail to move the other. `ModeloEditBaselineV1.schema_identity`
is now typed `ModeloEditSchemaIdentityV1` (new, `_edit_models.py`), carrying
`completeness_manifest_digest` -- never `field_manifest_digest`.
`ModeloWorkspaceSchemaIdentityV1.field_manifest_digest` is unchanged and
remains exclusively the S278 concept. A real cross-producer test
(`test_edit_schema_identity_is_never_confused_with_the_workspace_field_manifest_digest`)
runs both real producers over the same registry revision, proves the two
digests differ, proves the two types no longer share the field name, and
proves mutating only the completeness manifest moves one digest while
leaving the other, computed from an unrelated input, unchanged.

Amended `.vault/adr/2026-08-24-modelo-edit-contract-adr.md` (D2's governing
record for `_edit_services.py`'s producer) and
`.vault/adr/2026-08-24-tui-registry-api-gate-adr.md` (the S278 field-manifest
governing record for `workspace.py`'s producer) -- these are the two ADRs
that actually govern the two real producing modules, confirmed by reading
both ADRs' bodies. The Step's own scope named "modelo-workspace-interface and
registry-api-gate ADRs"; `2026-08-24-tui-modelo-workspace-interface-adr.md`
names neither `ModeloWorkspaceSchemaIdentityV1` nor `field_manifest_digest`
anywhere in its body, so it is not a governing record for this defect. This
is the same class of Step-text-vs-code mismatch this campaign has corrected
several times already (S137's `__init__.py`, S275/S281's binding-source
assumptions).
