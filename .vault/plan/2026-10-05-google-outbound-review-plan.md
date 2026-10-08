---
tags:
  - '#plan'
  - '#google-outbound-review'
date: '2026-10-05'
tier: L1
related:
  - '[[2026-10-05-google-outbound-review-adr]]'
  - '[[2026-10-04-google-app-identity-adr]]'
  - '[[2026-07-12-google-oauth-adr]]'
  - '[[2026-07-09-compatibility-lifecycle-adr]]'
  - '[[2026-06-03-modelo-export-workbook-parity-adr]]'
  - '[[2026-06-03-modelo-export-evidence-parity-adr]]'
  - '[[2026-06-03-modelo-export-visual-design-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:1a3818d5b4fe4d72c1f5ec4fb412e3833606038349699c1f585defd8df32778e'
---
# `google-outbound-review` plan

## Description

Approved 2026-10-05

Authorization basis: the user dispatched Session 02 to execute SESSION-02-CONTAINMENT-BACKUPS-BRIEF, own containment, marked native creation, outbound retirement and ciphertext integrity, and perform live tests through the application's actual client. Session 01's completed SESSION-02-A-FOUNDATION-BRIEF assigns this session single integration ownership for S01-S04 and S07. This authorizes implementation and verification, not deployment. Preserve separate workbook rendering and evidence assembly ownership.

Accepted 2026-10-05-google-outbound-review-adr governs outbound admission, publication and retirement; existing identity, workbook/evidence/visual, mirror and compatibility decisions remain applicable. The separate backup-custody-policy ADR is proposed. S04 may investigate and repair integrity under existing policy but cannot change credential selection, manifest confidentiality or restore behavior without acceptance.

S01 freezes shared snapshot/admission/publication interfaces before dependent integration. Sessions B/C own renderer and evidence builder implementations and provide integration requests. The single integration owner controls shared contracts, central registration, namespace declarations and generated enrollment. Independent settled boundary fixes and focused reproductions started under the user's explicit brief; evidence is retained in SESSION-02-PROGRESS.md.

2026-10-07 validation repair, authorized by the operator's request to resolve the Google ADR validation error: 2026-10-05-google-outbound-review-backup-custody-policy-adr remains proposed and is recorded here as S04's unmet prerequisite, rather than linked as governing authority for this approved plan. S04 remains open and policy-changing implementation remains blocked until the proposal is explicitly accepted. This repair grants no custody-policy, restore, deployment or provider-mutation authority.

## Steps

- [ ] `S01` - Freeze immutable review snapshot, artifact admission and publication receipt interfaces under the integration owner; `src/cadrumo/application/export/review_snapshot.py (new), managed_artifact_ports.py (new), publication_receipt.py (new)`.
- [ ] `S02` - Enforce profile-bound containment and direct marked creation for every Google request and retry; `src/cadrumo/adapters/outbound/google/{root_folder,drive_entries,api,calc_sheets_apply}.py and adapters/outbound/storage/{factory,_google_drive}.py`.
- [ ] `S03` - Retire public Google pull, remote calculation and verify enrollment while preserving released records and offline export; `src/cadrumo/application/modelo/modelo_spreadsheet_operation.py, modelo_spreadsheet_executor.py and entrypoints/{modelo_spreadsheet_operation_composition.py,cli/_modelo_spreadsheet_command_specs.py}`.
- [ ] `S04` - Implement backup inventory and isolated recovery policy only after custody proposal acceptance; `src/cadrumo/adapters/outbound/storage/{mirror_push,mirror_manifest}.py and adapters/persistence/storage/secure_object_namespaces.py and entrypoints/profile_archive_operation_composition.py`.
- [ ] `S05` - Render selected calculation and ledger snapshots as immutable native review publications with external notes; `src/cadrumo/application/export/google_operation.py and application/storage/calc_sheets/workbook_export.py and bounded renderer/style owners`.
- [ ] `S06` - Build reproducible evidence packages from pinned snapshots and verified original payloads; `src/cadrumo/application/evidence/service.py and application/modelo/audit_operation.py and entrypoints/modelo_audit_operation_composition.py and new snapshot builder/payload loader`.
- [ ] `S07` - Integrate operation registration, generated surfaces and cross-lane failure contracts; `src/cadrumo/entrypoints/operation_composition.py and owning command schemas/generated documentation under the single integration owner`.
- [ ] `S08` - Run real OAuth and folder-contained publication acceptance with user review and isolated recovery evidence; `owning Google live tests and SESSION-01-REPORT.md acceptance continuation and retained synthetic Drive artifacts`.

## Parallelization

S01 precedes all source writers. After the integration owner freezes its interfaces, lane A owns S02-S04, lane B owns S05 and lane C owns S06. B and C may build local projections concurrently; their live publication waits for S02. S04 also waits for acceptance of the separate custody proposal. S07 follows all applicable lanes, and S08 follows S07. Lane A alone writes shared contracts, central registration, namespace policy and generated enrollment. Refine individual Steps before execution if a bounded discovery checkpoint establishes that a Step exceeds one cohesive commit.

User authorization 2026-10-05: Session03 may manage GPT-6.1-Sol xhigh workers without waiting on dispatch; its principal retains architecture implementation. Within S05, disjoint concurrent assignments are B1 frontend presentation/bridge integration (dedicated CLI/TUI modules and own tests), B2 workbook presentation and localized-label adapter preparation (review_workbook.py plus a dedicated label module and renderer tests), and B3 acceptance fixtures/tests (new dedicated application/export integration tests and safe acceptance instructions). B1/B2 must submit central declaration, shared schema and generated locale changes to lane A rather than editing those owners. B3 reports production defects to the principal instead of editing other assignments. Session03 principal alone writes google_operation.py, coordinates Sessions02/04, owns shared checks, and serializes plan/ledger/commits and final review. Workers may execute settled work and prepare concrete patches for prerequisite-dependent wiring; none may launch OAuth, spawn further agents, close S05, or claim live acceptance independently.

## Verification

Require meaningful unit and native-operation tests for containment-before-content, pagination, stale/moved/foreign/shortcut refusal, retry uncertainty, removal across actual enrolled frontends, frozen revision values, literal text, preserved notes, exact evidence payload digests and incomplete status. Run applicable repository checks for changed code. Real OAuth uses the bundled client with drive.file as the only data scope. Retain synthetic native Sheets inside the managed root and obtain actual user review and edit feedback. Verify local revision stability after edits. Record ciphertext inventory/integrity separately from isolated restore evidence. No claim of recoverable backup without recovery. No deployment, production restore or destructive cleanup. Session 01 local tests and blocked provider cases are evidence, not S08 completion.
