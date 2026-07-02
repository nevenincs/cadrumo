---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S15'
related:
  - "[[2026-07-02-arch-remediation-crash-window-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-crash-window with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S15 and 2026-07-02-arch-remediation-crash-window-plan placeholders are machine-filled by
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
     The Assert every at-rest plaintext-scan surface reads the SQLite -wal sidecar so no committed-but-uncheckpointed rows are silently absent from the scan and ## Scope

- `src/aeat/adapters/persistence/storage/tests/test_wal_sidecar_accounting.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assert every at-rest plaintext-scan surface reads the SQLite -wal sidecar so no committed-but-uncheckpointed rows are silently absent from the scan

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_wal_sidecar_accounting.py`

## Description

Authored the at-rest WAL-sidecar accounting test: write a real committed secure-object row in WAL mode without a checkpoint, and prove the shared at-rest scan helper folds in the `-wal` sidecar so a main-file-only read (which misses the committed row) is strictly smaller than the combined view.

## Outcome

One test passes: the at-rest plaintext-scan surface reads the `-wal` sidecar so committed-but-uncheckpointed rows are not silently absent.

## Notes

None.
