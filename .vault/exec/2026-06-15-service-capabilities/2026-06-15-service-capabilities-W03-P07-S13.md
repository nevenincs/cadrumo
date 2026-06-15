---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S13'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace service-capabilities with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S13 and 2026-06-15-service-capabilities-plan placeholders are machine-filled by
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
     The Investigate the torch placement (vaultspec-rag managed-torch-direct-dependency) and restructure pyproject: capability-mapped extras + relocate torch correctly and ## Scope

- `pyproject.toml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Investigate the torch placement (vaultspec-rag managed-torch-direct-dependency) and restructure pyproject: capability-mapped extras + relocate torch correctly

## Scope

- `pyproject.toml`

## Description

- Confirm the safe location for torch by reading vaultspec-rag's `torch_config/_direct_dep.py`, which accepts a PEP 735 `[dependency-groups]` entry as a valid direct-dependency declaration.
- Move `torch` from `[project.dependencies]` to `[dependency-groups].dev` with a rationale comment (torch is a dev/RAG-build dependency, not a runtime requirement of the shipped CLI).
- Remove the now-unneeded `torch` entry from `[tool.deptry.per_rule_ignores]` DEP002.
- Re-resolve the lockfile and run the dependency gate.

## Outcome

`uv lock` resolved cleanly (265 packages) and `just check-dependencies` is green (exit 0). torch is no longer a declared runtime dependency of the shipped application while remaining available for the dev/RAG build. Committed as `93d903f30`; the dependency-provisioning ADR §4 was updated to record torch-relocation done and the capability-extras lean-core migration deferred (tracked as S09).

## Notes

The broader capability-extras lean-core migration (relocating google/playwright/anthropic out of `[project.dependencies]`) was deliberately NOT attempted here: it requires eager→lazy import conversion across several adapters and is breakage-risky. It is deferred and documented in the ADR; S09 carries its closure decision.
