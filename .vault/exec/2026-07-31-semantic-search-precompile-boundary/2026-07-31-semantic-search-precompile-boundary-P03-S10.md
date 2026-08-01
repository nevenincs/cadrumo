---
tags:
  - '#exec'
  - '#semantic-search-precompile-boundary'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:cbc50061bea2121862cfe2da83bce25a2603525f7fc3a1584d1bcd669787262c'
step_id: 'S10'
related:
  - "[[2026-07-31-semantic-search-precompile-boundary-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-search-precompile-boundary with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-07-31-semantic-search-precompile-boundary-plan placeholders are machine-filled by
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
     The Sweep every remaining install hint naming the retired extra from production strings, the extras-reporting half of this step being vacated by ADR Update 1 because config check never named a search extra and ## Scope

- `src/cadrumo/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Sweep every remaining install hint naming the retired extra from production strings, the extras-reporting half of this step being vacated by ADR Update 1 because config check never named a search extra

## Scope

- `src/cadrumo/`

## Description

- Sweep production strings under `src/cadrumo/` for install hints naming the retired `search` extra (`pip install`/`uv add` guidance, package-name references).
- The original row also instructed dropping the search capability from the `config check` extras-reporting surface; that half is vacated (ADR Update 1, point 1): `_check_cli.py` and `_check_payloads.py` never named a search extra, confirmed independently three times at HEAD (an executor read, a read-only inventory, and the ADR's own probe). The row was re-worded to its real half (the install-hint sweep) so no future reader fabricates the missing work or falsely marks it done under the original wording.

## Outcome

Landed as part of commit `13935ef3a2` "build(search): drop the search extra and its dependency refusal" (`THIRD_PARTY_NOTICES.md`, `dev/packaging/smoke_core.py`, and the deleted install-hint-bearing surfaces named there). Independently re-confirmed at current HEAD by this record: `rg -i "search"` over `src/cadrumo/entrypoints/cli/_config/_check_cli.py` and `_check_payloads.py` returns no match, and a broader `rg` for `cadrumo[search]` / `[search]` install-hint patterns and `extra.*=.*"search"` across `src/cadrumo/` returns no match. The step, as re-worded by ADR Update 1, is fully satisfied.

## Notes

None. The step's original wording named a subject (`config check` extras-reporting) that never existed in the codebase; ADR Update 1 vacated that half and re-scoped the row rather than the row being silently marked done against a fabricated action.
