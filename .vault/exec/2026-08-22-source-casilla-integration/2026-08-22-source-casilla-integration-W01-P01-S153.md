---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:7827d0df6008005d9cfa3ca673be966843a7a39446f6a309e1cff64071b1fa46'
step_id: 'S153'
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
     The S153 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The make live connectivity authority accept exactly one resolver-matching primary and reject contributor-only, ambiguous, orphaned, drifted, or malformed provenance graphs and ## Scope

- `src/cadrumo/application/registry` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# make live connectivity authority accept exactly one resolver-matching primary and reject contributor-only, ambiguous, orphaned, drifted, or malformed provenance graphs

## Scope

- `src/cadrumo/application/registry`

## Description

- Match encrypted connectivity proof only against resolver-owned `PRIMARY` rows.
- Refuse contributor-only matches, duplicate primaries, orphan contributors, and identity drift.
- Validate graphs at calculation-resolution, merge, persisted-revision, and live-authority boundaries.

## Outcome

The live authority treats contributors only as support and accepts exactly one truthful primary matching the claimed resolver, source, reference, and fingerprint.

## Notes

Implemented principally in shared-worktree commit `31e504c55b`; the merge-order correction is a follow-up. Selected source-mesh, encrypted-persistence, wallet, and authority coverage passed 85 tests.
