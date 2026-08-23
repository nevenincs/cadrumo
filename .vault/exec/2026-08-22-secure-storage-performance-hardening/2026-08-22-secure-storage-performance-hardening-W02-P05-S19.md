---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:651c317f603fc368702495e5cb6fde84f6d021b46625aad444ae9fd61d34b91a'
step_id: 'S19'
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
     The S19 and 2026-08-22-secure-storage-performance-hardening-plan placeholders are machine-filled by
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
     The Move heavy workflow contracts into cohesive sibling modules loaded only by owning commands and ## Scope

- `src/cadrumo/application/workflow/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Move heavy workflow contracts into cohesive sibling modules loaded only by owning commands

## Scope

- `src/cadrumo/application/workflow/`

## Description

- Atomically replace the broad workflow model monolith with cohesive state and run
  contract owners plus a shared period-identity leaf.
- Repoint the lazy facade, internal consumers, tests, and architecture ledger to the
  canonical owners and delete the old module without a bridge.
- Prove public object identity, state persistence, run persistence, and declaration
  helper behavior through focused tests.

## Outcome

State-only consumers no longer construct run/deadline/browser contracts, and run-only
consumers no longer construct encrypted state/profile contracts. The retired model
module has no production or architecture-ledger reference. Ruff passes and 34 focused
tests pass; independent review approved the split.

## Notes

The import-linter ledger test still reports four pre-existing missing TUI-launcher rows
outside this step. No harness or external-client file was modified.
