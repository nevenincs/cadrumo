---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S390'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace import-centralization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S390 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Drop the dead OutputLanguage re-export from entrypoints.cli._config.__all__, confirming no live consumer imports it from that facade before removing it (the canonical source is aeat.core.i18n) and ## Scope

- `src/aeat/entrypoints/cli/_config/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Drop the dead OutputLanguage re-export from entrypoints.cli._config.__all__, confirming no live consumer imports it from that facade before removing it (the canonical source is aeat.core.i18n)

## Scope

- `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

- Confirmed via grep that no production or test consumer imports `OutputLanguage` from `entrypoints.cli._config` — the only re-export path was the `__all__` entry itself; every Typer option annotation inside the module uses the type internally, not through the facade re-export.
- Removed the `"OutputLanguage"` entry from `__all__`, keeping the internal `from ....core.external_constants import OutputLanguage` import (still used for the module's own Typer option type annotations).
- `aeat.core.i18n` remains the sole canonical facade for `OutputLanguage`, unaffected by this change.

## Outcome

Committed alongside S364, S368, S369, and S388 in one commit (`b6aafa707`). `pytest --collect-only -q src/aeat` clean; no consumer breakage since nothing imported it from this facade.

## Notes

None.
