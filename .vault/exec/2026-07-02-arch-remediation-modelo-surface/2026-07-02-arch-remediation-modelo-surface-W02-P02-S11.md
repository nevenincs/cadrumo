---
tags:
  - '#exec'
  - '#arch-remediation-modelo-surface'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S11'
related:
  - "[[2026-07-02-arch-remediation-modelo-surface-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace arch-remediation-modelo-surface with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S11 and 2026-07-02-arch-remediation-modelo-surface-plan placeholders are machine-filled by
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
     The Consume the single iva-wallet ownership declaration from the registry relation-source validator, removing the inline _IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS carve-out and ## Scope

- `src/aeat/domain/calculations/registry/_validate_relation_sources.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Consume the single iva-wallet ownership declaration from the registry relation-source validator, removing the inline _IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS carve-out

## Scope

- `src/aeat/domain/calculations/registry/_validate_relation_sources.py`

## Description

- Replace the inline literal `_IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS` frozenset in the relation-source validator with the public canonical set.

## Outcome

The registry relation-source collision gate consumes the single declaration; the duplicated literal is gone. Commit `e353111d8`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
