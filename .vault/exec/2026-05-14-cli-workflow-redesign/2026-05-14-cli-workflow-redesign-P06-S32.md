---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S32'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-workflow-redesign with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S32 and 2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan placeholders are machine-filled by
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
     The Confirm Modelo 036 and Modelo 037 behavior and metadata remain unaffected by Modelo 145 successor work and ## Scope

- `tests/domain/calculations/registry` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Confirm Modelo 036 and Modelo 037 behavior and metadata remain unaffected by Modelo 145 successor work

## Scope

- `tests/domain/calculations/registry`

## Description

Add a censo-registry regression test that co-loads the new Modelo 145 registry snapshot before asserting Modelo 036 and Modelo 037 contracts.

Verify Modelo 036 still resolves as the active censo work-unit foundation with the committed event-kind vocabulary.

Verify Modelo 037 still resolves only as historical metadata, remains superseded by Modelo 036, and is still absent from active calculation-registry support.

## Outcome

`src/aeat/domain/calculations/registry/tests/test_censo_modelo_foundation.py` now confirms that Modelo 145 registry presence does not alter Modelo 036 active behavior or Modelo 037 historical metadata.

Verification:

- `uv run --no-sync ruff format --check src\aeat\domain\calculations\registry\tests\test_censo_modelo_foundation.py`
- `uv run --no-sync ruff check src\aeat\domain\calculations\registry\tests\test_censo_modelo_foundation.py`
- `uv run --no-sync pytest src\aeat\domain\calculations\registry\tests\test_censo_modelo_foundation.py -q`

## Notes

No blockers. No registry data or censo production behavior changed.
