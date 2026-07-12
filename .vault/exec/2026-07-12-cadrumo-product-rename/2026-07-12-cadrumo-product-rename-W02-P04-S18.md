---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S18'
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
     The S18 and 2026-07-12-cadrumo-product-rename-plan placeholders are machine-filled by
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
     The Move the platform application-data root to Cadrumo and refuse detected former-product state and ## Scope

- `src/cadrumo/core/_config_state_root.py`
- `src/cadrumo/core/tests/test_config_state_root.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Move the platform application-data root to Cadrumo and refuse detected former-product state

## Scope

- `src/cadrumo/core/_config_state_root.py`
- `src/cadrumo/core/tests/test_config_state_root.py`

## Description

- Derive the installed application directory from canonical Cadrumo product identity.
- Detect a sibling former-product application root before returning installed state.
- Raise a typed refusal without opening, moving, re-keying, deleting, or adopting former state.
- Preserve the checkout-local `var/storage` development root unchanged.
- Exercise fresh Cadrumo reuse and former-state refusal through real temporary filesystem trees.

## Outcome

Installed resolution now returns `<platform-user-data>/cadrumo/storage` on Windows, Linux, and macOS. Checkout resolution remains `PROJECT_ROOT/var/storage`. Before an installed root is returned, the resolver checks only for the existence of the sibling retired application directory and raises `FormerProductStateError` when detected. The refusal happens before a Cadrumo directory is created and performs no former-state content access or mutation.

The focused clean-environment test run passed all ten state-root tests. The real-filesystem refusal proof retained the former marker bytes and directory while confirming that no Cadrumo directory appeared. Fresh Cadrumo state was created by the test consumer, read back, and resolved to the same sole root without a fallback.

## Notes

The canonical Step scope was expanded through the plan CLI to include the cohesive root test file required by the Step contract. The literal former directory name remains only as a refusal detector; it is not an alias, fallback, migration source, or accepted state root.
