---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:1c4765e87f71b810af0647a0060cab1f4d6d80985684cdb5e9269155146b1da7'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `W08.P26.S372 independent code review`

## Scope

Independent read-only review of `W08.P26.S372` against the accepted navigation-join decision, the Home product-design research, and the live prototype and focused tests. The review covered candidate differentiation, immutable projection use, authority boundaries, operator copy, agenda evidence, keyboard semantics, semantic identities, seven-state truthfulness, responsive structure, and focused gates.

## Findings

### due-agenda-evidence | medium | Closed: due-driven agenda now distinguishes local and AEAT evidence per row

The initial implementation rendered only date, declaration, and period status in the due-driven agenda while exposing local and AEAT axes only in task-launcher detail. That made the favored candidate less truthful than the projection and the product-design contract. The live correction adds separate human-facing Local and AEAT columns and an exact regression test without displaying raw enum values.

### escape-return | medium | Closed: both prototype screens now provide an observable Escape return action

The initial screens had no Escape binding; a compositor probe confirmed Escape left the screen mounted. The live correction binds Escape to the prototype return action and tests the observable action flag, restoring the specified keyboard contract without adding navigation or business authority.

### agenda-focus-identity | medium | Closed: agenda identity is stable across due-date corrections

The initial agenda row identity included `due_on`, so a holiday or deadline correction changed identity for the same Modelo/year/period case and defeated semantic focus restoration. The live correction keys agenda rows by their natural declaration address and adds an identity-stability test proving due-date changes do not change the target.

### action-key-collision | low | Closed: action identity disambiguates reason while remaining stable across ranking

The initial action identity omitted both rank and reason, allowing two otherwise valid projected actions with the same declaration address and action id but different reasons to collide as `DataTable` keys. The live correction includes the application reason in identity while continuing to exclude mutable display rank, with collision and reorder-stability coverage.

## Recommendations

No open recommendation remains from this review. All three medium findings and the low finding were corrected in scope. The slice is safe to close with no open high or medium issue.

Focused verification completed with all candidate tests passing under the explicit integration marker selection. The review also confirmed two genuinely different candidates over the exact injected immutable projection, a single outer page scroll, compact and wide layout classes, seven synthetic authority states without false zeroes, human-facing reason and status copy, and no repository, network, CLI, adapter, calculation, classification, reconciliation, or action-execution authority in the prototype module.

