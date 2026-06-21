---
tags:
  - '#exec'
  - '#silent-zero-base-aggregation'
date: '2026-06-20'
modified: '2026-06-20'
step_id: 'S09'
related:
  - "[[2026-06-19-silent-zero-base-aggregation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace silent-zero-base-aggregation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S09 and 2026-06-19-silent-zero-base-aggregation-plan placeholders are machine-filled by
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
     The bind the recargo casillas, update the M303 manifest and construct, and add a real-behavior test that a recargo supplier's recargo cuota aggregates instead of reporting zero and ## Scope

- `src/aeat/_data/registry/aeat/modelos/303/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# bind the recargo casillas, update the M303 manifest and construct, and add a real-behavior test that a recargo supplier's recargo cuota aggregates instead of reporting zero

## Scope

- `src/aeat/_data/registry/aeat/modelos/303/`

## Description

Bound the M303 recargo cuota casillas and closed the recargo silent zero.

- Set casillas 158 (0.5%), 21 (1.4%), 24 (5.2%) to `input_kind = bound` with their
  recargo binding and added `ley-37-1992:art-161` to each casilla's legal_refs.
- Added the three casillas to the M303 completeness manifest and the three
  bindings + three casillas to the construct in `revision.toml`, with art-161 added
  to the construct legal_refs so the three-layer coverage check holds.
- Updated the M303 calculate test binding-value maps (registry, compensacion-carry,
  special-case routing) to supply the new recargo bindings.

Files under
`src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/` (casillas,
completeness_manifest, revision.toml) plus the affected test binding maps.

## Outcome

The registry loads with the recargo binds; the M303 recargo casillas leave the
manifest-drift closure-only set (only the peer's 01/04/07/28 base-binding drift
remains). The full registry+aggregation+ledger sweep: 3745 passed, the only two
reds being pre-existing peer-owned gates (M303 base manifest drift; a peer
iva-wallet tautology test). The recargo cuotas now aggregate instead of reporting
zero.

## Notes

The M303 casilla files carried stale (~35h) uncommitted peer base-binding work in a
different region; the recargo edits were made additively without disturbing the
peer's casilla 01/04/07/28 changes, and nothing was committed.
