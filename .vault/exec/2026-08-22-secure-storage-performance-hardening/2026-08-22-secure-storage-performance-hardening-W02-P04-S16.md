---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:ecdde0131f04683a9fba5c1614a52922877fb8217048bc782293b1266ebe63bb'
step_id: 'S16'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace secure-storage-performance-hardening with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S16 and 2026-08-22-secure-storage-performance-hardening-plan placeholders are machine-filled by
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
     The Replace hidden first-party function-local coupling with owned lazy public handler and schema boundaries referenced only by CommandSpec targets and ## Scope

- `src/cadrumo/entrypoints/cli/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace hidden first-party function-local coupling with owned lazy public handler and schema boundaries referenced only by CommandSpec targets

## Scope

- `src/cadrumo/entrypoints/cli/`

## Description

- Move executable-root and app-root handlers from the CLI assembly facade to an owned
  lazy public target module.
- Move the complete root helper cluster to one canonical support owner and remove the
  facade-to-handler cycle without aliases or duplicate implementations.
- Repoint CommandSpec handler targets and enroll every dynamic handler module in a
  static facade-import prohibition covering direct, aliased, relative, and literal
  dynamic import forms.

## Outcome

Every current root, group, and leaf handler resolves through an owned public target;
none targets or imports the CLI package facade. The graph-import test has no bootstrap
escape hatch. Six focused tests and Ruff pass, and independent re-review confirms the
original architectural finding is resolved.

## Notes

The first implementation moved the public callbacks but still imported six private
facade helpers. Review blocked that cosmetic split. The final implementation relocates
the helpers themselves and adds an executable regression gate. Harness and client
shipping surfaces were not modified.
