---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:a13dedce2d23adc9229e3d62e2d9567987ffd0271fd7ad9f982d77ca20e40e0b'
step_id: 'S90'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S90 and 2026-08-11-tui-architecture-plan placeholders are machine-filled by
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
     The Remove legacy TUI exports and package registrations from the inbound adapter namespace and ## Scope

- `src/cadrumo/adapters/inbound/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Remove legacy TUI exports and package registrations from the inbound adapter namespace

## Scope

- `src/cadrumo/adapters/inbound/__init__.py`

## Description

- Remove the retired TUI package registration from the import-linter configuration.
- Remove every TUI import, export, attribute, and registration from the inbound adapter namespace.
- Keep the inbound namespace documentation-only and free of forwarding behavior.
- Confirm exact dotted and path reference sweeps are empty outside the planted detector and its tests.

## Outcome

The inbound adapter namespace contains no TUI registration, import, export, attribute, facade, shim, or re-export. Import resolution for the retired package returns no module, and live source/dev searches find no consumers.

The zero-remnant detector returns an empty result, the complete 63-test migration/import-hygiene gate passes, and independent review approved the namespace cleanup.

## Notes

The namespace deliberately defines no `__all__`; concrete inbound parsers remain owned by their focused child packages. The registration and package cleanup landed in `ebeb4507a3`.
