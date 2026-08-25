---
tags:
  - '#exec'
  - '#docs-sphinx-ux'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:472be597a1de48b61f931ed3d8749809879dae7ce446df1ace2fef14b548614d'
step_id: 'S02'
related:
  - '[[2026-06-04-docs-sphinx-ux-plan]]'
---

# `docs-sphinx-ux` `W01.P01.S02`

Scope: `W01.P01.S02`.

## Description

Load project display metadata from `pyproject.toml`.
Enable the selected Sphinx extensions in `docs/conf.py`.
Keep sitemap activation behind the published-site URL setting.

## Outcome

The docs build now derives project name, author, release, version, repository links, and extension loading from the repository metadata surface.
`uv run --no-sync ruff check docs/conf.py` passed.

## Notes

The generated API reference still exposes an existing autodoc and Pydantic import failure during full-tree builds.
That failure is not introduced by the UX extension wiring and remains outside this foundation step.
