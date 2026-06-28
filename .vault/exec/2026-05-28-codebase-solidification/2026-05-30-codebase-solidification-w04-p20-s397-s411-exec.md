---
step_id: "S397-S411"
phase: "W04.P20"
feature: "codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-beta8
commit: e30370bdc
tags:
  - "#exec"
  - "#codebase-solidification"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W04.P20 — S397–S411 Step Record

## Steps closed

S397, S398, S399, S400, S401, S402, S403, S404, S405, S406, S407, S408, S409, S410, S411

## Collision check

Pre-flight `git diff` on all target files. `_operator.py` carried non-authored WIP
from a parallel campaign (`unwrap_optional_secret` additions at different lines). No
conflicting edits on our target lines. All other files were clean.

## Files touched and migrations

- `_browser_constants.py`: +`PLAYWRIGHT_TIMEOUT_SHORT_MS`, +`SEDE_BODY_ENCODING` (S398, S401)
- `_notifications.py`: 2 domcontentloaded literals enrolled (S397)
- `_renta_web_open.py`: 1 networkidle literal enrolled (S397)
- `_walker.py`: timeout=2_000 enrolled, "pdf" check enrolled (S398, S402)
- `_declarations.py`: latin-1 enrolled, 2 "pdf" checks enrolled (S401, S402)
- `external_constants.py`: +PDF_MIME_TYPE, +PDF_EXTENSION, +XLSX_EXTENSION, +XLSM_EXTENSION, +LATIN_1_ENCODING (S402, S408)
- `_export_parse.py`: latin-1 decode enrolled (S401/S402)
- `_record_design.py`: .pdf/.xlsx/.xlsm extension checks enrolled (S409)
- `_workbook_parity.py`: WorkbookScanStatus Literal→StrEnum; .xlsx checks enrolled (S407, S409)
- `_actions.py`: LedgerProviderID(StrEnum) introduced; dispatch chain migrated (S399)
- `_operator.py`: AuthAcquisitionLockState identity comparison; ProviderProbeResult(StrEnum); 11 result= assignments migrated (S403, S404)
- `_engine.py`: DeadlineRole + FilingWindowState StrEnums; 3 literal assignments migrated (S405, S406)
- `_persistence.py`: WorkflowEnvelopeReasonClass(StrEnum); 3 reason_class assignments migrated (S407)
- `_calc_sheets_pull.py`: MetadataMatchState(StrEnum); Literal annotation and 4 comparison sites migrated (S410)
- `_constants.py` (inbound): now imports PDF_EXTENSION + XLSX_EXTENSION from external_constants (S408)

## New StrEnums introduced (4)

- `LedgerProviderID` — 9 members (auto, csv, ofx, qfx, xlsx, excel, n26, pdf, pdf-n26)
- `ProviderProbeResult` — 10 members (no_provider, no_path_set, file_missing, unreadable, corrupt, expired, expiring, ok, identity_unset, invalid_identity)
- `DeadlineRole` — 2 members (INFORMATIONAL, BINDING)
- `FilingWindowState` — 3 members (ABSENT, OPEN, CLOSED)
- `WorkflowEnvelopeReasonClass` — 3 members (READABLE, UNREADABLE, ABSENT)
- `WorkbookScanStatus` — 4 members, converted from Literal (SCANNED, UNSUPPORTED, TIMEOUT, FAILED)
- `MetadataMatchState` — 3 members (MATCHES, STALE, MISSING)

## New test files

- `src/aeat/application/ledger/test_provider_id_enum.py` (S400) — 3 tests
- `src/aeat/test_hardcoded_constants_inventory.py` (S411) — 5 inventory assertions

## pytest outcome

8/8 new tests pass. 180/180 auth+workflow tests pass. Pre-existing registry
coverage failure (`test_committed_registry_tree_has_required_model_law_coverage`)
confirmed unrelated to this campaign.

## Commit SHA

e30370bdc
