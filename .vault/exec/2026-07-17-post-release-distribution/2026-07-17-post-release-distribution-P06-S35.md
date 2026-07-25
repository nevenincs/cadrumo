---
tags:
  - '#exec'
  - '#post-release-distribution'
date: '2026-07-25'
modified: '2026-07-25'
step_id: 'S35'
related:
  - "[[2026-07-17-post-release-distribution-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace post-release-distribution with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S35 and 2026-07-17-post-release-distribution-plan placeholders are machine-filled by
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
     The DONE 7d20b2d984, concurrent publication is closed rather than only recorded, the marketplace push re-clones and re-applies on a rejected push because concurrency groups are per-repository and cannot serialise across product repos, and refuses after three lost races. GATE, a workflow conformance test pins the retry, the re-clone inside the loop, and the fail-closed exhaustion and ## Scope

- `.github/workflows/publish-release.yml` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# DONE 7d20b2d984, concurrent publication is closed rather than only recorded, the marketplace push re-clones and re-applies on a rejected push because concurrency groups are per-repository and cannot serialise across product repos, and refuses after three lost races. GATE, a workflow conformance test pins the retry, the re-clone inside the loop, and the fail-closed exhaustion

## Scope

- `.github/workflows/publish-release.yml`

## Description

- Wrap the marketplace push in a re-clone-and-reapply retry.
- Refuse after three lost races rather than reporting success on an unpublished marketplace.
- Pin the retry, the in-loop re-clone, and the fail-closed exhaustion with a workflow conformance test.

## Outcome

Concurrent publication is closed rather than only recorded. Two products releasing into one shared marketplace can interleave clone and push, making the later push a non-fast-forward.

## Notes

A repository-level concurrency group cannot solve this: groups are scoped per repository, so they cannot serialise across separate product repositories. The retry is safe to repeat because the publish step is a pure function of the marketplace tree and the cohort. This is an expected operating condition under a shared marketplace rather than an edge case, which is why it was worth closing now. Semantic search was degraded for the whole of this work: the code index served roughly a fifth of the tree while reporting itself healthy, so a search miss was worthless as evidence. Discovery was done by direct directory listings, file reads, and targeted pattern search instead.
