---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:8143955a65d4ce5ff4625851c27e014ab09f92c388566be1647fd5d7123b13c0'
step_id: 'S151'
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
     The S151 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The emit IVA wallet decisions as immutable event-key primaries and parent their authority-source contributors to the decision provenance node and ## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/application/aggregation` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# emit IVA wallet decisions as immutable event-key primaries and parent their authority-source contributors to the decision provenance node

## Scope

- `src/cadrumo/application/calculations`
- `src/cadrumo/application/aggregation`

## Description

- Use `iva_wallet_decision_event_key` as the durable decision primary reference.
- Fingerprint the canonical decision payload on that primary.
- Parent wallet and local-recurrence authority contributors to the decision node.
- Verify exactly one primary and explicit contributor edges.

## Outcome

IVA wallet provenance distinguishes the resolver-owned reconciliation decision from the evidence that informed it.

## Notes

Implemented in shared-worktree commit `31e504c55b`. Contributors do not borrow the decision fingerprint when no canonical contributor-content digest exists.
