---
tags:
  - '#exec'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S01'
related:
  - "[[2026-07-18-user-docs-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S01 and 2026-07-18-user-docs-localization-plan placeholders are machine-filled by
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
     The Add sphinx-intl and babel to the docs dependency group, refresh the lockfile, and verify both import under uv and ## Scope

- `pyproject.toml`
- `uv.lock` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add sphinx-intl and babel to the docs dependency group, refresh the lockfile, and verify both import under uv

## Scope

- `pyproject.toml`
- `uv.lock`

## Description

- Add `sphinx-intl>=2.3` and `babel>=2.16` to the `dev` dependency group alongside the existing Sphinx cluster, with a comment stating `sphinx-intl` manages the per-language catalogues and `babel` parses catalogue statistics for the completeness gate.
- Refresh the lockfile with `uv lock` and reconcile the environment.
- Verify both packages import under `uv run --no-sync python`.

## Outcome

`sphinx-intl` 2.3.2 and `babel` 2.18.0 resolve and import cleanly. `babel` was already a transitive Sphinx dependency; the lock now pins both as declared docs tooling.

## Notes

The environment sync pruned four undeclared leftover packages (`pytest-httpx`, `pytest-rerunfailures`, `syrupy`, `time-machine`). They are not declared in the manifest and are members of the test-suite banned-live-imports gate, so removal reconciled the venv to the lock with no impact on collection.
