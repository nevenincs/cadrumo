---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:1cceb33064ac9adf30b4f22787760045d0009907f0e1f19642ff15e385a319b8'
step_id: 'S102'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S102 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Run the commissioned production write-call census, enumerating every write_bytes, write_text, open in write mode, mkdir, makedirs, os.replace, shutil.copy, tempfile, and archive-writer call and classifying each destination as enrolled, nested-ungoverned, operator-directed, or ad-hoc and ## Scope

- `src/cadrumo/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the commissioned production write-call census, enumerating every write_bytes, write_text, open in write mode, mkdir, makedirs, os.replace, shutil.copy, tempfile, and archive-writer call and classifying each destination as enrolled, nested-ungoverned, operator-directed, or ad-hoc

## Scope

- `src/cadrumo/`

## Description

- Enumerate every production `write_bytes`, `write_text`, `open` in write mode, `mkdir`, `makedirs`, `os.replace`, `shutil.copy*`, `tempfile`, and archive-writer call, classifying each destination as ENROLLED, NESTED-UNGOVERNED, OPERATOR-DIRECTED, or AD-HOC.

## Outcome

Landed as `storage-root-ledger/13-file-producing-sites.md` in the session scratchpad, measured against HEAD `86b02bf68e`. Counts: ENROLLED ~29 sites/~14 files; NESTED-UNGOVERNED 3 site families beyond the two already known to this campaign (blob-store hash-prefix fan-out, local-storage-provider namespace fan-out, observability run-id leaf — see S86–S92 for the full set combined with the secret-store and live/rotation findings); OPERATOR-DIRECTED ~14 sites/~9 files; AD-HOC 1 in-scope finding (`domain/manuals/_fetch.py`, see S92); ~8 files judged out of scope entirely (agent workspace, locales manager, LibreOffice temp staging, corpus-manifest zip primitive, parity tapes, CLI metadata tempdir — none touch `cadrumo_local_storage_root`).

## Notes

**Not durably homed.** This census lives only in the session scratchpad, not `.vault/`, and is at risk of loss when the session ends — the same gap the closure-criterion reference document already names for the test-migration inventory. Its findings are recorded here and in the closure-criterion document, and in Steps S86–S92, precisely so the underlying analysis survives even if the scratchpad file itself does not. The closure-criterion document previously stated this census as "commissioned but had not landed" — that was accurate when written and is now stale; corrected there in the same pass as this record.
