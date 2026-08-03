---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:ac0f57845c70b73c2d65c1ca92551f6de29667ad529cb023ca5dfffd7e7923e4'
step_id: 'S50'
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
     The S50 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Correct the wallet diagnostic field docstring so it stops overstating the capture scope relative to the implementation, gated by the generated environment reference regenerating without drift and ## Scope

- `src/cadrumo/core/_config_integration_fields.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Correct the wallet diagnostic field docstring so it stops overstating the capture scope relative to the implementation, gated by the generated environment reference regenerating without drift

## Scope

- `src/cadrumo/core/_config_integration_fields.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `fe527508fe`, confirmed at HEAD. The Step text names `src/cadrumo/core/_config_integration_fields.py`; the field actually lives in `src/cadrumo/core/config.py:519-536` (`cadrumo_wallet_diagnostic_dump_dir`). The description no longer claims "full captured page tree" or "may contain live taxpayer amounts" — it now states the capture is a "redacted structural-shape summary" (URL without query, element counts, form action paths, a content hash) and explicitly "never writes raw HTML, frame HTML, screenshots, input values, or wallet amounts." File-path correction noted here since the Step row cites the wrong file (see S105's record for the inverse mismatch — the two Steps' file citations appear swapped at authoring time).

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
