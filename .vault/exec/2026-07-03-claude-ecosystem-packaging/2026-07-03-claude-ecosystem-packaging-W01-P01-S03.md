---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S03'
related:
  - "[[2026-07-03-claude-ecosystem-packaging-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace claude-ecosystem-packaging with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S03 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Assert the derived tokens, logs, secret, blob and audit roots follow the installed platform base through the existing state-root validators and ## Scope

- `src/aeat/core/tests/test_config_state_root.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assert the derived tokens, logs, secret, blob and audit roots follow the installed platform base through the existing state-root validators

## Scope

- `src/aeat/core/tests/test_config_state_root.py`

## Description

- Add `src/aeat/core/tests/test_config_state_root.py` asserting the derived tokens, logs, secrets, blobs, and audit roots re-derive under the installed platform base.
- Confirm the re-derivation flows through the existing state-root validators: `default_factory` leaves the field unset so the `model_fields_set`-keyed validators re-derive it from the platform-resolved storage root rather than a stale default.
- Commit `83baff4254`.

## Outcome

- New test module passes, exercising the derived-root re-computation for every dependent state directory.

## Notes

No incidents. No skipped work.
