---
tags:
  - '#exec'
  - '#data-output-standardization'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S09'
related:
  - "[[2026-07-13-data-output-standardization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace data-output-standardization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-07-13-data-output-standardization-plan placeholders are machine-filled by
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
     The Replace the plain FileHandler with a size-capped rotating handler for cadrumo.log and ## Scope

- `src/cadrumo/core/logging.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the plain FileHandler with a size-capped rotating handler for cadrumo.log

## Scope

- `src/cadrumo/core/logging.py`

## Description

- Add two Settings fields (`cadrumo_log_file_max_bytes`, default 10 MiB; `cadrumo_log_file_backup_count`, default 5) as the diagnostic-log rotation knobs.
- Switch the `cadrumo.log` file handler in `core/logging.py` from `logging.FileHandler` to `logging.handlers.RotatingFileHandler`, wiring `maxBytes`/`backupCount` from the new settings, and import `logging.handlers`.
- Add real-behavior tests: the installed handler is a `RotatingFileHandler` carrying the settings cap/backup count, and writing past the cap rolls over while the retained-backup count stays bounded.
- Add the two fields to the env template and regenerate the env-overrides reference.

## Outcome

The diagnostic log now has a declared rotation lifecycle instead of unbounded growth. `RotatingFileHandler` is a `FileHandler` subclass, so the existing degrade-to-stderr and level-governance tests remain valid. Gates: the rotation suite, the existing logging suite, the settings/env-parity suite, and the env-reference freshness gate all pass (50 passed); ruff clean.

## Notes

Cap and backup count live as central Settings fields per schema-central-config rather than magic literals, since they are deployment knobs. First step of Wave W02 (lifecycle policy); the structural lifecycle gate in S13 will assert this field family maps to the rotation class.
