---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S05'
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
     The S05 and 2026-07-06-cross-period-prorrata-plan placeholders are machine-filled by
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
     The declare the PROFILE_PRORRATA_REGISTER FINANCIAL bucket-local secure-object namespace singleton and export it from the storage facade, mirroring PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE and ## Scope

- `src/aeat/adapters/persistence/storage/_namespace_registry.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# declare the PROFILE_PRORRATA_REGISTER FINANCIAL bucket-local secure-object namespace singleton and export it from the storage facade, mirroring PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE

## Scope

- `src/aeat/adapters/persistence/storage/_namespace_registry.py`

## Description

- Declare the `PROFILE_PRORRATA_REGISTER_NAMESPACE` FINANCIAL bucket-local secure-object singleton in `src/aeat/adapters/persistence/storage/_namespace_registry.py`, mirroring `PROFILE_BIENES_INVERSION_IVA_REGISTER_NAMESPACE` (namespace `aeat.persistence.profile.prorrata_register`, singleton `default` key, structured-custody).
- Enroll it in the `STORAGE_NAMESPACE_REGISTRY` namespaces tuple and the module `__all__`.
- Re-export it from the storage facade `src/aeat/adapters/persistence/storage/__init__.py` (import plus `__all__`).

## Outcome

The namespace is registered and discoverable; the storage namespace-registry conformance suite recognises it (31 passed). FINANCIAL sensitivity keeps the taxpayer's per-ejercicio percentages encrypted at rest, never plaintext.

## Notes

None.
