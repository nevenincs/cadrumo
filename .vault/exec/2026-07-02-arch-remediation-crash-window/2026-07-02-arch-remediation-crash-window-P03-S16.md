---
tags:
  - '#exec'
  - '#arch-remediation-crash-window'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S16'
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
     The S16 and 2026-07-02-arch-remediation-crash-window-plan placeholders are machine-filled by
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
     The Assert the sealed-archive writer checkpoints or includes the -wal sidecar so a sealed bundle carries every committed row and ## Scope

- `src/aeat/adapters/persistence/storage/tests/test_wal_sidecar_accounting.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assert the sealed-archive writer checkpoints or includes the -wal sidecar so a sealed bundle carries every committed row

## Scope

- `src/aeat/adapters/persistence/storage/tests/test_wal_sidecar_accounting.py`

## Description

Authored the sealed-export WAL-sidecar accounting test: write a real committed-but-uncheckpointed row and prove the SQL read layer (the layer `serialize_profile_bundle` uses to build the sealed-archive payload) returns the row even though the raw main `.db` file does not yet carry it, so a sealed bundle carries every committed row regardless of checkpoint state.

## Outcome

One test passes: the sealed export inherits the SQL read layer's WAL visibility, so no committed row is dropped.

## Notes

Tested at the SQL-read layer rather than through the export service, which is transiently blocked by an unrelated peer import break in `domain.user_profile`.
