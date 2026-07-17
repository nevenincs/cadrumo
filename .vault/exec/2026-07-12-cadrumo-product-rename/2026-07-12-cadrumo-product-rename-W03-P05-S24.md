---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
step_id: 'S24'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Rename root metadata, package selection, extras, URLs, and scripts so the sole human `aeat` command launches Cadrumo and `cadrumo-mcp` launches MCP

## Scope

- `pyproject.toml`

## Description

- Converge the root distribution, source-package selection, console scripts, self-referencing extras, repository URLs, dependency exceptions, and local companion source mappings on Cadrumo.
- Preserve AEAT only in authority-facing dependency descriptions, corpus paths, keywords, test markers, and outbound-adapter paths.
- Build and inspect the root wheel without regenerating dependency lock state.

## Outcome

The root metadata tuple is distribution `cadrumo`, source package `src/cadrumo`, human console script `cadrumo`, and MCP console script `cadrumo-mcp`. The aggregate extra self-references `cadrumo`, companion references use `cadrumo-data-manuals`, `cadrumo-data-official`, and their future canonical source paths, and project URLs identify `github.com/cadrumo/cadrumo`.

TOML parsing and exact residue checks passed. A real wheel build emitted `cadrumo-0.1.1-py3-none-any.whl`; its metadata reports `Name: cadrumo`, contains only Cadrumo package members, and declares exactly the two requested Cadrumo entry points. `uv.lock` was not modified.

## Notes

The current `pyproject.toml` already carried most of the S24 cut through user-authorized overlapping work; this Step preserves and cross-commits that converged content. No companion project file or directory was edited and no lock regeneration was run.

The user's explicit S24 instruction requires `cadrumo` and `cadrumo-mcp` scripts and therefore overrides the scaffolded Step heading's stale `aeat` executable wording for this execution.

Formal review found no actionable metadata issue. It recorded the older CLI ADR and plan wording as a governance conflict, not an implementation defect under the newer explicit instruction.
