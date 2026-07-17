---
tags:
  - '#exec'
  - '#export-publication'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S07'
related:
  - "[[2026-07-17-export-publication-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace export-publication with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-17-export-publication-plan placeholders are machine-filled by
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
     The Route both config profile export and subject-access-request through the sole portable-export application service and remove direct serialization, target writes, completion events, and static SAR category ownership from the CLI and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_export.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Route both config profile export and subject-access-request through the sole portable-export application service and remove direct serialization, target writes, completion events, and static SAR category ownership from the CLI

## Scope

- `src/cadrumo/entrypoints/cli/_config/_profile_export.py`

## Description

- Confirm both the profile export and the subject-access-request commands already route through the sole `export_profile_bundle` service and own no serialization, target write, or completion event; the lifecycle event write on the CLI is import-only.
- Rewrite the subject-access catalogue notice to stop enumerating a hand-maintained personal-data category list, pointing instead at the derived `data_categories` the export service computes from the bundle schema and carried registry namespaces (already carried on the response and in the notice context).
- Update the catalogue notice prose in the en, es, ca, and hu catalogues through the locales CLI.

## Outcome

The CLI no longer owns a static category list; the authoritative derived set rides on the response. Locale parity, honesty, drift-check, and the subject-access / export CLI suites pass. Committed in `c59e862ad7`.

## Notes

The plan's declared file `_profile_export.py` does not exist; the export and subject-access commands live in `_config/_profile_bundle.py` (with import). The substantive change was made there to avoid a file split touching the peer-hot `_config/__init__.py` registration wiring. The filename divergence was flagged to the coordinator.
