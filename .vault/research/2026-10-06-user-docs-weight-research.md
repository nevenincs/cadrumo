---
tags:
  - '#research'
  - '#user-docs-weight'
date: '2026-10-06'
modified: '2026-10-06'
body_schema: 'body-v2'
body_hash: 'sha256:a3495fc026d3bcfc3133b20441cab3f09547ecd967e7b5c457c8bd2a93577345'
related:
  - "[[2026-07-18-user-docs-localization-adr]]"
  - "[[2026-07-13-docs-cli-sequences-adr]]"
  - "[[2026-09-24-docs-build-performance-adr]]"
  - "[[2026-07-15-docs-terminology-search-adr]]"
---

# `user-docs-weight` research: `where the bundled user documentation's weight comes from and what removes it`

The Windows package 0.5.1 b2115 carried 432 MB of user documentation in 62,771 files, a complete tree per language. The question was which of that weight is accident, which is decided, and what would remove it. Measured on 2026-10-06 on a snapshot of the working tree (commit `af1fb06015`), one English desktop root was 109.0 MB in 15,702 shippable files. The changes made the same day inside existing decisions bring it to 93.8 MB. The decisive finding is that a translated page is the English page with different text in it: the four roots hold 289.6 MB of pages, and factored they are one 63.9 MB structure plus 4.2 to 5.0 MB of strings per language, recovered byte for byte. After that, the search index is the largest part of what a language adds.

## Findings

### A language is 4 to 5 MB of text over a structure every language shares

No page file is identical between two language roots, but their markup is. Compared piece by piece, the Spanish pages differ from the English ones in text runs and attribute values (`title`, `aria-label`, `lang`), in the language switcher, in one script tag, and in about 25 places where a translation adds inline emphasis. `dev/docs/shared_structure.py:129` factors each page into the bytes all languages share, with a numbered slot wherever they differ, and one flat list of strings per language. Over the 561 pages of the four roots built on 2026-10-06:

| | MB |
| --- | --- |
| Pages as built, four languages | 289.6 |
| One structure | 63.9 |
| English strings | 4.2 |
| Spanish strings | 4.8 |
| Catalan strings | 4.8 |
| Hungarian strings | 5.0 |
| Structure and four languages | 82.7 |

There are 279,687 slot occurrences and 37,695 distinct slots; a language's strings deflate to about 1.1 MB. Composing the structure with each language's strings reproduced all 2,244 pages exactly, in 29 seconds for the whole set. Of the other files, 61 are identical in every language (7.2 MB once: static assets, the image, downloads) and 60,232 differ, all but 0.02 MB of them the Pagefind index (63.5 MB across the four languages).

An earlier reading of this record compared whole pages, found none identical, and concluded nothing could be shared. That was the wrong test: the unit that repeats is the structure inside the page, not the page file.

### What was removed on 2026-10-06 without changing a decision

English desktop root, before and after, in MB:

| Area | Before | After | Cause removed |
| --- | --- | --- | --- |
| `_generated/legal` (185 pages) | 14.0 | 8.6 | each page's sidebar listed the 184 other documents (`dev/docs/navigation.py:65`); theme variables in every head |
| `_generated/casillas` (59 pages) | 35.0 | 32.0 | a class attribute on each of about 79,900 legal links and 13,133 index chips (`dev/docs/casilla_legal_grounding.py:162`) |
| `technical` (232 pages) | 16.2 | 14.1 | 6 KB of theme variables and 2.3 KB of chrome strings inline in every head (`dev/docs/shared_page_assets.py:1`) |
| root files | 2.1 | 0.0 | Sphinx's own `searchindex.js`, which no page reads (`docs/conf.py:1732`) |
| `_static` | 5.8 | 4.1 | the landing image copied to both `_static` and `_images` |
| all other pages | 17.1 | 16.3 | the same head blocks; Open Graph tags in the desktop flavor |
| images and downloads | 2.6 | 2.6 | |
| Pagefind index | 16.3 | 16.1 | recorded JSON envelopes indexed as page text (`docs/pagefind.yml:26`) |
| Total | 109.0 | 93.8 | |

A deflate estimate of the shippable files falls from 30.5 MB to 26.6 MB. The build no longer writes the 39 MB `_sources` copy of every page into each root (`docs/conf.py:415`). The package staging scan accepts the result with no refused reference and the same five inline-script hashes.

### Casilla pages are 32 MB per language because every card renders its full provenance

The 59 modelo pages hold 13,133 cards. Their legal-basis blocks are 12.3 MB, of which the links are 8.6 MB, and their registry-identifier disclosures are 7.3 MB. D6 of `2026-07-15-docs-terminology-search-adr` requires each entry to render the record's `legal_refs`, `source_refs`, `segmento` and `source_revisions`, and `dev/docs/tests/test_casilla_anchor_parity.py:102` gates it per entry. 6.2 MB of the link markup repeats references that every card of the same section shares; on Modelo 200 about 2,900 of 3,731 cards cite article 19 of Ley 27/2014, and a sampled card cites 17 articles of that law. Whether those are per-casilla grounding or a section-level basis copied onto each casilla in the registry was not investigated.

### Recorded JSON envelopes are 8 MB per language, and 21 frames hold most of it

297 `<pre>` blocks hold JSON command envelopes, 8.1 MB with markup in each language. 21 recorded frames exceed the 64 KiB advisory (`dev/docs/sequences/checks.py:91`) and hold 5.9 MB of golden text; four of them hold 3.8 MB (`renta-assembly-requires` frame 0, `review-values-relation` frame 3, `modelo-100-renta-2025` frame 2, `modelo-100-inspect-inputs` frame 5, each about 0.9 to 1.0 MB). A3 of the output weight amendment in `2026-07-13-docs-cli-sequences-adr` already says a reader-facing frame prints text unless a capture, an expectation or the page's teaching needs JSON; A4 makes the limit an advisory, and the same amendment rejects truncating displayed output. These frames were left untouched: `dev/docs/sequences/` had another session's uncommitted edits, and a refresh needs a tree where the product runs.

### The search index repeats every casilla record in every language

A root's Pagefind index is 16 MB in about 15,100 files. 13,133 fragments (6.5 MB) are casilla records, 502 are pages (2.9 MB), 830 legal provisions and 323 CLI commands. A casilla record's content is its title, aliases and all four languages' descriptions (`dev/docs/pagefind_inject.py:360`), so the four language indexes carry the same text four times: about 52,500 of the package's documentation files. Per-language indexes and the cross-language content follow D4 and D5 of the terminology-search decisions.

### The package stores four uncompressed trees, and text is most of it

`dev/packaging/native/docs_build.py:93` builds one root per declared language and `dev/packaging/native/docs_stage.py:475` copies each whole. The files are stored as built; deflate reduces the English root from 93.8 MB to about 27 MB, and the package ZIP holds the 432 MB tree in 123 MB. The `cadrumo-docs` scheme handler is about 500 lines and serves files by manifest path (`native/desktop/src-tauri/src/docs/site.rs:47`). The manifest itself is 7.2 MB of indented JSON, one digest per file (`dev/packaging/native/docs_stage.py:548`).

### Options not yet taken, by size

- Ship one structure and each language's strings, composed when a page is requested: 289.6 MB of pages become 82.7 MB, and the 21.7 MB of identical non-page files become 7.2 MB. The desktop composes in its scheme handler (`native/desktop/src-tauri/src/docs/site.rs:47`); a static web host needs the pages expanded at publish. The strings can come from aligning four built roots, as measured here, or from one compile that emits them from the catalogues; only the second stops the registry projections, the CLI introspection, the sequence rendering and the theme rendering from running once per language (`dev/packaging/native/docs_build.py:93`).
- One search index for all languages, or casilla records indexed once: the index is 63.5 MB and 60,232 files across the four languages, and after the factoring it is the largest part of the documentation. A casilla record already carries all four languages' text (`dev/docs/pagefind_inject.py:360`). Amends D4 and D5 of the terminology-search decisions.
- State a section's shared legal basis once and keep per-card references that differ: about 6 MB of the structure. Amends D6 of `2026-07-15-docs-terminology-search-adr` and its per-entry gates, or is resolved in the registry if the shared references are an authoring shortcut.
- Re-author the 21 over-limit frames as text or narrower commands, and make the limit a refusal: up to 6 MB of the structure. A3 already covers the authoring; refusal amends A4.
- Store the structure compressed and inflate in the scheme handler: text deflates about 3.5 to 1. Changes the package contract; not prototyped.

Rejected on the evidence: compressing or delta-encoding four built trees as the answer, which leaves the four builds and stores the repetition instead of removing it; substituting text in the browser, which the no-JavaScript constraint in `2026-09-24-docs-build-performance-adr` excludes for the published site.

The evidence favours the shared structure first: it removes more than every other option together and its correctness is checkable byte for byte against the roots built today. The search index is the next decision.

## Sources

- `dev/docs/navigation.py:65`
- `dev/docs/shared_page_assets.py:1`
- `dev/docs/shared_structure.py:129`
- `dev/docs/casilla_legal_grounding.py:162`
- `dev/docs/casilla_card_rendering.py:161`
- `dev/docs/tests/test_casilla_anchor_parity.py:102`
- `dev/docs/sequences/checks.py:91`
- `dev/docs/pagefind_inject.py:360`
- `docs/pagefind.yml:26`
- `docs/conf.py:415`
- `docs/conf.py:1732`
- `dev/packaging/native/docs_build.py:93`
- `dev/packaging/native/docs_stage.py:475`
- `dev/packaging/native/docs_stage.py:548`
- `native/desktop/src-tauri/src/docs/site.rs:47`
- `native/package-layout.json` (`user_docs.languages`)
- `native/CONTRACT.md`
- Measurements: English and Spanish desktop roots built from commit `af1fb06015` with and without the 2026-10-06 changes, compared file by file over the media types the package serves. The scripts and roots were session scratch and are not retained; the same roots are produced by `python -m dev.docs.build --language <code> --flavor desktop --isolated-source --out-dir <dir>`.
