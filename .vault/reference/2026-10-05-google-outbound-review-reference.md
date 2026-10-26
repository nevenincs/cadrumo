---
tags:
  - '#reference'
  - '#google-outbound-review'
date: '2026-10-05'
modified: '2026-10-05'
body_schema: 'body-v2'
body_hash: 'sha256:57e8f9841b4f201617b0834be5eb75d9b195562a2d4902c464eb59cd889cb753'
related: []
---

# `google-outbound-review` reference: `Session 01 current export, containment and evidence boundaries`

## Summary

Static characterization on 2026-10-05, entry HEAD ca1d65b5b79d4d52714fa5fa0754b5e13029a64d with unrelated dirty work. Reused the discovery corpus in `.codex/scratch/luna-google-discovery`; bounded checkpoints and exact inspected slices are in `SESSION-01-CHECKPOINTS.md`. Code semantic search was unavailable (service stopped); named-owner fallback used. Vault semantic search succeeded and all 545 ADRs were enumerated in two pages. This record does not establish published behavior or live Google acceptance.

## Findings

### Calculation export currently exports a template

`src/cadrumo/application/export/google_operation.py:96` requests profile/model/year/period, not a CalculationRevisionId. Its `_build_plan` at line 327 passes empty OperatorInputs and either empty relations or a local prior-filing resolver. `src/cadrumo/application/storage/calc_sheets/workbook_export.py:109` does the same for offline workbooks. Native Sheet creation therefore does not prove selected saved values were exported.

### Remote business-data read routes remain enrolled

`src/cadrumo/entrypoints/cli/_modelo_spreadsheet_command_specs.py:218` declares pull, calculate and verify. `src/cadrumo/application/modelo/modelo_spreadsheet_executor.py:231` retains read/compute projections, without canonical fact persistence. `src/cadrumo/entrypoints/modelo_spreadsheet_operation_composition.py:176` discards the verified root when calling pull; the adapter receives only workbook ID and credentials. `src/cadrumo/adapters/outbound/google/calc_sheets_pull.py:186` requests marker metadata, not parents/MIME/trash, then reads developer metadata and business values at line 497. Its compute_from_pull at line 970 runs the canonical calculator on those edits. Production verify uses the parity harness and another scenario write; retiring only CLI help would leave operation contracts and backend behavior.

`src/cadrumo/entrypoints/operation_composition.py:1154` and line 1788 register the four spreadsheet operations. Separate export.google-sheets registration is at line 1835. Spreadsheet worker definitions permit CLI only; Google push permits all frontends. Reports B3/B5 establish no TUI Sheets caller; native/MCP discoverability still needs generated and installed proof. Checkout CLI help executed in this session shows all five verbs.

### Containment differs from ownership

`src/cadrumo/adapters/outbound/google/calc_sheets_apply.py:311` creates a Sheet with spreadsheets.create, then reads parents and moves/stamps it. This violates identity commitment 7 and the session creation constraint. No intentional live reproduction is permitted.

`src/cadrumo/adapters/outbound/google/root_folder.py:83` bootstraps through name lookup under My Drive root. Its stored-root check at line 116 checks marker, folder MIME and trash but not profile identity. `src/cadrumo/adapters/outbound/google/drive_entries.py:199` lists ten results without nextPageToken, and returns the first owned match. A parent-scoped list at My Drive root is outside the managed root even though it is not a global Drive scan.

`src/cadrumo/adapters/outbound/storage/_google_drive.py:487` and line 589 cache vault and namespace IDs for the provider lifetime. Child lists are parent-scoped and paginated, but cached folder ancestry is not renewed. Storage creates folders/objects with parents and markers. Neither that nor drive.file supplies an atomic folder-membership condition for subsequent content requests. `src/cadrumo/adapters/outbound/google/api.py:139` is an error/retry boundary, not an artifact admission authority.

### Re-export overwrites review work

`src/cadrumo/adapters/outbound/google/calc_sheets_apply.py:871` reuses a name/period target, reads occupied cells, writes baseline and formula cells, then clears stale addresses. Preview at line 995 reads current workbook values. `USER_ENTERED` in line 776 combines ordinary strings and intentional formulas. Immutable exports require new publication identity, literal text, and no read/diff/clear of review notes.

### Backup axes are distinct

A2/A9 establish that Google token, metadata and Drive-config namespaces are excluded from portable bundles but inherit CIPHERTEXT_WITH_METADATA for remote mirroring. `src/cadrumo/adapters/outbound/storage/mirror_push.py:317` gates mirror policy independently from sensitivity/custody. `src/cadrumo/adapters/outbound/storage/mirror_manifest.py:67` serializes manifest JSON without application encryption. This is explicitly permitted by accepted 2026-07-12-google-oauth-adr; confidentiality is not wholly unruled as the earlier handover suggests. Token eligibility remains open in the identity ADR.

`src/cadrumo/adapters/outbound/storage/mirror_push.py:404` uploads rows and rolls back successfully uploaded keys on namespace failure, while the provider put at line 688 may update earlier objects. This is a static destructive-rollback candidate needing a focused reproduction. No mirror restore exists; sealed archive database custody and portable bundle selection must not be conflated.

### Existing revision and payload seams

`src/cadrumo/domain/modelos/calculation_revision.py:858` carries revision/work-unit identity, pinned registry reference, values, typed observations, row coordinates, operator layer, source provenance and source issues. Optional ledger snapshot/evidence at line 912 is captured at verify/file time and can be absent for a draft. `src/cadrumo/domain/modelos/ledger_filing_snapshot.py:149` supplies tax-relevant contributor projections and attachment/invoice references. `src/cadrumo/application/storage/calc_sheets/evidence.py:31` requires explicit contributor-to-casilla attribution; it does not derive that mapping by guesswork.

`src/cadrumo/application/modelo/audit_operation.py:414` calls EvidenceBundleService.export without record_payloads. `src/cadrumo/application/evidence/service.py:389` defaults to an empty map: nonempty bundles refuse unless forced; force writes manifest only. `src/cadrumo/entrypoints/modelo_audit_operation_composition.py:17` supplies repositories but no payload loader. `src/cadrumo/adapters/persistence/storage/attachment.py:315` can load decrypted bytes by digest; verify_blob recomputes the digest. Load once and verify those exact bytes before publication, rather than reading twice.

`src/cadrumo/application/modelo/review_package.py:203` is a separate sealed-revision filing package containing draft, revision, evidence projection and package-info under checksums. It does not bundle original attachments and is not the provisional review package door.

### Local execution and live limitations

`.venv/Scripts/aeat.exe --version` reports CADRUMO 0.5.1. Import resolves to this checkout's src/cadrumo, so it is not independent installed-build evidence. `aeat --format json config google status` exits 1 with ERROR_CALCULATIONS_REGISTRY_AUTHORITY_DESCRIPTOR_UNAVAILABLE, active_profile null, before OAuth/provider access. No published executable on PATH or standard Programs/Start Menu location was located. The user was asked for the launch path. No Google credential, private profile payload or client metadata was read. Published version/build, runtime health and authority generation remain unestablished.

Full case classifications and subsequent checks belong to `SESSION-01-REPORT.md`; historical plan closure is not live acceptance.

### Runtime fixture follow-up and user clarification

The user clarified that the live OAuth application is the bundled client in the uv environment; no separate installed executable is required. Data authorization remains drive.file only, with existing identity scopes and no spreadsheet scope. Repo-root conftest.py:183 and justfile:77 set CADRUMO_AUTHORITY_ROOT to .authority. The descriptor exists: logical generation 64578b399a91c3743178129dac23ee58dea8b9a393d98f16ad448b9fde7e2dc7, database SHA-256 5ca48589c3cad2def92ca7790ede2ef806cace14cead48c4376b7e5463944bd4. The earlier missing-descriptor error was a direct-launch environment problem, not absence of a published generation.

The native Google configuration integration test passed (1 test, 42.52 seconds, 19 SQLAlchemy deprecation warnings). It uses native_cli_profile_scope, isolated encrypted profile registration, explicit development session admission, a retained Windows runtime and a separate profile worker. It deliberately uses MemoryNativePort and synthetic OAuth records and never starts sign-in. It proves local runtime/profile composition only. Logs: var/storage/development/.logs/test-runs/2026-10-05/20261005T120958.643095Z-pytest-41448-98df09d9/run.log. The 36 Google/evidence unit tests also passed. No browser OAuth, Drive provider call, document creation or user review occurred; known root bootstrap and creation-contract violations block those slices under Session 01 constraints.
