---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S07'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-period-prorrata with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S07 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
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
     The add the application service facade to declare, list, and get the per-ejercicio register entry, exposed only through the package top-level __all__ and ## Scope

- `src/aeat/application/prorrata_register/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# add the application service facade to declare, list, and get the per-ejercicio register entry, exposed only through the package top-level __all__

## Scope

- `src/aeat/application/prorrata_register/__init__.py`

## Description

- Add the `ProrrataRegisterService` application facade in `src/aeat/application/prorrata_register/__init__.py` (thin orchestration over `ProrrataRegisterRepository`) exposing `declare`, `list_all`, and `get`, all through the package top-level `__all__`.
- Pin the new production `application -> adapters` edge in the layered-architecture ledger (`.importlinter`), mirroring the `bienes_inversion` facade entry.

## Outcome

The facade composes over the encrypted repository without re-implementing any write path; `get` reads one entry by `(ejercicio, sector)` key. All five import contracts KEPT, including the layered-architecture ledger.

## Notes

The layered-architecture contract fails a new production `application -> adapters` edge loudly by design; the ledger entry `aeat.application.prorrata_register -> aeat.adapters.**` was added in alphabetical position, exactly as `aeat.application.bienes_inversion` is pinned.
