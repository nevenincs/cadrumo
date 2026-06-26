---
tags:
  - '#exec'
  - '#binding-vocabulary-cli-cohesion'
date: '2026-06-26'
modified: '2026-06-26'
step_id: 'S19'
related:
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace binding-vocabulary-cli-cohesion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-06-26-binding-vocabulary-cli-cohesion-plan placeholders are machine-filled by
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
     The Assert and document the three prefill tiers are distinct and not merged: relation prefill (_relation_prefill.py, RelationPrefillSourceResolver), previous-filing direct carry (_binding_prefill.py), and AEAT borrador pre-fill (registry _schema.py aeat_prefilled / borrador-fed typed_enum) and ## Scope

- `add a clarifying module-docstring line on each where the distinction is not already explicit`
- `one atomic commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/calculations/_relation_prefill.py`
- `src/aeat/application/calculations/_binding_prefill.py`
- `src/aeat/domain/calculations/registry/_schema.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Assert and document the three prefill tiers are distinct and not merged: relation prefill (_relation_prefill.py, RelationPrefillSourceResolver), previous-filing direct carry (_binding_prefill.py), and AEAT borrador pre-fill (registry _schema.py aeat_prefilled / borrador-fed typed_enum)

## Scope

- `add a clarifying module-docstring line on each where the distinction is not already explicit`
- `one atomic commit`
- `collect-only clean before commit`
- `apply-cached own-only`
- `abort-on-WIP`
- `src/aeat/application/calculations/_relation_prefill.py`
- `src/aeat/application/calculations/_binding_prefill.py`
- `src/aeat/domain/calculations/registry/_schema.py`

## Description

- Add a clarifying tier-distinction line to the relation prefill module docstring naming it the relation tier and pointing at the other two tiers.
- Add a clarifying tier-distinction line to the previous-filing direct-carry prefill module docstring naming it the previous-filing tier.
- Add an inline comment on the registry `aeat_prefilled` field naming it the third, AEAT-live borrador pre-fill tier and stating the three must not be merged.

## Outcome

Landed as one atomic commit (`7cf62cc05`). Docstring/comment-only, behaviour-preserving. collect-only clean, ruff clean, the 24 prefill and relation tests green. The three prefill modules were already distinctly named and the two application modules already cross-referenced each other; this Step makes the three-way tier distinction (including the AEAT borrador tier) explicit on each surface.

## Notes

All three files were clean of peer WIP. No merge of the prefill modules was performed (none was warranted): they name three different mechanisms and sources and share only the word "prefill".
