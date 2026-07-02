---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S388'
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
     The S388 and 2026-07-01-import-centralization-plan placeholders are machine-filled by
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
     The Exclude __main__.py modules from the shim/pure-reexport classifier in the import-hygiene scanner, since a module whose only statement is from .cli import app plus an if __name__ == "__main__": app() guard is the standard entrypoint pattern, not a Family-2 shim and ## Scope

- `dev/import_hygiene_scan.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Exclude __main__.py modules from the shim/pure-reexport classifier in the import-hygiene scanner, since a module whose only statement is from .cli import app plus an if __name__ == "__main__": app() guard is the standard entrypoint pattern, not a Family-2 shim

## Scope

- `dev/import_hygiene_scan.py`
- `dev/tests/test_import_hygiene_scan.py`

## Description

- Excluded `__main__.py` modules from `find_shim_modules`'s pure-reexport classifier: the standard `from .cli import app` plus `if __name__ == "__main__": app()` entrypoint shape was false-positiving as a Family-2 shim (`src/aeat/locales/__main__.py`).
- Added two real-behavior regression tests against the live tree: one confirming `locales/__main__.py` is no longer flagged, one confirming a genuine pure-reexport module (`entrypoints/cli/_schemas.py`) is still flagged, guarding against an over-broad exclusion.
- Confirmed via a fresh scanner run that `locales/__main__.py` no longer appears under the Family-2 findings.

## Outcome

Committed alongside S364, S368, and S369 in one commit (`b6aafa707`). `dev/tests/test_import_hygiene_scan.py` (7 tests) green; `pytest --collect-only -q src/aeat` clean.

## Notes

None.
