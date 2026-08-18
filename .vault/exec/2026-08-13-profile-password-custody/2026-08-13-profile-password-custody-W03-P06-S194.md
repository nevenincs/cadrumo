---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:f0f04a06501fde408f212cdb134492d250bce599f5ec039fa7291525166e0910'
step_id: 'S194'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-password-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S194 and 2026-08-13-profile-password-custody-plan placeholders are machine-filled by
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
     The Have Terra XHigh stop the two advisory paths that refuse or crash on states an operator legitimately passes through, the manager overview projecting a taxpayer classification without guarding the validation error a half-entered non-resident record raises so declaring non-residency before a country crashes the screen and blocks that onboarding outright, and the descendants advisory embedding an executable invocation in a notice message where the envelope contract admits one only through its typed action projection and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_status_frontend.py and src/cadrumo/application/wizard/_commands.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Have Terra XHigh stop the two advisory paths that refuse or crash on states an operator legitimately passes through, the manager overview projecting a taxpayer classification without guarding the validation error a half-entered non-resident record raises so declaring non-residency before a country crashes the screen and blocks that onboarding outright, and the descendants advisory embedding an executable invocation in a notice message where the envelope contract admits one only through its typed action projection

## Scope

- `src/cadrumo/entrypoints/cli/_config/_status_frontend.py and src/cadrumo/application/wizard/_commands.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Both advisory paths are fixed (commits `a6c9d9fb90`, locale follow-up). The manager overview's no-AEAT-history projection now guards `derive_tax_route(projection_for_taxpayer(record))` against `ValidationError` — a half-entered non-resident record (residency declared, country not) degrades to the generic advisory with `tax_route=None` instead of crashing the status page (the sibling `_overview.py` degrade precedent). The descendants advisory no longer interpolates an executable command string into the notice message: `command=` and the `'{command}'` placeholder are gone from the tr() calls and from all four catalogues, and the door now rides the typed action projection — a new `operator.profile.descendiente` catalogue entry (`target_command_key="config.profile.descendiente"`) resolved through `next_action`, so a renamed verb fails closed at emission instead of shipping a dead instruction. The honesty test asserts the nested `notice["action"]["action"]` shape; wizard command-helper suite 23 passed, honesty 7 passed.

## Notes

Routed finding: `test_status_frontend_gate.py` fails 4 cases at HEAD asserting `StatusPageData.recovery` — the recovery-zone model was never landed while the committed test expects it (peer WIP left half-committed); pre-existing, not this row's. The half-entered non-resident regression rides the guard via the existing degrade test's empty-root path.
