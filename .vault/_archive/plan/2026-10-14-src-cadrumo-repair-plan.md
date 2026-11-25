---
tags:
  - '#plan'
  - '#src-cadrumo-repair'
date: '2026-10-14'
tier: L1
related:
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-08-14-test-harness-sanity-successor-adr]]'
  - '[[2026-06-05-test-topology-refactor-adr]]'
  - '[[2026-07-25-bucket-event-payload-bounding-adr]]'
modified: '2026-10-17'
body_schema: body-v2
body_hash: 'sha256:d0e3bc991a37f9aaa8c3ee5ce1ee0177fcf33bbc2904c52b6e95035dbbdc9c06'
---

# `src-cadrumo-repair` plan

## Description

Approved 2026-10-14

Authorization: the user requested continued fixes to src/cadrumo after the source-scoped unit run recorded 50 failures and 41 errors. Repair root causes and necessary ownership references while retaining behavioral coverage and protective gates. Preserve concurrent changes and the completed registry-wire and actor-bound fixes.

Existing accepted import-centralization, test-topology and test-harness-sanity decisions govern S01-S02: canonical defining modules, inert namespaces, user-confirmed TUI ownership inside cadrumo and separate runtime package ownership, narrow fixture ownership and complete fail-closed collection. The accepted bucket-event-payload-bounding decision governs S05. S03-S04 are routine repairs within existing diagnostic and storage contracts; no costly new decision is involved. S06 verifies the integrated result and owner-generated manifests. No legal-data rewrite, taxpayer filing, compatibility shim or broadened test exclusion is authorized.

Baseline evidence is .logs/test-runs/src-cadrumo-unit-20261014-232926-839/unit.log and its summary. Reconcile current source before each repair because another writer has corrected the malformed profile patch header and moved several formerly failing modules. Discover actual current failures rather than reconstructing removed paths.

The user corrected role conflation on 2026-10-15 and authorized continued repairs and mixed Luna max and Sol 6.1 medium agents. TUI remains a tax-product frontend in cadrumo; runtime is separate. A fixture dependency alone does not determine test ownership. Packaging/distribution inclusion, generic runtime authority and tax persistence paths must be assessed separately. Reassess earlier moves against the behavior each test proves before applying further ownership repairs.

## Steps

- [x] `S01` - Restore source parsing and resolve moved test and fixture ownership without compatibility imports; `src/cadrumo/entrypoints and affected application tests, canonical runtime or harness-owned destination tests where relocation is required`.
- [x] `S02` - Reconcile complete source inventories, canonical references and operation surface coverage with current ownership; `src/cadrumo core and cross-cutting source audit tests, shared inventory helpers and affected source docstrings`.
- [x] `S03` - Restore consistent diagnostic logging format and side-effect-free import behavior; `src/cadrumo/core/logging.py, diagnostic_log.py and their owning tests`.
- [x] `S04` - Repair storage setting enrollment, documented environment controls and producer liveness receipts; `src/cadrumo/core storage configuration and taxonomy modules, .env.example and storage policy tests`.
- [x] `S05` - Prove bounded optional decimal event payloads without weakening payload refusal; `src/cadrumo/application/ledger/actions_common.py and actions_lifecycle.py, domain/buckets/tests/test_payload_value_bounding.py`.
- [ ] `S06` - Run focused and complete product verification, regenerate affected owner-generated contracts and review the integrated repair; `src/cadrumo unit selection, affected canonical destination tests, configured code gates and repair evidence`.
- [x] `S07` - Separate corpus evidence from Python controls and republish verified authority; `dev/registry compiler and receipt tests, dev/quality/tests/test_corpus_provenance.py, src/cadrumo/_data/corpus/tests, src/cadrumo/adapters/outbound/aeat/sede/tests/test_groi_check.py, .authority/authority.current.json`.
- [x] `S08` - Resolve IVA evidence duties against the filing frame and enforce canonical IVA names; `src/cadrumo/application/aggregation/evidence_advisory.py, application/aggregation/tests/test_calculation_revision_iva_evidence_authority.py, application/tests/test_reference_catalogue.py, application/tests/test_apoderado_scopes_payload.py, tests/test_spanish_iva_stem_conformance.py`.
- [x] `S09` - Repair typed profile recovery and canonical operation notice output at frontend seams; `src/cadrumo/entrypoints/cli/_profile_authentication_gate.py, its refusal and command-ownership tests, src/cadrumo_runtime/commands/tests/test_tax_action_target_ownership.py, src/cadrumo_client/commands/registered_operation_observations.py, entrypoint settlement fixture tests`.
- [x] `S10` - Remove reexports and bind every consumer to the canonical defining module; `src/cadrumo reexport sites, their first-party direct and dynamic consumers, defining client modules, configured import-boundary controls`.

## Parallelization

S01 implementation was assigned to Sol 6.1 medium ownership_review: restore the TUI to cadrumo.entrypoints.tui, update its callers and launch paths, and restore tax CLI assertion modules using explicit neutral fixture ports while keeping concrete runtime setup/lifetime in host providers. Root owns storage and source-gate files excluded from that assignment.

S02 docstring and canonical symbol-reference repairs were assigned to Sol 6.1 medium doc_reference_repair, including the two doc-reference resolvers and the reported defining-module references. The disjoint 18-row central TUI error-enrollment repair was assigned to Luna max unit_coverage, limited to the existing declaration table and registration callers. Root serializes shared vault records, generated inventories and integration.

Root owns S03 logging, S04 storage scope and shared AST detector, S05 bounded payload and registry evidence behavior. Luna max unit_run owns the complete src/cadrumo unit run and focused checks; Luna max unit_summary owns the configured just check-code aggregate. Sol may prepare the integrated review read-only once a concurrency slot is free. Source writers are frozen during final checks, outputs are separate, and no worker stages or overwrites concurrent edits.

## Verification

Reproduce each owning failure and check success and refusal boundaries. Prove source parsing and clean affected collection after ownership changes. Retain moved tests at canonical owners, preserve markers and fixture lifetime, and remove dangling references rather than adding aliases or ignores. Static inventories remain complete and live, with existing planted-defect controls intact.

Run focused logging, storage, payload and source-audit tests and Ruff checks for changed files. Finish with the exact offline unit selector over src/cadrumo including calculation and revision-registry tests, affected moved tests at canonical destinations and configured code quality gates. Regenerate operation metadata only through its owning CLI and prove fresh currency. Record actual counts and unresolved conditions in the ledger and integrated review. Preserve unrelated index and worktree changes; never stage or commit another writer's unreviewed work.
