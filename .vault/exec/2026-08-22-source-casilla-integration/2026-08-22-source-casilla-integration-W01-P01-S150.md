---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b9fc57616c4ea36d53387e0fc8b243394205021ac5e864a467b8568638daed8a'
step_id: 'S150'
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
     The S150 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The migrate every calculation-source provenance constructor, serializer, merge, and revision-identity payload without defaults, aliases, or dual-read compatibility and ## Scope

- `src/cadrumo/application`
- `src/cadrumo/adapters`
- `src/cadrumo/domain` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# migrate every calculation-source provenance constructor, serializer, merge, and revision-identity payload without defaults, aliases, or dual-read compatibility

## Scope

- `src/cadrumo/application`
- `src/cadrumo/adapters`
- `src/cadrumo/domain`

## Description

- Migrate every production provenance constructor to the required lineage fields.
- Project the complete graph through persistence, CLI payloads, revision hashes, and event trace digests.
- Remove the retired provenance fields without aliases, defaults, or dual readers.
- Extend encrypted-load rejection coverage for every required identity axis.

## Outcome

All production constructors and serialization boundaries use the single canonical provenance shape; legacy payload omissions are rejected.

## Notes

Implemented in shared-worktree commit `31e504c55b`; the shared-commit incident described by S149 applies.
