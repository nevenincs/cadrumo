---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
step_id: 'S37'
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
     The S37 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Update the slim-wheel clean-install probe to Cadrumo names and ## Scope

- `dev/packaging/smoke_core.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Update the slim-wheel clean-install probe to Cadrumo names

## Scope

- `dev/packaging/smoke_core.py`

## Description

- Read the binding naming ADR and confirm that `aeat` is the sole human
  executable while `CADRUMO` is the version identity.
- Correct the slim-wheel installed CLI assertion to require `CADRUMO` from
  `aeat --version`.
- Run focused packaging tests, lint, formatting, and the real wheel build and
  fresh virtual-environment installation probe.

## Outcome

The slim-wheel probe now verifies the installed `aeat` executable and rejects
version output that does not carry the `CADRUMO` identity. The focused packaging
suite passed three tests, Ruff and formatting passed, and the real packaging
smoke built `cadrumo-0.2.0-py3-none-any.whl`, installed it into a fresh virtual
environment, exercised the installed CLI, and wrote its smoke manifest.

## Notes

The real smoke completed in 312 seconds. Existing authority-owned `AEAT` and
`registry/aeat` names were not changed. Sentence prose casing was outside this
Step; the uppercase assertion is intentional because version output is an
identity context under the binding ADR.
