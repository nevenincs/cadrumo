---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S36'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cadrumo-product-rename with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S36 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Regenerate all root and companion dependency records after metadata converges and ## Scope

- `uv.lock` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Regenerate all root and companion dependency records after metadata converges

## Scope

- `uv.lock`

## Description

- Read the root and both companion metadata projects plus the complete existing lock.
- Restore the authorized one-line human console-script drift from `aeat` to canonical `cadrumo` while preserving every other root metadata byte.
- Run `uv lock` through the project workflow and verify it immediately with `uv lock --check`.
- Parse the resulting TOML and prove canonical project names, versions, path sources, companion extras, and root self-references.
- Classify exact former distribution and directory residue and inspect the lock diff for dependency churn.

## Outcome

Both lock commands resolved 246 packages successfully. The canonical lock contains one editable root package `cadrumo` at 0.1.1, one `cadrumo-data-manuals` and one `cadrumo-data-official` package at the same version, and canonical directory sources for both companion projects. Root metadata carries the five `cadrumo` self-references for `google`, `browser`, `anthropic`, `agent`, and `search`, plus both companion requirements under `corpus-sources`.

The regenerated lock hash is byte-identical to `HEAD`, so no dependency version or solver record changed. Exact scans found no `aeat-cli`, former companion distribution, or former companion directory residue.

## Notes

S36 is evidence-only because overtaking work had already regenerated the canonical lock. Restoring the concurrent script drift returned `pyproject.toml` to its committed canonical bytes, so neither metadata nor `uv.lock` requires a new file delta in this Step.

Formal review found no issue and independently confirmed unique canonical package blocks, path sources, version parity, current extras, zero former identity residue, and zero dependency churn.
