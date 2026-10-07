---
tags:
  - '#plan'
  - '#user-docs-weight'
date: '2026-10-06'
tier: L1
related:
  - '[[2026-10-06-user-docs-weight-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:742754bcb13d7c8066e82f1ed80c61b1f7319c568179d4edc338e4d956cba82e'
---

# `user-docs-weight` plan

## Description

Approved 2026-10-06. Basis: the operator's direction of that date, recorded in `2026-10-06-user-docs-weight-adr` ("We should not need to query and build the actual compiled documentation pages four times. That is wrong. The only difference is actual text."), which the plan executes.

The plan reaches the decision's two commitments in its order D5. S01 to S05 change what is shipped: the four built roots are factored into one structure and each language's text, and the desktop and the publisher compose pages from them. S06 to S08 change what is compiled: each localization mechanism emits its strings directly, its per-language build is retired, and after S08 the documentation is compiled once. S09 gives the site one search index, which the operator directed the same day (D6 of the decision): it follows S02 because it changes what a built root contains, and S03 stages what it produces.

## Steps

- [x] `S01` - Factor pages into one structure and each language's strings, recovered byte for byte; `dev/docs/shared_structure.py, dev/docs/tests/test_shared_structure.py`.
- [x] `S02` - Factor whole language roots: page structures, language text, files stored once and files kept per language, with a composer that rebuilds any root and a gate that compares it with the built one; `dev/docs/language_roots.py, dev/docs/tests/`.
- [x] `S09` - Build one search index for all languages at the site's apex: each page a record filtered by its language, each term, casilla, legal and CLI record indexed once, and the search controller filtering by the page's language and opening shared records inside it; `dev/docs/pagefind_index.py, dev/docs/pagefind_inject.py, dev/docs/build.py, dev/packaging/native/docs_build.py, docs/_static/cadrumo-docs.js, dev/docs/tests/`.
- [x] `S03` - Stage the package as one structure and each language's text, with a manifest that says how each address is served; `dev/packaging/native/docs_stage.py, native/package-layout.json`.
- [x] `S04` - Compose a page from its structure and the language's text in the documentation scheme handler, and state the layout in the contract; `native/desktop/src-tauri/src/docs/, native/CONTRACT.md`.
- [x] `S05` - Publish the site by composing each language's pages from the structure and the text; `dev/deploy/docs_static_site.py`.
- [x] `S06` - Emit every language's strings for the generated references from one projection and retire their per-language generation; `dev/docs/casilla_reference.py, dev/docs/legal_reference.py, dev/docs/glossary_reference.py, dev/docs/cli_reference.py`.
- [x] `S07` - Emit the site chrome's strings for every language from the catalogues; `dev/docs/site_chrome.py, docs/_templates/`.
- [x] `S08` - Emit the authored pages' strings from the gettext catalogues in the one compile, retire the per-language builds, and move the strict and completeness gates onto the composed pages; `dev/docs/build.py, dev/docs/i18n.py, dev/packaging/native/docs_build.py, dev/docs/tests/`.
- [x] `S10` - Make the local and CI flows compile the documentation once: the language recipes, the live preview's per-language rebuilds, the docs gates that the local gate and the repository-contract lane each run again, and the prove jobs that repeat them per interpreter; `justfile, .github/workflows/release.yml, dev/docs/serve.py, dev/docs/serve_languages.py`.
- [x] `S11` - Run each language-independent projection once per compile: the command tree written per root and the command walk the search records repeat per language; `dev/docs/cli_tree.py, dev/docs/terminology/cli_projection.py, docs/conf.py`.
- [x] `S12` - Build the packaged documentation once for every platform preset and key its cache on what it reads, not on the binary directory; `native/cmake/Docs.cmake, dev/packaging/native/action_cache.py`.
- [x] `S13` - Store the structure with one line terminator whatever platform compiled it, and compose each page with the terminator the composing platform's own build writes; `dev/docs/language_roots.py, dev/docs/compile_once.py, dev/docs/_locale_chrome.py`.

## Parallelization

S01 and S02 come first and in order; everything else reads their format. S09, S03 and S04 write disjoint files and may run at once, one writer each; S03's manifest names the one index S09 builds. S03 and S04 change files that other sessions hold uncommitted edits in (`dev/packaging/native/docs_stage.py`, `native/package-layout.json`, `native/CONTRACT.md`, the desktop host): each starts only after its holder has been asked through the session directory, and the two land together, because a staged package the handler cannot serve is a broken package. S05 is independent of S03 and S04. S06, S07 and S08 run in that order, one mechanism at a time, so the builds not yet retired stay as the oracle for the one being moved.

## Verification

- Every page of every language, composed from the structure and that language's text, equals the page that language's build produced, byte for byte. This holds after every Step for as long as a per-language build exists, and is the condition for retiring one.
- The staged documentation is measured before and after S03: pages of four languages near 83 MB instead of 290 MB, files identical in every language stored once.
- The packaged desktop serves every language's entry page, a casilla page and the search page through the scheme handler with the content security policy, script hashes and path containment it has today, and the packaged end-to-end test passes.
- The strict user-scope build, the completeness gate and the catalogue drift gate keep refusing what they refuse today; after S08 they read the composed pages.
- After S09 the site holds one search index: a query in each language returns that language's pages and the shared term, casilla, legal and CLI records, each opening inside the language being read, and the index is measured against the 63.5 MB and 60,232 files of four.
- After S08 a package build runs one documentation compile, and its duration is recorded beside the four-build duration it replaces.
