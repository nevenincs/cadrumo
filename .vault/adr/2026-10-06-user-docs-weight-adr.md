---
tags:
  - '#adr'
  - '#user-docs-weight'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:e85927b733200d837ae33dacf8182d05fb2b405eda7fa1eb91db063d45082480'
related:
  - "[[2026-10-06-user-docs-weight-research]]"
  - "[[2026-07-18-user-docs-localization-adr]]"
  - "[[2026-09-24-docs-build-performance-adr]]"
  - "[[2026-07-15-docs-terminology-search-adr]]"
  - "[[2026-09-27-website-repository-boundary-docs-static-delivery-adr]]"
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-06-10-docs-terminology-search-adr]]'
---

# `user-docs-weight` adr: `one documentation structure, each language as text` | (**status:** `accepted`)

Operator direction 2026-10-06: "We should not need to query and build the actual compiled documentation pages four times. That is wrong. The only difference is actual text." That direction is the authority for C1 and C2 below. The format and the order of work are how they are met and may change within them.

## Problem Statement

The documentation is compiled once per language and shipped once per language. Each compile repeats the registry projections, the CLI introspection, the sequence rendering, the theme rendering and the search indexing, and the package carries four complete trees. `2026-10-06-user-docs-weight-research` measured what the four trees have in common: 289.6 MB of pages are one 63.9 MB structure and 4.2 to 5.0 MB of strings per language, recoverable byte for byte.

## Considerations

- `2026-07-18-user-docs-localization-adr` fixes the catalogues, the language set and the completeness gate. Those stand. Its build matrix, one build and one site root per language, is the means this decision replaces.
- The published site is static files with no code at the edge (`2026-09-27-website-repository-boundary-docs-static-delivery-adr`), and every page must work without JavaScript (`2026-09-24-docs-build-performance-adr`). A reader of the site must therefore receive a complete page.
- The desktop serves the documentation through its own scheme handler, so it can compose a page when it is requested.
- Recorded command output stays English in every language, and the search index is one per language (`2026-07-15-docs-terminology-search-adr`, D5).

## Considered options

- Compress or delta-encode the four built trees. Smaller on disk, but the four compiles remain and the repetition is stored instead of removed. Rejected.
- Substitute text in the browser. Breaks the published site without JavaScript. Rejected.
- One structure and one list of strings per language, composed by whoever serves the page. Chosen.

## Constraints

- Composing the structure with a language's strings must give exactly the page that language's own build gives, for as long as such a build exists to compare with.
- A reader never sees another language's text where a translation is missing: the completeness gate of the localization decision still refuses an incomplete catalogue before anything is composed.
- The address of every page in every language stays what it is.

## Implementation

- C1, the commitment on what is shipped: the documentation is one structure and, for each language, its text. The structure holds every byte the languages share. A language adds only strings, and the files that are not pages and differ by language. English is a language like the others.
- C2, the commitment on what is compiled: the documentation is compiled once. A language's text comes from its catalogues, not from compiling the pages again.
- D1, format: a page's structure is its bytes with a slot number, delimited by U+E000 and U+E001, wherever the languages differ. A language's text is one ordered list of strings indexed by slot number; numbering is shared by all pages, so a string that recurs is stored once. A page that already contains a delimiter is refused (`dev/docs/shared_structure.py`).
- D2, proof: a gate composes every page in every language and compares it with that language's built page, byte for byte.
- D3, the desktop package: one structure tree, one text file per language, one copy of each file that is identical in every language, and per language only the files that differ and are not pages. The scheme handler composes a page on request. The staging manifest says how each address is served.
- D4, the published site: the publisher composes each language's pages from the structure and the text into the static roots it uploads.
- D5, the order in which C2 is reached: until a localization mechanism emits its strings directly, that mechanism's per-language build stays as the source of its strings and as the oracle for D2. The mechanisms move one at a time, each proven by D2 against the build it retires: the generated references first (casilla, legal, glossary and CLI pages, which hold most of the structure and all of the registry queries), then the site chrome, then the authored pages translated through gettext.
- D6, one search index. Operator direction 2026-10-06: "ONE index because it already carries all languages and we filter." The site has one Pagefind index, stored once at the site's apex and loaded by every language's pages. A page is one record that carries its own language as a filter. A term, casilla, legal or CLI record is indexed once, carries every language's text as it does today, and matches every language's filter. The search controller filters by the language of the page it runs on and opens a cross-language record inside that language's root. The index was 63.5 MB in 60,232 files across four languages, most of it the same casilla records four times.

Affected wording in `2026-07-18-user-docs-localization-adr`: its Implementation item "Build matrix" and its Constraint on per-language `-W` builds describe the means this decision replaces, and remain in force only as D5 says, mechanism by mechanism. D4 of `2026-09-24-docs-build-performance-adr` (language roots build concurrently) lapses when the last per-language build is retired. D6 replaces the per-language index of D5 in `2026-06-10-docs-terminology-search-adr` and the localization decision's constraint that the index is built once per language; the record kinds, their ranking tiers and their destinations stay as those decisions set them.

Affected wording in `2026-10-04-desktop-shell-adr`: it places the documentation under `docs/user/` in the published layout, English at the top and the other languages under `<lang>/`, with a manifest of languages, entries and a sha256 inventory. Under D3 that layout is the layout of the addresses the scheme handler answers, which the language switcher depends on, and no longer the layout of the files stored. The inventory covers the files stored, and the manifest also says how each address is served. Its path containment, closed media-type table, script hashes and content security policy apply to the composed response as they did to the file.

- D7, how the one compile carries every language. Operator direction 2026-10-06: the documentation must not be compiled once per language, in the package build, the published site, CI or a local build; "imagine if we supported localization for 40 languages". The compile's output is the structure itself: wherever a string depends on the language the compiled page carries a slot, and each language's string for that slot is collected beside it. Three sources fill slots. The generated references render every language from one projection, and their sources are factored before they are compiled. Theme, Sphinx and site-chrome strings are answered by a translator that returns a slot and records each language's catalogue value. An authored page's translatable messages become slots through a generated catalogue, and each language's translation of a message is rendered once, as a fragment in its page's own context. A language then costs the rendering of its text and nothing else, so adding one adds no compile. The published site is composed from the same structure and text, with the one index of D6. These three mechanisms are how C2 is met and may change; the commitment is that no step compiles pages per language. Each is proven by D2 against that language's own build before the build is retired, and a difference kept on purpose, such as an anchor that no longer depends on the language, is listed with its reason where the comparison is made.

## Rationale

The languages differ in text and in nothing else, so text is the only thing a language should cost to compile, ship and store. Factoring makes that literal, and it is checkable: the composed page either equals the built one or it does not. Moving one mechanism at a time keeps a full oracle beside every change instead of replacing four builds on trust.

## Consequences

- The pages of four languages weigh about 83 MB instead of 290 MB, and non-page files identical across languages are stored once.
- The desktop's scheme handler gains composition, and the package contract changes with it.
- Each retired per-language build removes its share of the compile; when the last is gone the documentation is compiled once.
- A structure is not a page a browser can open; anything that reads the package's files directly must compose first.
- Search works across languages from one index: a reader sees pages in the language being read, and the term, casilla, legal and CLI records every language shares.
