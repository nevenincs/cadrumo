---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:185ce6567a7bfa6e4cafddb900687209fb2c553d392cf711f66e1044e9eea8f6'
step_id: 'S160'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S160 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The decide and implement the canonical live connected-proof gate composition and ## Scope

- `src/cadrumo/application/registry` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# decide and implement the canonical live connected-proof gate composition

## Scope

- `src/cadrumo/application/registry`

## Description

- Compose connected census checks from the canonical live authority, production ownership and workflow catalogues, and repository-root digest verification.
- Execute independently authored typed invoice inputs through canonical invoice construction and persistence, enrolled source resolution, registry calculation, atomic revision persistence, and encrypted reload.
- Keep the zero-connected census path free of fixture, storage, and key allocation.
- Prove source mutation changes both revision identity and primary fingerprint, missing primary identity fails closed, and ephemeral storage is removed on exit.

## Outcome

The canonical connected-proof composition now has one data-only fixture boundary and one composer-owned encrypted calculation lifecycle. Census assertions cannot author the expected workflow, destination, provenance, or stored revision, and the live authority adjudicates all axes conjunctively.

## Notes

Formal re-review passed with no Critical, High, or Medium findings. Six focused live-proof tests pass after the invoice-ingress and cleanup tightening; Ruff and the focused `ty` surface pass. A broader full-authority run was temporarily blocked after successful calculation persistence by unrelated concurrent operator-surface reconciliation work, and an intermediate collection was blocked by an unrelated concurrent `SCHEMA_REGISTRY` migration. Both shared-worktree conditions were outside S160 and were not repaired here.

