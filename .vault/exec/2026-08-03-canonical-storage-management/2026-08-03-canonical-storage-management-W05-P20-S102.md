---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:a7a3b5cd28d8e4971da0f352166f02ce807ff6c4e1a532722f82036f372dd618'
step_id: 'S102'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Run the commissioned production write-call census, enumerating every write_bytes, write_text, open in write mode, mkdir, makedirs, os.replace, shutil.copy, tempfile, and archive-writer call and classifying each destination as enrolled, nested-ungoverned, operator-directed, or ad-hoc

## Scope

- `src/cadrumo/`

## Description

- Enumerate every production `write_bytes`, `write_text`, `open` in write mode, `mkdir`, `makedirs`, `os.replace`, `shutil.copy*`, `tempfile`, and archive-writer call, classifying each destination as ENROLLED, NESTED-UNGOVERNED, OPERATOR-DIRECTED, or AD-HOC.

## Outcome

Landed as `storage-root-ledger/13-file-producing-sites.md` in the session scratchpad, measured against HEAD `86b02bf68e`. Counts: ENROLLED ~29 sites/~14 files; NESTED-UNGOVERNED 3 site families beyond the two already known to this campaign (blob-store hash-prefix fan-out, local-storage-provider namespace fan-out, observability run-id leaf — see S86–S92 for the full set combined with the secret-store and live/rotation findings); OPERATOR-DIRECTED ~14 sites/~9 files; AD-HOC 1 in-scope finding (`domain/manuals/_fetch.py`, see S92); ~8 files judged out of scope entirely (agent workspace, locales manager, LibreOffice temp staging, corpus-manifest zip primitive, parity tapes, CLI metadata tempdir — none touch `cadrumo_local_storage_root`).

## Notes

**Not durably homed.** This census lives only in the session scratchpad, not `.vault/`, and is at risk of loss when the session ends — the same gap the closure-criterion reference document already names for the test-migration inventory. Its findings are recorded here and in the closure-criterion document, and in Steps S86–S92, precisely so the underlying analysis survives even if the scratchpad file itself does not. The closure-criterion document previously stated this census as "commissioned but had not landed" — that was accurate when written and is now stale; corrected there in the same pass as this record.
