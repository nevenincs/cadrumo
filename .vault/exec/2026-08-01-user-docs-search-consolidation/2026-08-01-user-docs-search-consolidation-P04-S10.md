---
tags:
  - '#exec'
  - '#user-docs-search-consolidation'
date: '2026-08-01'
modified: '2026-08-01'
body_schema: 'body-v1'
body_hash: 'sha256:c4968f8e7ff571ff66880ab09d14c9479c12a3a9bcc5c258079811c731245e8b'
step_id: 'S10'
related:
  - "[[2026-08-01-user-docs-search-consolidation-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace user-docs-search-consolidation with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S10 and 2026-08-01-user-docs-search-consolidation-plan placeholders are machine-filled by
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
     The Retire the pages-only CADRUMO_DOCS_PAGEFIND_MODE deploy value so every root builds the full record-injected index, updating the deploy-environment test to pin full mode and ## Scope

- `dev/deploy/docs_static_site.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Retire the pages-only CADRUMO_DOCS_PAGEFIND_MODE deploy value so every root builds the full record-injected index, updating the deploy-environment test to pin full mode

## Scope

- `dev/deploy/docs_static_site.py`

## Description

- Pin the deploy build environment's Pagefind contract to `full`, replacing the `pages` value that discarded every injected record from the published site.
- Record in the docstring why the key is pinned explicitly rather than left to the build default: an ambient value in the publishing session would otherwise narrow the shipped contract.
- Correct the localized-root build environment docstring, which described the retired page-only contract.
- Update the deploy-environment test to pin full mode, and add a test asserting every deploy root - English and each localized root - resolves the full contract through the build's own resolver, including against a hostile base environment that sets `pages`.

## Outcome

The deployed contract is now full mode on every root, as Update 1 of the governing ADR rules.

Measured before the change, against the live site: the deployed `pagefind-entry.json` carried one language and a page count of 75, with no injected records; the deploy environment's `pages` value was the sole cause.

The new assertions read the contract through `pagefind_index_mode` rather than comparing the raw string, so they pin the contract the build will actually select. The hostile-base case proves the explicit pin does work the build default could not.

Verification, all real counts: the deploy test module runs 12 tests, and the deploy modules together run 21, all passing. Mutation proof: restoring the `pages` value fails two of them, naming the divergence (`assert 'pages' == 'full'`); restoring `full` returns both to green.

## Notes

The change materially lengthens a publish. Injecting the full corpus of 7,890 records costs about fifteen minutes per root, measured, and the publisher builds four roots, so a publish gains roughly an hour. This is the ruled contract's real cost, not a defect, and every non-deploy build already paid it because full mode is the build default. It is called out because nothing in the ADR anticipated it and the operator should not meet it as a surprise mid-publish.

The `pages` mode itself is deliberately left standing in the build. After this change it has no production consumer, but retiring it would edit the build module and its tests, which belong to other steps; it is named here so the question is not lost.
