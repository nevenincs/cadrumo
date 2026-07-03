---
tags:
  - '#exec'
  - '#claude-ecosystem-packaging'
date: '2026-07-03'
modified: '2026-07-03'
step_id: 'S20'
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
     The S20 and 2026-07-03-claude-ecosystem-packaging-plan placeholders are machine-filled by
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
     The Add the corpus-sources optional extra pinning aeat-data at an exact version and ## Scope

- `pyproject.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the corpus-sources optional extra pinning aeat-data at an exact version

## Scope

- `pyproject.toml`

## Description

- Add the `corpus-sources` optional extra to `pyproject.toml`, pinning `aeat-data==0.1.0` at an exact version.
- Deliberately exclude `corpus-sources` from the `all` aggregate extra until the companion distribution is published — including it would make `aeat[all]` unresolvable.
- Add a `[tool.uv.sources]` path source pointing at `packaging/aeat_data` so the dev resolver builds the companion locally, while published wheel metadata keeps the bare version pin.
- Teach `dev/packaging/smoke_core.py`'s `_export_names` to resolve local-path export rows via the referenced project's `[project].name`.
- Document the deptry `DEP002` suppression for the data-only package (reached dynamically via `importlib.resources`, carries no importable code).
- Commit `d04ec459ad`.

## Outcome

- `just packaging-smoke-dependencies` exits 0.
- `just check-dependencies` (deptry) exits 0.

## Notes

Executed inline by the coordinator during the executor-fleet rate-limit window. No incidents.
