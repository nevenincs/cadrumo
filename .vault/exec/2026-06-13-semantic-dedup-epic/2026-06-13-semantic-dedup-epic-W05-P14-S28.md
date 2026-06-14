---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S28'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S28 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
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
     The C2-2 Extract a parameterized uppercase-alpha and unique-tuple validator factory and route the copies through it and ## Scope

- `src/aeat/domain/calculations/registry/_binding_selector_utils.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# C2-2 Extract a parameterized uppercase-alpha and unique-tuple validator factory and route the copies through it

## Scope

- `src/aeat/domain/calculations/registry/_binding_selector_utils.py`

## Description

- Verified the pydantic v2 `field_validator(...)(factory("label"))` wiring in a
  standalone check before touching production (no factory-validator precedent
  in the codebase).
- Added `uppercase_alpha_code(label)` and `unique_tuple(label)` factories to
  `_binding_selector_utils` (with `RegistryValidationError`).
- Routed 7 uppercase-alpha validators (invoice, counterpart, withholding,
  detail_record x4) and 4 pure unique-tuple validators (invoice, counterpart,
  withholding, previous_filing) through the factories via the assignment form.
- Left the clave validators and invoice `_claves_uppercase_unique` in place
  (constraint-divergent: extra AEAT clave-membership check).

## Outcome

Committed as `ea84618ce`, tagged `relocation:uppercase_alpha_code` (6 files,
+55/-74). Ruff clean; 368 registry binding/observation tests green.

## Notes

The unified message `"<label> must be uppercase alphabetic"` satisfies every
existing assertion: the two two-`if` sites' tests match `"country_code must be
uppercase"` as an `re.search` substring, and the detail_record tests match the
full label-specific string exactly (labels chosen as country_code / "ISO code"
/ member_state_code to match). Behaviour (accept/reject set) is identical; only
the granular two-message wording on two sites collapsed to one.
