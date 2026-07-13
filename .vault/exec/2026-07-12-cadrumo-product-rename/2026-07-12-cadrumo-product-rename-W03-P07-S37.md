---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
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

- Retarget source paths, wheel glob, archive prefixes, imports, install target, executable, version assertion, and optional-extra remedy to Cadrumo.
- Preserve `registry/aeat` leaves as authority-owned taxonomy evidence.
- Isolate installed-wheel subprocess settings from unrelated host product state.
- Run the real wheel build and fresh virtual-environment installation probe.

## Outcome

The slim-wheel probe now expects `cadrumo`, `cadrumo-*.whl`, `cadrumo/_data`,
`cadrumo[anthropic]`, Cadrumo imports, and the installed `cadrumo` script, with no
former distribution, import, member, or executable expectation. Ruff, formatting,
residue, plan, and diff checks pass.

## Notes

The first real run exposed an installed import inheriting former-product host
state; the second exposed the same leak in the default CLI check. Both child
processes now receive isolated Cadrumo storage and database settings. The final
run built and installed the real wheel and advanced through installed data and
runtime-surface checks into CLI profile/config work, but the outer 124-second
command budget expired before the smoke manifest was written. This timeout is
recorded as incomplete end-to-end acceptance evidence rather than a passing run.
