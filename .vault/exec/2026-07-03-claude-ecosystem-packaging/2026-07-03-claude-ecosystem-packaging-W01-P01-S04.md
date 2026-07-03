---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S04'
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
     The S04 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Prove installed-mode storage resolves off the platform directory and never off PROJECT_ROOT with a fresh-install roundtrip test and ## Scope

- `src/aeat/core/tests/test_config_state_root.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Prove installed-mode storage resolves off the platform directory and never off PROJECT_ROOT with a fresh-install roundtrip test

## Scope

- `src/aeat/core/tests/test_config_state_root.py`

## Description

- Add a fresh-install roundtrip test to `src/aeat/core/tests/test_config_state_root.py` proving installed-mode resolution lands under the platform user-data directory and never under `PROJECT_ROOT`.
- Confirm the checkout default is unchanged by the same proof.
- Add an anti-tautology case: repo markers (a `pyproject.toml` file plus a `.git` path) beat a populated `LOCALAPPDATA` environment variable, so a checkout is never mistakenly routed to the platform directory.
- Exercise the real `Settings` validator chain end to end; no mocks, fakes, or monkeypatches.
- Commit `196058bb29`.

## Outcome

- Full-suite collect-only gate (`uv run --no-sync pytest --collect-only -q`) clean across 265 collected items.

## Notes

No incidents. No skipped work.
